import { findAndScrapeUrl, scrapeApiUrlFromDetailsPage, saveUrlToJson } from '../gis_scraper.js';

/**
 * Performs the specific navigation logic for the NYS GIS Portal.
 */
export async function handleGisScrape(page, dataset, config) {
    // Reconstruct the source object for legacy function compatibility
    const sourceWrapper = { 
        ...config, 
        ...dataset, 
        origin_url: `${config.base_search_url}${dataset.category || ''}` 
    };

    console.log(`[GisEngine] Processing ${dataset.search_term}...`);
    
    const detailsUrl = await findAndScrapeUrl(page, sourceWrapper);
    if (detailsUrl) {
        const apiUrl = await scrapeApiUrlFromDetailsPage(page, detailsUrl, sourceWrapper);
        if (apiUrl) {
            // Save result back to manifest
            await saveUrlToJson('./data/sources.json', dataset.id, apiUrl);
            return apiUrl;
        }
    }
    throw new Error(`Failed to extract API URL for ${dataset.id}`);
}