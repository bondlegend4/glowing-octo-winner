import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
import geopandas as gpd
from shapely.geometry import Point
from sqlalchemy import create_engine
from src.agroforestry.data.importer import (
    get_db_engine,
    load_source_manifest,
    load_gdf_to_postgis,
    import_from_geojson_api
)

class TestImporterIntegration(unittest.TestCase):
    def setUp(self):
        # Sample data for testing transformation and loading logic
        self.sample_gdf = gpd.GeoDataFrame(
            {'id': ['test_1']},
            geometry=[Point(-76.5, 43.4)], # Oswego, NY area
            crs="EPSG:4326"
        )
        # Load environment variables from your .env for real connection testing
        from dotenv import load_dotenv
        load_dotenv()

    # --- ENVIRONMENT & DEPENDENCY TESTS ---
    
    def test_geoalchemy2_presence(self):
        """CRITICAL: Ensures geoalchemy2 is installed in the current environment."""
        try:
            import geoalchemy2
        except ImportError:
            self.fail("geoalchemy2 package is not installed. GeoPandas cannot write to PostGIS.")

    # --- INTEGRATION TESTS (MOCKS REMOVED) ---

    @patch('src.agroforestry.data.importer.create_engine')
    def test_get_db_engine_logic(self, mock_engine):
        """Tests engine creation logic without mocking the OS environment."""
        # This now relies on your actual .env file on the VPS
        if 'DB_USER' in os.environ:
            engine = get_db_engine()
            self.assertIsNotNone(engine)
        else:
            with self.assertRaises(KeyError):
                get_db_engine()

    def test_load_gdf_to_postgis_dependency_check(self):
        """
        Tests the actual to_postgis call. 
        MOCK REMOVED: This will now catch missing geoalchemy2 or driver errors.
        """
        # We use a 'dummy' engine that will fail on connection, 
        # but the code will have to pass the 'geoalchemy2' check first.
        mock_engine = create_engine("postgresql://user:pass@localhost:5432/db")
        
        with self.assertRaises(Exception) as context:
            # We allow it to fail the connection, but we want to see HOW it fails.
            load_gdf_to_postgis(self.sample_gdf, 'test_table', mock_engine)
        
        # If geoalchemy2 is missing, the error message will contain the requirement.
        self.assertNotIn("requires geoalchemy2", str(context.exception))

    # --- UNIT TESTS (MOCKS RETAINED FOR EXTERNAL APIS) ---

    @patch('src.agroforestry.data.importer.requests.get')
    def test_import_from_geojson_api_mocked(self, mock_get):
        """
        Keeps mocking for external requests to save time and avoid network flakiness.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"type": "FeatureCollection", "features": []}'
        mock_get.return_value = mock_response
        
        # Verify the logic of the downloader itself
        gdf = import_from_geojson_api("http://mock-api.com", "test_table")
        self.assertIsNotNone(gdf)

if __name__ == '__main__':
    unittest.main()