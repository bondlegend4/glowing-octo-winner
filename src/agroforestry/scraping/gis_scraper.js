import puppeteer from 'puppeteer';

/**
 * Clicks the "More results" button until all pages are loaded.
 * @param {import('puppeteer').Page} page The Puppeteer page object.
 * @param {import('puppeteer').ElementHandle} catalogHandle Handle to the <arcgis-hub-catalog>.
 */
export async function loadAllResults(page, catalogHandle) {
    console.log('Calculating how many times to click "More results"...');
    const resultHandle = await catalogHandle.evaluateHandle(el =>
        el.shadowRoot?.querySelector('arcgis-hub-gallery')?.shadowRoot?.querySelector('p.results-count')
    );
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
    const linkHandle = await cardHandle.evaluateHandle(el => el.shadowRoot.querySelector('h3.title a'));
    return await linkHandle.evaluate(el => el.href);
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
        
        const damsUrl = await findAndScrapeUrl(page, 'Dams');

        if (damsUrl) {
            console.log('\n--- SCRAPER COMPLETE ---');
            console.log(`✅ Extracted URL: ${damsUrl}`);
            console.log('------------------------\n');
        } else {
            console.log('\n--- SCRAPER FAILED ---');
            console.log('❌ Could not find the URL for "Dams".');
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