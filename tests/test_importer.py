import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
import geopandas as gpd
from shapely.geometry import Point
from sqlalchemy import create_engine, text
from src.agroforestry.data.importer import (
    get_db_engine,
    load_source_manifest,
    load_gdf_to_postgis,
    import_from_geojson_api,
    get_safe_table_name
)

class TestImporterIntegration(unittest.TestCase):
    def setUp(self):
        load_dotenv('.env.production')
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
    
    @patch('requests.get')
    def test_layer_discovery(self, mock_get):
        """Verify the logic that expands a FeatureServer into multiple tables."""
        from src.agroforestry.data.importer import get_layers_from_service
        
        # Mocking a standard ArcGIS /layers response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "layers": [
                {"id": 1, "name": "Confined Aquifers"},
                {"id": 2, "name": "Unconfined Aquifers"}
            ]
        }
        
        layers = get_layers_from_service("https://fake-gis.ny.gov/FeatureServer")
        self.assertEqual(len(layers), 2)
        self.assertEqual(layers[0]['name'], "Confined Aquifers")

    def test_manifest_url_validity(self):
        """Ensure no malformed URLs exist in the source manifest."""
        path = os.path.join('data', 'sources.json')
        manifest = load_source_manifest(path)
        for definition in manifest['source_definitions']:
            for cat in definition['categories']:
                for ds in cat['datasets']:
                    url = ds.get('scraped_url', '')
                    if url:
                        self.assertTrue(url.startswith('http'))
    
    def test_database_connection_real(self):
        """Verifies actual connectivity to the dev_agro database."""
        engine = get_db_engine()
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version();")).fetchone()
                self.assertIn("PostgreSQL", result[0])
        except Exception as e:
            self.fail(f"Could not connect to development database: {e}")

    def test_live_api_fetch_real(self):
        """Tests actual network fetch and GDF creation for a small dataset."""
        # Using a reliable, small NYS dataset for integration testing
        test_url = "https://services6.arcgis.com/DZHaqZm9cxOD4CWM/arcgis/rest/services/Ecological_Regions/FeatureServer/7/query?where=1%3D1&outFields=*&f=geojson"
        gdf = import_from_geojson_api(test_url, "test_integration_table")
        
        self.assertIsNotNone(gdf)
        self.assertFalse(gdf.empty)
        self.assertEqual(gdf.crs.to_epsg(), 4326)

class TestImporterResilience(unittest.TestCase):

    def test_load_manifest_success(self):
        """Ensure the manifest loads correctly from the data directory."""
        path = os.path.join('data', 'sources.json')
        manifest = load_source_manifest(path)
        self.assertIn('source_definitions', manifest)

    @patch.dict(os.environ, {}, clear=True)
    def test_get_db_engine_missing_env(self):
        """Test that the importer fails gracefully if credentials are missing."""
        with self.assertRaises(KeyError):
            get_db_engine()

    def test_naming_safety_logic(self):
        """Verify that table names are truncated to 63 chars to avoid Postgres errors."""
        long_id = "nys_unconsolidated_aquifers"
        long_layer = "confined_unconsolidated_aquifers_upper_hudson_valley_250k"
        
        safe_name = get_safe_table_name(long_id, long_layer)
        
        self.assertLessEqual(len(safe_name), 63)
        self.assertTrue(safe_name.startswith("nys_unconsolidated"))
        # Ensure it's lowercase and uses underscores
        self.assertEqual(safe_name, safe_name.lower().replace('-', '_'))

if __name__ == '__main__':
    unittest.main()