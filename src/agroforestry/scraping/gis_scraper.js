import puppeteer from 'puppeteer';

/**
 * Clicks the "More results" button until all pages are loaded.
 * @param {import('puppeteer').Page} page The Puppeteer page object.
 * @param {import('puppeteer').ElementHandle} catalogHandle Handle to the <arcgis-hub-catalog>.
 */
export async function loadAllResults(page, catalogHandle) {
    // FIX: Wait for the results count element to be ready to prevent timing errors.
    console.log('Waiting for results count to be visible...');
    await page.waitForFunction(() => {
        const catalog = document.querySelector('arcgis-hub-catalog');
        const gallery = catalog?.shadowRoot?.querySelector('arcgis-hub-gallery');
        const p = gallery?.shadowRoot?.querySelector('p.results-count');
        // Ensure the text has loaded, e.g., "1 - 12 of 26 results"
        return p && p.textContent.includes('of');
    });
    console.log('Results count is visible.');

    const resultHandle = await catalogHandle.evaluateHandle(el =>
        el.shadowRoot?.querySelector('arcgis-hub-gallery')?.shadowRoot?.querySelector('p.results-count')
    );
    // This should no longer fail, but we add a check for safety.
    if (!resultHandle.asElement()) {
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
        const moreButtonHandle = await catalogHandle.evaluateHandle(el =>
            el.shadowRoot?.querySelector('arcgis-hub-gallery')?.shadowRoot?.querySelector('div.gallery-list-footer calcite-button')
        );
        if (moreButtonHandle.asElement()) {
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
 * Searches for a card with a specific data-test ID on the current page.
 * @param {import('puppeteer').ElementHandle} catalogHandle Handle to the <arcgis-hub-catalog>.
 * @param {string} cardTestId The value of the data-test attribute (e.g., "Dams").
 * @returns {Promise<import('puppeteer').ElementHandle|null>}
 */
export async function findCardOnPage(catalogHandle, cardTestId) {
    console.log(`Searching for card with data-test="${cardTestId}"...`);
    const cardHandle = await catalogHandle.evaluateHandle((el, id) => {
        const gallery = el.shadowRoot?.querySelector('arcgis-hub-gallery');
        const layoutList = gallery?.shadowRoot?.querySelector('arcgis-hub-gallery-layout-list');
        return layoutList?.shadowRoot?.querySelector(`arcgis-hub-entity-card[data-test="${id}"]`);
    }, cardTestId); // Pass cardTestId as an argument to evaluateHandle

    if (cardHandle.asElement()) {
        console.log(`Found card: "${cardTestId}"`);
        return cardHandle;
    }

    console.log(`Card "${cardTestId}" not found on the current view.`);
    return null;
}

/**
 * Extracts the URL from a given entity card handle.
 * @param {import('puppeteer').ElementHandle} cardHandle Handle to the <arcgis-hub-entity-card>.
 * @returns {Promise<string|null>}
 */
export async function extractUrlFromCard(cardHandle) {
    // Traverse the two nested shadow roots to find the link.
    const linkHandle = await cardHandle.evaluateHandle(el => {
        const hubCard = el.shadowRoot?.querySelector('arcgis-hub-card');
        // The link is inside the hubCard's shadow root.
        return hubCard?.shadowRoot?.querySelector('h3.title a');
    });

    if (!linkHandle.asElement()) return null; // Return null if the link isn't found
    return await linkHandle.evaluate(el => el.href);
}


/**
 * Now handles multiple possible button/workflows to find the API link.
 * @param {import('puppeteer').Page} page The Puppeteer page object.
 * @param {string} detailsUrl The URL of the dataset's map/details page.
 * @returns {Promise<string|null>} The GeoJSON API or data source URL.
 */
export async function scrapeApiUrlFromDetailsPage(page, detailsUrl) {
    console.log(`\nNavigating to details page: ${detailsUrl}`);
    await page.goto(detailsUrl, { waitUntil: 'networkidle0', timeout: 60000 });
    console.log(`Landed on page: ${page.url()}`);

    try {
        if (page.url().includes('/explore')) {
            // 1. Find the button that opens the side panel (the "About" button).
            const infoButtonXPath = "//button[contains(., 'About')]";
            console.log('Looking for the info panel button...');
            const infoPanelButton = await page.waitForSelector(`xpath/${infoButtonXPath}`);

            // 2. Click it if it's not already active.
            const buttonClassName = await infoPanelButton.evaluate(el => el.className);
            if (!buttonClassName.includes('active')) {
                console.log("Button is not active. Clicking to open side panel...");
                await infoPanelButton.click();
                console.log("Button clicked");
            } else {
                console.log("Side panel is already active.");
            }

            // 3. Wait for the "View Full Details" link to appear inside the panel.
            console.log("Waiting for 'View Full Details' link to appear...");
            const detailsLinkXPath = "//div[@class='side-panel-ref']//a[contains(., 'View Full Details')]";
            const fullDetailsLink = await page.waitForSelector(`xpath/${detailsLinkXPath}`);

            // 4. Click the "View Full Details" link to trigger the dynamic content load.
            console.log('Found "View Full Details" link, clicking...');
            await fullDetailsLink.evaluate(el => el.click());
        }

        try {
            // 5. Wait for the API link content to appear on the new view.
            const apiResourcesButton = await page.waitForSelector('button[data-test="apiResources"]', { timeout: 15000 });
            console.log('Found "API Resource" link, clicking...');
            /*Even though this is a button it is not actually ".click()" able. 
            I think cause it's clicked by js.*/
            await apiResourcesButton.evaluate(el => el.click());
            console.log('Clicked "View API Resources" button.');


            // 6. Find the specific container div that holds the API resources.
            const containerXPath = "//div[contains(@class, 'content-action-card') and .//button[@data-test='apiResources']]";
            const containerHandle = await page.waitForSelector(`xpath/${containerXPath}`);

            // 4. Search for the input elements ONLY within that container.
            console.log('Searching for all <arcgis-copyable-input> elements within the specific container...');
            const candidateInputs = await containerHandle.$$('arcgis-copyable-input');
            console.log(`Found ${candidateInputs.length} total <arcgis-copyable-input> elements to inspect.`);

            // 5. Loop through the scoped candidates to find the GeoJSON link.
            // --- DIAGNOSTIC LOGIC ---
            // 1. Create an array to hold the data we find.
            const foundData = [];

            // 2. Loop through every input and extract its internal label and value.
            for (const inputHandle of candidateInputs) {
                const collectedData = await inputHandle.evaluate(el => {
                    return {
                        label: el.shadowRoot?.querySelector('label')?.textContent.trim() || 'LABEL NOT FOUND',
                        value: el.value || 'VALUE NOT FOUND'
                    };
                });
                foundData.push(collectedData);
            }



            // 4. Now, search through the data we collected for the target.
            const geoJsonData = foundData.find(data => data.value.includes('geojson'));

            if (geoJsonData) {
                console.log('SUCCESS: Found GeoJSON data by searching the URL value.');
                return geoJsonData.value;
            } else {
                // 3. Print a table of everything that was found.
                console.log('\n--- DEBUG: Inspecting contents of all found inputs: ---');
                console.table(foundData);
                console.log('--- END OF DEBUG DATA ---\n');
            }

        }
        catch {
            // --- Fallback Logic ---
            console.warn('Could not find GeoJSON input by its label. Trying fallback...');
            const dataSourceLink = await page.$('a[data-test="dataSource"]');
            if (dataSourceLink) {
                console.log('Found Data Source link via fallback.');
                return dataSourceLink.evaluate(el => el.href);
            }
        }



    } catch (error) {
        console.error('A critical step failed while scraping the details page.', error);
    }

    console.error('Could not find any API or Data Source link on the page.');
    return null;
}


/**
 * Main orchestrator function to find and scrape a URL.
 * It first checks the current page, then loads all results and checks again.
 * @param {import('puppeteer').Page} page
 * @param {string} cardToFind The data-test ID of the card to find.
 */
export async function findAndScrapeUrl(page, cardToFind) {
    await page.goto('https://data.gis.ny.gov/search?categories=%2Fcategories%2Fwater', {
        waitUntil: 'networkidle0'
    });
    const catalogHandle = await page.waitForSelector('arcgis-hub-catalog');

    // 1. Try to find the card on the first page.
    let cardHandle = await findCardOnPage(catalogHandle, cardToFind);

    // 2. If not found, load all results and search again.
    if (!cardHandle) {
        await loadAllResults(page, catalogHandle);
        cardHandle = await findCardOnPage(catalogHandle, cardToFind);
    }

    // 3. If we have the card handle (either from step 1 or 2), extract the URL.
    if (cardHandle) {
        return extractUrlFromCard(cardHandle);
    }

    console.error(`Could not find the card "${cardToFind}" after all attempts.`);
    return null;
}


// This allows the file to be run directly from the command line
async function main() {
    let browser;
    try {
        console.log('🚀 Launching scraper...');
        browser = await puppeteer.launch({ headless: "new" });
        const page = await browser.newPage();

        // --- STAGE 1: Find the initial details page URL ---
        const detailsUrl = await findAndScrapeUrl(page, 'Dams');

        if (detailsUrl) {
            console.log(`\n✅ STAGE 1 COMPLETE: Found details page URL: ${detailsUrl}`);

            // --- STAGE 2: Navigate to the details page and find the API link ---
            const apiUrl = await scrapeApiUrlFromDetailsPage(page, detailsUrl);

            if (apiUrl) {
                console.log('\n--- SCRAPER COMPLETE ---');
                console.log(`✅ STAGE 2 COMPLETE: Found API URL: ${apiUrl}`);
                console.log('------------------------\n');
            } else {
                console.log('\n--- SCRAPER FAILED ---');
                console.log('❌ Could not find the final API URL in Stage 2.');
                console.log('----------------------\n');
            }
        } else {
            console.log('\n--- SCRAPER FAILED ---');
            console.log('❌ Could not find the initial details URL in Stage 1.');
            console.log('----------------------\n');
        }

    } catch (error) {
        console.error('An error occurred during scraping:', error);
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}


// This condition checks if the script is being run directly
if (process.argv[1] && process.argv[1].endsWith('gis_scraper.js')) {
    main();
}