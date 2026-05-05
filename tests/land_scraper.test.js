import { describe, it, expect, beforeAll, afterAll } from '@jest/globals';
import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import { handleLandScrape } from '../src/agroforestry/scraping/scraper_engine.js';

puppeteer.use(StealthPlugin());

describe('Land.com Plugin Integration', () => {
    let browser;
    const mockConfig = {
        base_url: "https://www.land.com/New-York/all-land/for-sale/",
        selectors: {
            listing_container: "div[data-qa-placard]",
            property_link: "a[href*='/property/']",
            address_selector: "p[data-qa='placard-address']"
        }
    };

    beforeAll(async () => {
        browser = await puppeteer.launch({ headless: "new", args: ['--no-sandbox'] });
    });

    afterAll(async () => {
        await browser.close();
    });

    it('should bypass bot detection and find the "Land for Sale" H1', async () => {
        const page = await browser.newPage();
        await page.goto(mockConfig.base_url, { waitUntil: 'networkidle2' });
        const h1Text = await page.$eval('h1', el => el.textContent);
        expect(h1Text).toContain('Land for Sale');
        await page.close();
    });

    it('should extract valid property links using stable data-attributes', async () => {
        const page = await browser.newPage();
        const results = await handleLandScrape(page, { id: 'test' }, mockConfig);
        
        expect(results.listings.length).toBeGreaterThan(0);
        expect(results.listings[0].url).toContain('land.com/property/');
        await page.close();
    });
});