import { jest, describe, it, expect, beforeAll, afterAll, beforeEach, afterEach } from '@jest/globals';
import puppeteer from 'puppeteer';
import fs from 'fs/promises';
import {
    saveUrlToJson,
    processSourceDefinitions,
    findCardOnPage,
    loadAllResults,
    extractUrlFromCard,
    findAndScrapeUrl,
    scrapeApiUrlFromDetailsPage
} from '../src/agroforestry/scraping/gis_scraper.js';

// A mock source configuration object to be used in tests
const mockBaseConfig = {
    base_search_url: "https://data.gis.ny.gov/search?categories=%2Fcategories%2F",
    state: "NY",
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

// --- Test Suite for Configuration Processing ---
describe.only('processSourceDefinitions', () => {
    it('should correctly merge base config and definitions into a flat list', () => {
        // Updated mockConfig to match the new structure
        const mockConfig = {
            base_config: {
                base_search_url: "http://test.com/",
                state: "NY",
                selectors: { "test": "selector" }
            },
            source_definitions: [{
                name: "Test_Catalog",
                categories: [
                    { category: "cat1", datasets: [{ id: "d1", search_term: "s1" }] },
                    { category: "cat2", datasets: [{ id: "d2", search_term: "s2" }] }
                ]
            }]
        };

        const processed = processSourceDefinitions(mockConfig);
        
        expect(processed).toHaveLength(2);
        expect(processed[0].id).toBe("d1");
        expect(processed[0].state).toBe("NY");
        expect(processed[0].name).toBe("Test_Catalog");
        expect(processed[0].origin_url).toBe("http://test.com/cat1");
        expect(processed[1].origin_url).toBe("http://test.com/cat2");
    });
});


// --- Test Suite for File System Operations ---
describe.only('saveUrlToJson', () => {
    const tempFilePath = './test_sources.json';
    // Updated mockConfig to match the new structure
    const mockConfig = {
        source_definitions: [{
            name: "Test_Catalog",
            categories: [{
                category: "cat1",
                datasets: [
                    { id: "d1", search_term: "s1", imported: false }
                ]
            }]
        }]
    };

    beforeEach(async () => await fs.writeFile(tempFilePath, JSON.stringify(mockConfig)));
    afterEach(async () => await fs.unlink(tempFilePath));

    it('should update the correct dataset with the new URL and imported flag', async () => {
        await saveUrlToJson(tempFilePath, "d1", "http://new.url");
        const updatedConfig = JSON.parse(await fs.readFile(tempFilePath, 'utf-8'));
        const dataset = updatedConfig.source_definitions[0].categories[0].datasets[0];
        expect(dataset.scraped_url).toBe("http://new.url");
        expect(dataset.imported).toBe(true);
    });
});


describe('Individual Scraper Functions', () => {
    let browser;
    let page;
    let catalogHandle;

    const source = processSourceDefinitions({ // Create a single processed source for tests
        base_config: { ...mockBaseConfig, base_search_url: 'https://data.gis.ny.gov/search?categories=%2Fcategories%2F' },
        source_definitions: [{
            name: "NYS_GIS_Water_Catalog",
            categories: [ // It should be a "categories" array
                {
                    category: "water",
                    datasets: [{ id: "nys_dams_test", search_term: "Dams", imported: false }]
                }
            ]
        }]    })[0];

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
                await page.goto(source.origin_url, {
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
            const cardHandle = await findCardOnPage(catalogHandle, { ...source, search_term: 'Sediment Caps' });
            expect(cardHandle).not.toBeNull();
        });
    });

    // --- Test Suite for loadAllResults ---
    describe('loadAllResults', () => {
        it('should load new results onto the page', async () => {
            const getCardCount = () => catalogHandle.evaluate(el => el.shadowRoot?.querySelector('arcgis-hub-gallery')?.shadowRoot?.querySelector('arcgis-hub-gallery-layout-list')?.shadowRoot?.querySelectorAll('arcgis-hub-entity-card').length);

            const initialCount = await getCardCount();
            expect(initialCount).toBeGreaterThan(0);

            // Pass the source object to the function
            await loadAllResults(page, catalogHandle, source);

            const finalCount = await getCardCount();
            expect(finalCount).toBeGreaterThan(initialCount);
        });
    });

    // --- Test Suite for extractUrlFromCard ---
    describe('extractUrlFromCard', () => {
        it('should extract a valid URL from a given card handle', async () => {
            const cardHandle = await findCardOnPage(catalogHandle, { ...source, search_term: 'Sediment Caps' });
            expect(cardHandle).not.toBeNull();

            // Pass the source object to the function
            const url = await extractUrlFromCard(cardHandle, source);
            expect(typeof url).toBe('string');
            expect(url).toContain('https://data.gis.ny.gov/maps/');
        });
    });

    // --- Test Suite for scrapeApiUrlFromDetailsPage ---
    describe('scrapeApiUrlFromDetailsPage', () => {
        it('should redirect and extract the API link from the /about page', async () => {
            const damsDetailsUrl = 'https://data.gis.ny.gov/maps/71781adc8f9d4c70b35f5c1ac3168833';
            const testPage = await browser.newPage();

            // Pass the source object to the function
            const apiUrl = await scrapeApiUrlFromDetailsPage(testPage, damsDetailsUrl, source);

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
            const apiUrl = await scrapeApiUrlFromDetailsPage(testPage, damsDetailsUrl, source);

            // Assert that the final API URL was found
            expect(apiUrl).not.toBeNull();
            expect(apiUrl).toContain('/FeatureServer');
        });
    });
});

// --- THIS IS THE UPDATED TEST SUITE ---
describe('Complete Scraper Integration', () => {
    let browser;
    const tempFilePath = './integration_test_sources.json';
    const mockConfig = {
        base_config: { // Add base_config
            base_search_url: "https://data.gis.ny.gov/search?categories=%2Fcategories%2F",
            selectors: mockBaseConfig.selectors
        },
        source_definitions: [{
            name: "NYS_GIS_Water_Catalog",
            category: "water", // Use category instead of origin_url
            categories: [ // It should be a "categories" array
            {
                category: "water",
                datasets: [{ id: "nys_dams_test", search_term: "Dams", imported: false }]
            }
        ]
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
        const sourceToScrape = processSourceDefinitions(mockConfig)[0];
        const testPage = await browser.newPage();

        expect(sourceToScrape.id).toBe(damsDataset.id);
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