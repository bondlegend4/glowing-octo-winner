import puppeteer from 'puppeteer';
import fs from 'fs/promises';

/**
 * Reads, updates, and writes the scraped URL back to the JSON configuration file.
 * @param {string} filePath - The path to the sources.json file.
 * @param {string} datasetId - The unique ID of the dataset to update.
 * @param {string} apiUrl - The scraped API URL to save.
 */
export async function saveUrlToJson(filePath, datasetId, apiUrl) {
    try {
        const fileContent = await fs.readFile(filePath, 'utf-8');
        const config = JSON.parse(fileContent);
        let updated = false;

        for (const definition of config.source_definitions) {
            for (const category of definition.categories) {
                const dataset = category.datasets.find(d => d.id === datasetId);
                if (dataset) {
                    dataset.scraped_url = apiUrl;
                    dataset.imported = true;
                    updated = true;
                    break; // Exit the inner loop once found and updated
                }
            }
            if (updated) break; // Exit the outer loop
        }

        if (updated) {
            await fs.writeFile(filePath, JSON.stringify(config, null, 4));
            console.log(`✅ Successfully updated ${datasetId} in ${filePath}`);
        } else {
            console.warn(`Could not find dataset with id "${datasetId}" to update.`);
        }
    } catch (error) {
        console.error(`Error saving URL to JSON:`, error);
    }
}


/**
 * Processes the raw configuration object into a flat list of source objects ready for scraping.
 * This separates configuration logic from the scraping execution.
 * @param {object} config - The parsed JSON configuration object from sources.json.
 * @returns {Array<object>} A flat array of fully-formed source objects.
 */
export function processSourceDefinitions(config) {
    const processedSources = [];
    const baseConfig = config.base_config || {};

    for (const definition of config.source_definitions) {
        for (const category of definition.categories) {
            const origin_url = `${baseConfig.base_search_url}${category.category}`;
            for (const dataset of category.datasets) {
                processedSources.push({
                    ...baseConfig,
                    name: definition.name,
                    category: category.category,
                    ...dataset,
                    origin_url
                });
            }
        }
    }
    return processedSources;
}

/**
 * A reusable helper to query through nested shadow DOMs.
 * @param {import('puppeteer').ElementHandle} parentHandle - The starting element.
 * @param {string[]} path - An array of shadow host selectors.
 * @param {string} finalSelector - The selector for the target element in the final shadow root.
 * @returns {Promise<import('puppeteer').ElementHandle|null>}
 */
async function queryShadowDom(parentHandle, path, finalSelector) {
    let currentHandle = parentHandle;
    for (const selector of path) {
        // Correctly pass `selector` as an argument `sel` into the browser context
        const nextHandle = await currentHandle.evaluateHandle((el, sel) => el.shadowRoot?.querySelector(sel), selector);
        if (!nextHandle.asElement()) return null;
        currentHandle = nextHandle;
    }
    // Also apply the fix to the final query for consistency
    const finalElementHandle = await currentHandle.evaluateHandle((el, sel) => el.shadowRoot?.querySelector(sel), finalSelector);
    return finalElementHandle.asElement() ? finalElementHandle : null;
}

/**
 * Clicks the "More results" button until all pages are loaded based on config.
 * @param {import('puppeteer').Page} page
 * @param {import('puppeteer').ElementHandle} catalogHandle
 * @param {object} source - The configuration object for the data source.
 */
