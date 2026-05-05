import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import fs from 'fs/promises';
// Import existing GIS logic
import { findAndScrapeUrl, scrapeApiUrlFromDetailsPage } from './gis_scraper.js';

puppeteer.use(StealthPlugin());

async function main() {
    const configData = JSON.parse(await fs.readFile('./data/sources.json', 'utf-8'));
    const browser = await puppeteer.launch({
        headless: "new",
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    for (const definition of configData.source_definitions) {
        const config = configData.configs[definition.type];
        
        for (const dataset of definition.datasets || definition.categories.flatMap(c => c.datasets)) {
            if (dataset.imported) continue;

            const page = await browser.newPage();
            try {
                if (definition.type === 'arcgis_rest') {
                    await handleGisScrape(page, dataset, config);
                } else if (definition.type === 'web_dom_land') {
                    await handleLandScrape(page, dataset, config);
                }
            } catch (err) {
                console.error(`Failed ${dataset.id}:`, err);
            } finally {
                await page.close();
            }
        }
    }
    await browser.close();
}

/**
 * LAND.COM ENGINE
 * Uses stable data-attributes and text-traversal instead of randomized IDs.
 */
async function handleLandScrape(page, dataset, config) {
    await page.goto(config.base_url, { waitUntil: 'networkidle2' });

    // Dynamic Search Result Count via H1 adjacency
    const totalCount = await page.evaluate(() => {
        const h1 = Array.from(document.querySelectorAll('h1')).find(el => el.textContent.includes('Land for Sale'));
        const p = h1?.closest('div')?.querySelector('p');
        return p?.textContent.match(/of ([\d,]+) listings/)?.[1].replace(',', '') || "0";
    });

    const listings = await page.$$eval(config.selectors.listing_container, (elements, sel) => {
        return elements.map(el => ({
            url: el.querySelector(sel.property_link)?.href,
            address: el.querySelector(sel.address_selector)?.innerText,
            price: el.querySelector(sel.price_selector)?.innerText
        }));
    }, config.selectors);

    console.log(`[Land.com] Found ${totalCount} listings for ${dataset.id}`);
    // logic to save to sources.json or land_leads table...
}