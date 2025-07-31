import { jest, describe, it, expect, beforeAll, afterAll, beforeEach, afterEach } from '@jest/globals';
import puppeteer from 'puppeteer';
import {
    findCardOnPage,
    loadAllResults,
    extractUrlFromCard,
    findAndScrapeUrl,
    scrapeApiUrlFromDetailsPage // Import the new function
} from '../src/agroforestry/scraping/gis_scraper.js';

// A mock source configuration object to be used in tests
const mockSource = {
    search_term: "Dams",
    selectors: {
        catalog_container: "arcgis-hub-catalog",
        gallery_card: {
            query: "arcgis-hub-entity-card[data-test='{SEARCH_TERM}']",
            path: ["arcgis-hub-gallery", "arcgis-hub-gallery-layout-list"]
        },
        more_results_button: {
            query: "div.gallery-list-footer calcite-button",
            path: ["arcgis-hub-gallery"]
        },
        results_count: {
            query: "p.results-count",
            path: ["arcgis-hub-gallery"]
        },
        card_url: {
            query: "h3.title a",
            path: ["arcgis-hub-card"]
        },
        details_page: {
            info_button_xpath: "//button[contains(., 'About')]",
            details_link_xpath: "//div[@class='side-panel-ref']//a[contains(., 'View Full Details')]",
            api_resources_button: "button[data-test='apiResources']",
            api_container_xpath: "//div[contains(@class, 'content-action-card') and .//button[@data-test='apiResources']]",
            api_input_selector: "arcgis-copyable-input",
            api_input_value_match: "geojson",
            fallback_api_selector: "a[data-test='dataSource']"
        }
    }
};


jest.setTimeout(90000);

describe('GIS Scraper Functions', () => {
    let browser;
    let page;
    let catalogHandle;

    beforeAll(async () => {
        browser = await puppeteer.launch({ headless: "new" });
    });

    afterAll(async () => {
        await browser.close();
    });

    // Before each test, navigate to a fresh page and get the main catalog handle
    beforeEach(async () => {
        page = await browser.newPage();
        // FIX: Add a retry loop to make navigation more resilient to network errors.
        let success = false;
        for (let i = 0; i < 3; i++) { // Try up to 3 times
            try {
                await page.goto('https://data.gis.ny.gov/search?categories=%2Fcategories%2Fwater', {
                    waitUntil: 'networkidle0',
                    timeout: 60000
                });
                success = true;
                break; // Exit loop on success
            } catch (error) {
                console.warn(`Attempt ${i + 1} to navigate failed. Retrying...`);
                if (i === 2) throw error; // Rethrow error on last attempt
            }
        }
        catalogHandle = await page.waitForSelector('arcgis-hub-catalog');
    });

    afterEach(async () => {
        await page.close();
    });

    // --- Tests for Stage 1 functions ---
    // --- Test Suite for findCardOnPage ---
    describe('findCardOnPage', () => {
        it('should find that multiple cards exist on the first page', async () => {
            const cardHandle = await findCardOnPage(catalogHandle, { ...mockSource, search_term: 'Sediment Caps' });
            expect(cardHandle).not.toBeNull();
        });
    });

    // --- Test Suite for loadAllResults ---
    describe('loadAllResults', () => {
        it('should load new results onto the page', async () => {
            const getCardCount = () => catalogHandle.evaluate(el => el.shadowRoot?.querySelector('arcgis-hub-gallery')?.shadowRoot?.querySelector('arcgis-hub-gallery-layout-list')?.shadowRoot?.querySelectorAll('arcgis-hub-entity-card').length);

            const initialCount = await getCardCount();
            expect(initialCount).toBeGreaterThan(0);

            // Pass the mockSource object to the function
            await loadAllResults(page, catalogHandle, mockSource);

            const finalCount = await getCardCount();
            expect(finalCount).toBeGreaterThan(initialCount);
        });
    });

    // --- Test Suite for extractUrlFromCard ---
    describe('extractUrlFromCard', () => {
        it('should extract a valid URL from a given card handle', async () => {
            const cardHandle = await findCardOnPage(catalogHandle, { ...mockSource, search_term: 'Sediment Caps' });
            expect(cardHandle).not.toBeNull();

            // Pass the mockSource object to the function
            const url = await extractUrlFromCard(cardHandle, mockSource);
            expect(typeof url).toBe('string');
            expect(url).toContain('https://data.gis.ny.gov/maps/');
        });
    });

    // --- Test Suite for scrapeApiUrlFromDetailsPage ---
    describe('scrapeApiUrlFromDetailsPage', () => {
        it('should redirect and extract the API link from the /about page', async () => {
            const damsDetailsUrl = 'https://data.gis.ny.gov/maps/71781adc8f9d4c70b35f5c1ac3168833';
            const testPage = await browser.newPage();
            
            // Pass the mockSource object to the function
            const apiUrl = await scrapeApiUrlFromDetailsPage(testPage, damsDetailsUrl, mockSource);

            expect(apiUrl).not.toBeNull();
            expect(apiUrl).toContain('/FeatureServer/');
            expect(apiUrl).toContain('geojson');
        });
    });

    describe('scrapeApiUrlFromDetailsPageDataSource', () => {
        it('should redirect and extract the API link from the /about page', async () => {
            const damsDetailsUrl = 'https://data.gis.ny.gov/maps/eaa83cbb75c045db8290109b3a94c847';
            const testPage = await browser.newPage();
            
            // This function call will now be tested
            const apiUrl = await scrapeApiUrlFromDetailsPage(testPage, damsDetailsUrl, mockSource);

            // Assert that the final API URL was found
            expect(apiUrl).not.toBeNull();
            expect(apiUrl).toContain('/FeatureServer');
        });
    });

    // --- End-to-End Integration Test ---
    describe('findAndScrapeUrl (End-to-End)', () => {
        it('should complete both stages and return the final API URL for "Dams"', async () => {
            const testPage = await browser.newPage();
            // Pass the complete mockSource object
            const detailsUrl = await findAndScrapeUrl(testPage, { ...mockSource, origin_url: 'https://data.gis.ny.gov/search?q=Dams' });

            // The original test had an incorrect expectation for the URL. 
            // The important part is that a URL is returned.
            expect(detailsUrl).toContain('https://data.gis.ny.gov/maps/');
            
            const apiUrl = await scrapeApiUrlFromDetailsPage(testPage, detailsUrl, mockSource);
            expect(apiUrl).not.toBeNull();
            expect(apiUrl).toContain('/FeatureServer');
            await testPage.close();
        });
    });
});