export async function loadAllResults(page, catalogHandle, source) {
    const { selectors } = source;

    console.log('Waiting for results count to be visible...');
    await page.waitForFunction((path, query) => {
        let element = document.querySelector('arcgis-hub-catalog');
        for (const p of path) {
            element = element?.shadowRoot.querySelector(p);
        }
        const countEl = element?.shadowRoot.querySelector(query);
        return countEl && countEl.textContent.includes('of');
    }, {}, selectors.results_count.path, selectors.results_count.query);
    console.log('Results count is visible.');

    const resultHandle = await queryShadowDom(catalogHandle, selectors.results_count.path, selectors.results_count.query);
    if (!resultHandle) {
        console.log('Could not read result count, cannot click "More results".');
        return;
    }
    const resultText = await resultHandle.evaluate(el => el.textContent);
    const matches = resultText.match(/(\d+)\s*-\s*(\d+)\s*of\s*(\d+)/);

    let clicksNeeded = 0;
    if (matches) {
        const resultsPerPage = parseInt(matches[2], 10) - parseInt(matches[1], 10) + 1;
        const totalResults = parseInt(matches[3], 10);
        clicksNeeded = Math.ceil(totalResults / resultsPerPage) - 1;
        console.log(`Need to click ${clicksNeeded} time(s).`);
    }

    for (let i = 0; i < clicksNeeded; i++) {
        const moreButtonHandle = await queryShadowDom(catalogHandle, selectors.more_results_button.path, selectors.more_results_button.query);
        if (moreButtonHandle) {
            console.log(`Clicking 'More results'... (${i + 1}/${clicksNeeded})`);
            await moreButtonHandle.click();
            await new Promise(r => setTimeout(r, 2000));
        } else {
            console.log('No more "More results" button found. Stopping.');
            break;
        }
    }
}

/**
 * Finds a specific entity card on the page using selectors from the config.
 * @param {import('puppeteer').ElementHandle} catalogHandle
 * @param {object} source - The configuration object.
 * @returns {Promise<import('puppeteer').ElementHandle|null>}
 */
export async function findCardOnPage(catalogHandle, source) {
    const { selectors, search_term } = source;
    const finalQuery = selectors.gallery_card.query.replace('{SEARCH_TERM}', search_term);
    console.log(`Searching for card with selector: "${finalQuery}"...`);

    const cardHandle = await queryShadowDom(catalogHandle, selectors.gallery_card.path, finalQuery);

    if (cardHandle) {
        console.log(`Found card: "${search_term}"`);
        return cardHandle;
    }
    console.log(`Card "${search_term}" not found on the current view.`);
    return null;
}

/**
 * Extracts the URL from a given card handle.
 * @param {import('puppeteer').ElementHandle} cardHandle
 * @param {object} source - The configuration object.
 * @returns {Promise<string|null>}
 */
export async function extractUrlFromCard(cardHandle, source) {
    const { card_url } = source.selectors;
    const linkHandle = await queryShadowDom(cardHandle, card_url.path, card_url.query);
    if (!linkHandle) return null;
    return linkHandle.evaluate(el => el.href);
}

/**
 * Scrapes the API URL from the dataset's details page.
 * @param {import('puppeteer').Page} page
 * @param {string} detailsUrl
 * @param {object} source - The configuration object.
 * @returns {Promise<string|null>} The GeoJSON API or data source URL.
 */
export async function scrapeApiUrlFromDetailsPage(page, detailsUrl, source) {
    console.log(`\nNavigating to details page: ${detailsUrl}`);
    await page.goto(detailsUrl, { waitUntil: 'networkidle0', timeout: 60000 });
    console.log(`Landed on page: ${page.url()}`);

    const { selectors } = source;
    const pageSelectors = selectors.details_page;

    try {
        // Handle the "/explore" page workflow first
        if (page.url().includes('/explore')) {
            console.log('Detected /explore URL, initiating side panel workflow...');
            const infoButton = await page.waitForSelector(`xpath/${pageSelectors.info_button_xpath}`);
            if (!(await infoButton.evaluate(el => el.className.includes('active')))) {
                await infoButton.click();
            }
            const fullDetailsLink = await page.waitForSelector(`xpath/${pageSelectors.details_link_xpath}`);
            await fullDetailsLink.evaluate(el => el.click());
        }

        // Try the primary method: finding the API resources button and inputs
        try {
            const apiResourcesButton = await page.waitForSelector(pageSelectors.api_resources_button, { timeout: 15000 });
            await apiResourcesButton.evaluate(el => el.click());

            const containerHandle = await page.waitForSelector(`xpath/${pageSelectors.api_container_xpath}`);
            const candidateInputs = await containerHandle.$$(pageSelectors.api_input_selector);

            const foundData = [];
            for (const inputHandle of candidateInputs) {
                const collectedData = await inputHandle.evaluate(el => ({
                    label: el.shadowRoot?.querySelector('label')?.textContent.trim() || 'LABEL NOT FOUND',
                    value: el.value || 'VALUE NOT FOUND'
                }));
                foundData.push(collectedData);
            }

            const geoJsonData = foundData.find(data => data.value.includes(pageSelectors.api_input_value_match));

            if (geoJsonData) {
                console.log(`SUCCESS: Found ${pageSelectors.api_input_value_match} data by searching the URL value.`);
                return geoJsonData.value;
            } else {
                console.log('\n--- DEBUG: Inspecting contents of all found inputs: ---');
                console.table(foundData);
                console.log('--- END OF DEBUG DATA ---\n');
            }
        } catch (e) {
            console.warn('Primary method failed or timed out. Trying fallback...');
            // This catch block intentionally allows the code to proceed to the fallback
        }

        // Fallback Logic: if the primary method fails, look for a direct data source link
        const dataSourceLink = await page.$(pageSelectors.fallback_api_selector);
        if (dataSourceLink) {
            console.log('SUCCESS: Found Data Source link via fallback.');
            return dataSourceLink.evaluate(el => el.href);
        }

    } catch (error) {
        console.error('A critical step failed while scraping the details page.', error);
    }

    console.error('Could not find any API or Data Source link on the page.');
    return null;
}


