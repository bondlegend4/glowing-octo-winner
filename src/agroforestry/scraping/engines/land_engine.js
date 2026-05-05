/**
 * LAND.COM ENGINE
 * Handles DOM-based scraping for property leads using stable structural traversal.
 */
export async function handleLandScrape(page, dataset, config) {
    const { base_url, selectors } = config;
    
    console.log(`[LandEngine] Navigating to ${base_url}`);
    await page.goto(base_url, { waitUntil: 'networkidle2' });

    // 1. EXTRACT TOTAL COUNT
    // Uses the provided snippet: <div><h1>Header</h1><p>Count text</p></div>
    const totalCount = await page.evaluate(() => {
        const h1 = Array.from(document.querySelectorAll('h1'))
                        .find(el => el.textContent.includes('Land for Sale'));
        
        // Find the P tag within the same parent div as the H1
        const p = h1?.closest('div')?.querySelector('p');
        
        // Regex to find '122' in ": 1 - 25 of 122 listings"
        const match = p?.textContent.match(/of ([\d,]+) listings/);
        return match ? match[1].replace(',', '') : "0";
    });

    console.log(`[LandEngine] Detected ${totalCount} total listings for search.`);

    // 2. EXTRACT LISTING LEADS
    const listings = await page.$$eval(selectors.listing_container, (placards, sel) => {
        return placards.map(el => {
            const info = el.querySelector(sel.info_container);
            const link = el.querySelector(sel.property_link);
            
            // Address is typically the only <p> inside the info container
            const address = info?.querySelector(sel.address_selector)?.textContent;
            
            // Price and Size are in <span> tags. We filter by content to distinguish them.
            const spans = Array.from(info?.querySelectorAll(sel.price_selector) || []);
            const price = spans.find(s => s.textContent.includes('$'))?.textContent;
            const size = spans.find(s => s.textContent.toLowerCase().includes('acres'))?.textContent;
            
            return {
                url: link?.href,
                address: address?.trim(),
                price: price?.trim(),
                size: size?.trim()
            };
        });
    }, selectors);

    console.log(`[LandEngine] Successfully parsed ${listings.length} property placards.`);

    return {
        total: totalCount,
        leads: listings,
        apiUrl: listings[0]?.url // Satisfies the manifest's 'imported' logic
    };
}