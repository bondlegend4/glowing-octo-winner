import puppeteer from 'puppeteer';
import {
    findCardOnPage,
    loadAllResults,
    extractUrlFromCard,
    findAndScrapeUrl,
    scrapeApiUrlFromDetailsPage // Import the new function
} from '../src/agroforestry/scraping/gis_scraper.js';

jest.setTimeout(90000); // Increased global timeout for multi-stage tests

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
            const getVisibleCardTitles = () => {
                return catalogHandle.evaluate(el => {
                    const cards = el.shadowRoot?.querySelector('arcgis-hub-gallery')
                                      ?.shadowRoot?.querySelector('arcgis-hub-gallery-layout-list')
                                      ?.shadowRoot?.querySelectorAll('arcgis-hub-entity-card');
                    // Return the data-test attribute which is the title
                    return Array.from(cards).map(card => card.getAttribute('data-test'));
                });
            };
            
            const initialTitles = await getVisibleCardTitles();
            expect(initialTitles.length).toBeGreaterThan(0);
        });
    });

    describe('loadAllResults', () => {
        it('should load new results onto the page', async () => {
            // 1. Get all card titles on the first page.
            const getVisibleCardTitles = () => {
                return catalogHandle.evaluate(el => {
                    const cards = el.shadowRoot?.querySelector('arcgis-hub-gallery')
                                      ?.shadowRoot?.querySelector('arcgis-hub-gallery-layout-list')
                                      ?.shadowRoot?.querySelectorAll('arcgis-hub-entity-card');
                    // Return the data-test attribute which is the title
                    return Array.from(cards).map(card => card.getAttribute('data-test'));
                });
            };
            
            const initialTitles = await getVisibleCardTitles();
            expect(initialTitles.length).toBeGreaterThan(0);

            // 2. Run the function to click "More results"
            await loadAllResults(page, catalogHandle);

            // 3. Get all card titles again.
            const finalTitles = await getVisibleCardTitles();

            // 4. Assert that there are more cards now than before.
            expect(finalTitles.length).toBeGreaterThan(initialTitles.length);

            // 5. Confirm at least one new card exists that wasn't there before.
            const newCard = finalTitles.find(title => !initialTitles.includes(title));
            expect(newCard).toBeDefined();
        });
    });

    describe('extractUrlFromCard', () => {
        it('should extract a valid URL from a given card handle', async () => {
            // Get a handle for a known card on the first page
            const cardHandle = await findCardOnPage(catalogHandle, 'Sediment Caps');
            expect(cardHandle).not.toBeNull();

            // Test the extraction function
            const url = await extractUrlFromCard(cardHandle);
            expect(typeof url).toBe('string');
            expect(url).toContain('https://data.gis.ny.gov/maps/');
        });
    });

    // --- New Test Suite for Stage 2 function ---
    describe('scrapeApiUrlFromDetailsPageApiResource', () => {
        it('should redirect and extract the API link from the /about page', async () => {
            const damsDetailsUrl = 'https://data.gis.ny.gov/maps/71781adc8f9d4c70b35f5c1ac3168833';
            const testPage = await browser.newPage();
            
            // This function call will now be tested
            const apiUrl = await scrapeApiUrlFromDetailsPage(testPage, damsDetailsUrl);

            // Assert that the final API URL was found
            expect(apiUrl).not.toBeNull();
            expect(apiUrl).toContain('/FeatureServer/');
            expect(apiUrl).toContain('=geojson');
        });
    });

    describe('scrapeApiUrlFromDetailsPageDataSource', () => {
        it('should redirect and extract the API link from the /about page', async () => {
            const damsDetailsUrl = 'https://data.gis.ny.gov/maps/eaa83cbb75c045db8290109b3a94c847';
            const testPage = await browser.newPage();
            
            // This function call will now be tested
            const apiUrl = await scrapeApiUrlFromDetailsPage(testPage, damsDetailsUrl);

            // Assert that the final API URL was found
            expect(apiUrl).not.toBeNull();
            expect(apiUrl).toContain('/FeatureServer');
        });
    });

    // --- End-to-End Integration Test ---
    describe('findAndScrapeUrl (End-to-End)', () => {
        it('should complete both stages and return the final API URL for "Dams"', async () => {
            const testPage = await browser.newPage();
            const detailsUrl = await findAndScrapeUrl(testPage, 'Dams');
            expect(detailsUrl).toBe('https://data.gis.ny.gov/maps/5a7d83359cc842e08711215408f5b55c');
            
            const apiUrl = await scrapeApiUrlFromDetailsPage(testPage, detailsUrl);
            expect(apiUrl).not.toBeNull();
            expect(apiUrl).toContain('/FeatureServer');
            expect(apiUrl).toContain('=geojson');
        });

        it('should complete both stages and return the final API URL for "Unconsolidated Aquifers 250K Upstate NY"', async () => {
            const testPage = await browser.newPage();
            const detailsUrl = await findAndScrapeUrl(testPage, 'Unconsolidated Aquifers 250K _ Upstate NY');
            expect(detailsUrl).toBe('https://data.gis.ny.gov/maps/eaa83cbb75c045db8290109b3a94c847');
            
            const apiUrl = await scrapeApiUrlFromDetailsPage(testPage, detailsUrl);
            expect(apiUrl).not.toBeNull();
            expect(apiUrl).toContain('/FeatureServer');
        });
    });
});