import os
import json
import unittest
from unittest.mock import patch, MagicMock, mock_open
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import requests # <--- FIX: Added the missing import

# Import the functions from your script that you want to test
from src.agroforestry.data.importer import (
    get_db_engine,
    load_source_manifest,
    import_from_geojson_api,
    load_gdf_to_postgis,
    main,
)

class TestImporter(unittest.TestCase):
    """Test suite for the data importer script."""

    def setUp(self):
        """Set up mock data and objects for tests."""
        self.sample_gdf = gpd.GeoDataFrame(
            {'city': ['Buenos Aires', 'Brasilia', 'Santiago']},
            geometry=[Point(-58, -34), Point(-47, -15), Point(-70, -33)],
            crs="EPSG:4326"
        )

    @patch('src.agroforestry.data.importer.create_engine')
    @patch.dict(os.environ, {
        'DB_USER': 'testuser',
        'DB_PASS': 'testpass',
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'testdb'
    })
    def test_get_db_engine_success(self, mock_create_engine):
        """Test that the database engine is created successfully with env vars."""
        get_db_engine()
        expected_url = "postgresql://testuser:testpass@localhost:5432/testdb"
        mock_create_engine.assert_called_once_with(expected_url)

    # FIX: This test is now more specific and works with the corrected importer
    @patch.dict(os.environ, {}, clear=True)
    def test_get_db_engine_failure(self):
        """Test that get_db_engine raises a KeyError if env vars are missing."""
        with self.assertRaises(KeyError):
            get_db_engine()
            
    def test_load_source_manifest_success(self):
        """Test successful loading and parsing of the manifest file."""
        mock_json_content = """
        {
            "source_definitions": [{
                "categories": [{
                    "datasets": [
                        {"id": "test-data", "imported": true, "scraped_url": "http://example.com/data?f=geojson"},
                        {"id": "non-geojson", "imported": true, "scraped_url": "http://example.com/data?f=shapefile"},
                        {"id": "not-imported", "imported": false, "scraped_url": "http://example.com/data2?f=geojson"}
                    ]
                }]
            }]
        }
        """
        m = mock_open(read_data=mock_json_content)
        with patch('builtins.open', m):
            sources = load_source_manifest("dummy/path.json")

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]['name'], 'test-data')
        self.assertEqual(sources[0]['target_table'], 'test_data')

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_load_source_manifest_file_not_found(self, mock_open):
        """Test manifest loading when the file does not exist."""
        sources = load_source_manifest("nonexistent/path.json")
        self.assertEqual(sources, [])

    @patch('builtins.open', mock_open(read_data="this is not json"))
    def test_load_source_manifest_malformed_json(self):
        """Test manifest loading with a malformed JSON file."""
        sources = load_source_manifest("bad/json.json")
        self.assertEqual(sources, [])

    @patch('src.agroforestry.data.importer.requests.get')
    @patch('src.agroforestry.data.importer.gpd.read_file')
    def test_import_from_geojson_api_success(self, mock_read_file, mock_requests_get):
        """Test successful download and parsing of a GeoJSON API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"type": "FeatureCollection", "features": []}'
        mock_requests_get.return_value = mock_response
        mock_read_file.return_value = self.sample_gdf

        gdf = import_from_geojson_api("http://example.com/api", "test_table")

        self.assertIsNotNone(gdf)
        mock_requests_get.assert_called_once_with("http://example.com/api", timeout=60)
        mock_read_file.assert_called_once_with(mock_response.text)

    @patch('src.agroforestry.data.importer.requests.get')
    def test_import_from_geojson_api_request_fails(self, mock_requests_get):
        """Test GeoJSON API handler when the HTTP request fails."""
        mock_requests_get.side_effect = requests.exceptions.RequestException("Connection error")
        
        gdf = import_from_geojson_api("http://example.com/api", "test_table")
        self.assertIsNone(gdf)

    @patch('geopandas.GeoDataFrame.to_postgis')
    @patch('geopandas.GeoDataFrame.to_crs')
    def test_load_gdf_to_postgis(self, mock_to_crs, mock_to_postgis):
        """Test that the GeoDataFrame is correctly written to PostGIS."""
        mock_engine = MagicMock()
        mock_to_crs.return_value = self.sample_gdf

        load_gdf_to_postgis(self.sample_gdf, 'my_table', mock_engine)
        
        mock_to_crs.assert_called_once_with(epsg=4326)
        mock_to_postgis.assert_called_once_with(
            name='my_table', con=mock_engine, if_exists='replace', index=True
        )

    @patch('src.agroforestry.data.importer.get_db_engine')
    @patch('src.agroforestry.data.importer.load_source_manifest')
    @patch('src.agroforestry.data.importer.import_from_geojson_api')
    @patch('src.agroforestry.data.importer.load_gdf_to_postgis')
    def test_main_workflow(self, mock_load_db, mock_import_api, mock_load_manifest, mock_get_engine):
        """Test the main function's orchestration logic."""
        mock_get_engine.return_value = MagicMock()
        mock_load_manifest.return_value = [{'name': 'test-source', 'url': 'http://test.com', 'target_table': 'test_table'}]
        mock_import_api.return_value = self.sample_gdf

        main()

        mock_load_manifest.assert_called_once_with('sources.json')
        mock_get_engine.assert_called_once()
        mock_import_api.assert_called_once_with('http://test.com', 'test_table')
        mock_load_db.assert_called_once_with(self.sample_gdf, 'test_table', mock_get_engine.return_value)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)