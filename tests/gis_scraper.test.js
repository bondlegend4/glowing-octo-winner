import puppeteer from 'puppeteer';
import {
    findCardOnPage,
    loadAllResults,
    extractUrlFromCard,
    findAndScrapeUrl
} from '../src/agroforestry/scraping/gis_scraper.js';

jest.setTimeout(60000); // Increased timeout for multiple tests

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
        await page.goto('https://data.gis.ny.gov/search?categories=%2Fcategories%2Fwater', {
            waitUntil: 'networkidle0',
            timeout: 60000
        });
        catalogHandle = await page.waitForSelector('arcgis-hub-catalog');
    });

    afterEach(async () => {
        await page.close();
    });

    // --- Test Suite for findCardOnPage ---
    describe('findCardOnPage', () => {
        it('should find a card that exists on the first page', async () => {
            // "Wastewater Facility" is typically on the first page
            const cardHandle = await findCardOnPage(catalogHandle, 'Sediment Caps');
            expect(cardHandle).not.toBeNull();
            expect(cardHandle.asElement()).toBeTruthy();
        });

        it('should return null for a card not on the first page', async () => {
            const cardHandle = await findCardOnPage(catalogHandle, 'Dams');
            expect(cardHandle).toBeNull();
        });
    });

    // --- Test Suite for loadAllResults ---
    describe('loadAllResults', () => {
        it('should load more results so that a later item becomes visible', async () => {
            // 1. Confirm "Dams" is NOT visible initially
            let damsCard = await findCardOnPage(catalogHandle, 'Dams');
            expect(damsCard).toBeNull();

            // 2. Run the function to click "More results"
            await loadAllResults(page, catalogHandle);

            // 3. Confirm "Dams" IS visible now
            damsCard = await findCardOnPage(catalogHandle, 'Dams');
            expect(damsCard).not.toBeNull();
            expect(damsCard.asElement()).toBeTruthy();
        });
    });

    // --- Test Suite for extractUrlFromCard ---
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

    // --- Integration Test for the Main Function ---
    describe('findAndScrapeUrl', () => {
        it('should successfully find and return the URL for "Dams"', async () => {
            // This test uses a new page to ensure a clean run of the whole process
            const testPage = await browser.newPage();
            const url = await findAndScrapeUrl(testPage, 'Dams');
            expect(url).toBe('https://data.gis.ny.gov/maps/5a7d83359cc842e08711215408f5b55c');
            await testPage.close();
        });
    });
});