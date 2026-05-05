const puppeteer = require('puppeteer');
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

async function scrapeLandCom(page, source) {
    await page.goto(source.base_url, { waitUntil: 'networkidle2' });

    // --- Dynamic Total Count Logic ---
    // Look for a div containing an h1 with "Land for Sale"
    const totalCount = await page.evaluate(() => {
        const h1s = Array.from(document.querySelectorAll('h1'));
        const targetH1 = h1s.find(h1 => h1.textContent.includes('Land for Sale'));
        if (!targetH1) return "0";
        
        const parentDiv = targetH1.closest('div');
        const pTag = parentDiv.querySelector('p');
        
        // Extract number from ": 1 - 25 of 193 listings"
        const match = pTag.textContent.match(/of ([\d,]+) listings/);
        return match ? match[1].replace(',', '') : "0";
    });

    console.log(`[Land.com] Detected ${totalCount} total listings.`);

    // --- Listing Extraction ---
    const listings = await page.$$eval(source.selectors.listing_container, (elements) => {
        return elements.map(el => ({
            url: el.querySelector('a[href*="/property/"]')?.href,
            address: el.querySelector('p.af8d67c')?.innerText,
            price: el.querySelector('span._6ae8672')?.innerText // Bonus selector
        }));
    });

    return { totalCount, listings };
}

// Example usage following your current URL structure
scrapeLandCom('https://www.land.com/New-York/all-land/for-sale/is-active/type-179/page-1/').then(console.log);