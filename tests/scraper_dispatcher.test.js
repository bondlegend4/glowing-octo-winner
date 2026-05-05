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

    it('should correctly route "arcgis_rest" types to the GIS engine', async () => {
        const gisSpy = jest.fn();
        // Mocks the engine call within the dispatcher
        await runDispatcher(mockManifest, { gisEngine: gisSpy });
        expect(gisSpy).toHaveBeenCalled();
    });

    it('should correctly route "web_dom_land" types to the Land engine', async () => {
        const landSpy = jest.fn();
        await runDispatcher(mockManifest, { landEngine: landSpy });
        expect(landSpy).toHaveBeenCalled();
    });
});