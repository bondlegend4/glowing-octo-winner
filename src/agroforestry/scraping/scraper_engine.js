import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import fs from 'fs/promises';
// Import existing GIS logic
import { 
    findAndScrapeUrl, 
    scrapeApiUrlFromDetailsPage,
    saveUrlToJson 
} from './gis_scraper.js';

puppeteer.use(StealthPlugin());

/**
 * DISPATCHER: Routes tasks to the correct engine based on source type.
 * Exported for tests/scraper_dispatcher.test.js
 */
export async function runDispatcher(configData, engines = {}) {
    const browser = await puppeteer.launch({
        headless: "new",
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    try {
        for (const definition of configData.source_definitions) {
            const config = configData.configs[definition.type];
            
            // Flexible dataset collection for both GIS (categories) and Web (datasets)
            const datasets = definition.datasets || definition.categories.flatMap(c => c.datasets);

            for (const dataset of datasets) {
                if (dataset.imported) continue;

                const page = await browser.newPage();
                try {
                    if (definition.type === 'arcgis_rest') {
                        // Use the injected mock or the real handler
                        const handler = engines.gisEngine || handleGisScrape;
                        await handler(page, dataset, config);
                    } else if (definition.type === 'web_dom_land') {
                        const handler = engines.landEngine || handleLandScrape;
                        const result = await handler(page, dataset, config);
                        
                        if (result && result.apiUrl) {
                            await saveUrlToJson('./data/sources.json', dataset.id, result.apiUrl);
                        }
                    }
                } catch (err) {
                    console.error(`[Dispatcher] Failed ${dataset.id}:`, err);
                } finally {
                    await page.close();
                }
            }
        }
    } finally {
        await browser.close();
    }
}

/**
 * LAND.COM ENGINE
 * Exported for tests/land_scraper.test.js
 */
export async function handleLandScrape(page, dataset, config) {
    console.log(`[LandEngine] Scraping ${dataset.id} at ${config.base_url}`);
    await page.goto(config.base_url, { waitUntil: 'networkidle2' });

    // Dynamic Total Count Logic
    const totalCount = await page.evaluate(() => {
        const h1 = Array.from(document.querySelectorAll('h1')).find(el => el.textContent.includes('Land for Sale'));
        const p = h1?.closest('div')?.querySelector('p');
        return p?.textContent.match(/of ([\d,]+) listings/)?.[1].replace(',', '') || "0";
    });

    // Listing Extraction using stable data-attributes
    const listings = await page.$$eval(config.selectors.listing_container, (elements, sel) => {
        return elements.map(el => ({
            url: el.querySelector(sel.property_link)?.href,
            address: el.querySelector(sel.address_selector)?.innerText,
            price: el.querySelector(sel.price_selector)?.innerText
        }));
    }, config.selectors);

    console.log(`[LandEngine] Found ${listings.length} items of ${totalCount} total.`);
    
    // For now, return the first valid link as the "scraped_url" to satisfy the manifest
    return { 
        totalCount, 
        listings, 
        apiUrl: listings[0]?.url 
    };
}

/**
 * ARCGIS ENGINE WRAPPER
 */
export async function handleGisScrape(page, dataset, config) {
    // Reconstruct the source object expected by the original gis_scraper functions
    const sourceWrapper = { ...config, ...dataset, origin_url: `${config.base_search_url}${dataset.category || ''}` };
    
    const detailsUrl = await findAndScrapeUrl(page, sourceWrapper);
    if (detailsUrl) {
        const apiUrl = await scrapeApiUrlFromDetailsPage(page, detailsUrl, sourceWrapper);
        if (apiUrl) {
            await saveUrlToJson('./data/sources.json', dataset.id, apiUrl);
        }
    }
}

// Main execution block
async function main() {
    try {
        const configData = JSON.parse(await fs.readFile('./data/sources.json', 'utf-8'));
        await runDispatcher(configData);
    } catch (err) {
        console.error("Main Engine Error:", err);
    }
}

if (import.meta.url === `file://${process.argv[1]}`) {
    main();
}