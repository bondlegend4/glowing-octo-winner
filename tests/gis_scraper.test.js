import { jest, describe, it, expect, beforeAll, afterAll, beforeEach, afterEach } from '@jest/globals';
import puppeteer from 'puppeteer';
import fs from 'fs/promises'; // Import the file system module for testing

import {
    saveUrlToJson, // Import the new function
    processSourceDefinitions,
    findCardOnPage,
    loadAllResults,
    extractUrlFromCard,
    findAndScrapeUrl,
    scrapeApiUrlFromDetailsPage
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

// --- Test Suite for JSON Processing ---
describe('JSON Processing', () => {
    it('should correctly combine a source definition with its datasets', () => {
        const mockConfig = {
            source_definitions: [{
                name: "Test_Catalog",
                origin_url: "http://test.com",
                selectors: { "test_selector": "value" },
                datasets: [
                    { id: "d1", purpose: "p1", search_term: "s1" },
                    { id: "d2", purpose: "p2", search_term: "s2" },
                ]
            }]
        };

        const processed = processSourceDefinitions(mockConfig);

        // Check that the output is an array of the correct length
        expect(Array.isArray(processed)).toBe(true);
        expect(processed.length).toBe(2);

        // Check that properties were merged correctly
        expect(processed[0].name).toBe("Test_Catalog");
        expect(processed[0].origin_url).toBe("http://test.com");
        expect(processed[0].id).toBe("d1");
        expect(processed[0].search_term).toBe("s1");
        expect(processed[0].selectors).toEqual({ "test_selector": "value" });
        expect(processed[1].id).toBe("d2");
    });
});

// --- New Test Suite for File System Operations ---
describe('File System Operations', () => {
    const tempFilePath = './test_sources.json';
    const mockConfig = {
        source_definitions: [{
            name: "Test_Catalog",
            datasets: [
                { id: "d1", search_term: "s1", imported: false },
                { id: "d2", search_term: "s2", imported: false },
            ]
        }]
    };

    beforeEach(async () => {
        // Create a temporary file before each test in this block
        await fs.writeFile(tempFilePath, JSON.stringify(mockConfig, null, 4));
    });

    afterEach(async () => {
        // Clean up the temporary file after each test
        await fs.unlink(tempFilePath);
    });

    it('should update the correct dataset in the JSON file with the new URL', async () => {
        const newUrl = "http://new-api.url/data.geojson";
        const targetId = "d2";

        await saveUrlToJson(tempFilePath, targetId, newUrl);

        const updatedContent = await fs.readFile(tempFilePath, 'utf-8');
        const updatedConfig = JSON.parse(updatedContent);

        const updatedDataset = updatedConfig.source_definitions[0].datasets.find(d => d.id === targetId);
        
        expect(updatedDataset.scraped_url).toBe(newUrl);
        expect(updatedDataset.imported).toBe(true);
    });
});


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
        // Add a retry loop to make navigation more resilient to network errors.
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
});

// --- THIS IS THE UPDATED TEST SUITE ---
describe.only('Complete Scraper Integration', () => {
    let browser;
    const tempFilePath = './integration_test_sources.json';
    const damsDataset = { id: "nys_dams", purpose: "infrastructure", search_term: "Dams", imported: false };
    const mockConfig = {
        source_definitions: [{
            name: "NYS_GIS_Water_Catalog",
            state: "NY",
            origin_url: "https://data.gis.ny.gov/search?categories=%2Fcategories%2Fwater",
            selectors: mockSource.selectors, // Use selectors from the mock
            datasets: [damsDataset]
        }]
    };
    
    beforeAll(async () => {
        browser = await puppeteer.launch({ headless: "new" });
        // Create the temporary file for the integration test
        await fs.writeFile(tempFilePath, JSON.stringify(mockConfig, null, 4));
    });

    afterAll(async () => {
        await browser.close();
        // Clean up the temporary file
        await fs.unlink(tempFilePath);
    });

    it('should find, scrape, and save the URL for a dataset', async () => {
        // --- 1. CONFIG PROCESSING ---
        const configContent = await fs.readFile(tempFilePath, 'utf-8');
        const config = JSON.parse(configContent);
        const sources = processSourceDefinitions(config);
        const sourceToScrape = sources[0];
        
        expect(sourceToScrape.id).toBe(damsDataset.id);

        const testPage = await browser.newPage();

        // --- 2. STAGE 1: Find Details URL ---
        const detailsUrl = await findAndScrapeUrl(testPage, sourceToScrape);
        expect(detailsUrl).toContain('https://data.gis.ny.gov/maps/');

        // --- 3. STAGE 2: Scrape API URL ---
        const apiUrl = await scrapeApiUrlFromDetailsPage(testPage, detailsUrl, sourceToScrape);
        expect(apiUrl).not.toBeNull();
        expect(apiUrl).toContain('/FeatureServer');
        expect(apiUrl).toContain('geojson');

        // --- 4. STAGE 3: Save Result to JSON ---
        await saveUrlToJson(tempFilePath, sourceToScrape.id, apiUrl);

        // --- 5. VERIFICATION ---
        const updatedContent = await fs.readFile(tempFilePath, 'utf-8');
        const updatedConfig = JSON.parse(updatedContent);
        const updatedDataset = updatedConfig.source_definitions[0].datasets.find(d => d.id === sourceToScrape.id);

        expect(updatedDataset.scraped_url).toBe(apiUrl);
        expect(updatedDataset.imported).toBe(true);

        await testPage.close();
    });
});