/**
 * Main orchestrator that finds and scrapes a URL based on the source config.
 * @param {import('puppeteer').Page} page
 * @param {object} source - The configuration object.
 * @returns {Promise<string|null>}
 */
export async function findAndScrapeUrl(page, source) {
    await page.goto(source.origin_url, { waitUntil: 'networkidle0' });
    const catalogHandle = await page.waitForSelector(source.selectors.catalog_container);

    let cardHandle = await findCardOnPage(catalogHandle, source);
    if (!cardHandle) {
        await loadAllResults(page, catalogHandle, source);
        cardHandle = await findCardOnPage(catalogHandle, source);
    }

    if (cardHandle) {
        return extractUrlFromCard(cardHandle, source);
    }
    console.error(`Could not find the card "${source.search_term}" after all attempts.`);
    return null;
}

/**
 * Main execution block.
 */
/* All helper functions (saveUrlToJson, queryShadowDom, etc.) remain the same */

/**
 * Main execution block updated to programmatically build the origin URL.
 */
async function main() {
    let browser;
    const jsonPath = './data/sources.json';
    try {
        const configData = await fs.readFile(jsonPath, 'utf-8');
        const config = JSON.parse(configData);
        
        const sourcesToScrape = processSourceDefinitions(config);

        for (const source of sourcesToScrape) {
            if (source.imported) {
                console.log(`Skipping already imported dataset: "${source.search_term}"`);
                continue;
            }

            console.log(`\n🚀 --- Scraping Dataset: ${source.search_term} --- 🚀`);
            browser = await puppeteer.launch({ headless: "new" });
            const page = await browser.newPage();
            
            const detailsUrl = await findAndScrapeUrl(page, source);

            if (detailsUrl) {
                console.log(`\n✅ STAGE 1 COMPLETE: Found details page URL: ${detailsUrl}`);
                const apiUrl = await scrapeApiUrlFromDetailsPage(page, detailsUrl, source);

                if (apiUrl) {
                    console.log(`✅ STAGE 2 COMPLETE: Found API URL: ${apiUrl}`);
                    // Save the successful result back to the JSON file
                    await saveUrlToJson(jsonPath, source.id, apiUrl);
                } else {
                    console.log(`❌ FAILED STAGE 2 for "${source.search_term}".`);
                }
            } else {
                console.log(`❌ FAILED STAGE 1 for "${source.search_term}".`);
            }
            
            await browser.close();
            console.log(`\n--- FINISHED: ${source.search_term} ---\n`);
        }

    } catch (error) {
        console.error('A critical error occurred during the main process:', error);
    } finally {
        if (browser?.process() != null) {
            await browser.close();
        }
    }
}

/* Other helper functions and the final if block remain the same */

// Check if the script is being run directly to execute main()
if (import.meta.url === `file://${process.argv[1]}`) {
    main();
}