import { jest, describe, it, expect } from '@jest/globals';
import { runDispatcher } from '../src/agroforestry/scraping/scraper_engine.js';

describe('Scraper Dispatcher Unit Tests', () => {
    const mockManifest = {
        configs: {
            arcgis_rest: { base_search_url: "http://gis.test" },
            web_dom_land: { base_url: "http://land.test" }
        },
        source_definitions: [
            { id: "gis_task", type: "arcgis_rest", datasets: [{ id: "d1", search_term: "test" }] },
            { id: "land_task", type: "web_dom_land", datasets: [{ id: "l1", search_term: "test" }] }
        ]
    };

    it('should correctly route "arcgis_rest" and prevent fallback side-effects', async () => {
        const gisSpy = jest.fn();
        const landSpy = jest.fn(); // Mocking both to prevent ERR_NAME_NOT_RESOLVED
        
        await runDispatcher(mockManifest, { 
            gisEngine: gisSpy, 
            landEngine: landSpy 
        });
        
        expect(gisSpy).toHaveBeenCalled();
        expect(landSpy).toHaveBeenCalled();
    });
});