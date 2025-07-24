# src/data_importer.py
import yaml
import requests
import geopandas as gpd
import fiona
import os
import tempfile
import zipfile
from sqlalchemy import create_engine
from config import get_db_connection_string # Assuming you have this helper

def _import_gdb_from_zip(url, layer_name, purpose):
    """Downloads a zipped GDB, extracts it, and reads a specific layer."""
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, "data.zip")
        print(f"Downloading GDB zip from {url}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print("Extracting GDB...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            
        # Find the .gdb directory
        gdb_path = None
        for root, dirs, files in os.walk(temp_dir):
            for d in dirs:
                if d.endswith(".gdb"):
                    gdb_path = os.path.join(root, d)
                    break
            if gdb_path:
                break

        if not gdb_path:
            raise FileNotFoundError("Could not find .gdb directory in the extracted archive.")

        print(f"Reading layer '{layer_name}' from {gdb_path}")
        gdf = gpd.read_file(gdb_path, layer=layer_name)
        return gdf, f"{purpose}_{layer_name}".lower()


def _import_gpkg_from_url(url, purpose):
    """Downloads a GPKG file and reads it."""
    print(f"Reading GPKG from {url}...")
    gdf = gpd.read_file(url)
    return gdf, f"{purpose}".lower()


def _import_from_rest_api(url, purpose):
    """Fetches data from an ArcGIS REST API."""
    print(f"Fetching from REST API: {url}...")
    query_url = f"{url}/query?where=1%3D1&outFields=*&f=geojson"
    gdf = gpd.read_file(query_url)
    return gdf, f"{purpose}".lower()


def run_importer():
    """
    Main function to run the data importation process based on the config file.
    """
    with open("data_config.yaml", 'r') as f:
        config = yaml.safe_load(f)

    engine = create_engine(get_db_connection_string())

    for source in config['sources']:
        if source.get('imported', False):
            print(f"Skipping already imported source: {source['id']}")
            continue

        try:
            gdf = None
            table_name = None
            source_type = source['type']
            purpose = source['purpose']
            url = source['url']

            if source_type == 'gdb_zip':
                gdf, table_name = _import_gdb_from_zip(url, source['layer_name'], purpose)
            elif source_type == 'gpkg':
                gdf, table_name = _import_gpkg_from_url(url, purpose)
            elif source_type == 'rest_api':
                gdf, table_name = _import_from_rest_api(url, purpose)
            else:
                print(f"Unknown source type: {source_type}")
                continue

            if gdf is not None:
                print(f"Loading data into PostGIS table: {table_name}...")
                # Standardize column names (lowercase, no special chars)
                gdf.columns = gdf.columns.str.lower().str.replace(' ', '_').str.replace('[^a-zA-Z0-9_]', '', regex=True)
                gdf.to_postgis(table_name, engine, if_exists='replace', index=False)
                print(f"Successfully loaded {source['id']}.")
                # Here you would update the YAML to mark as imported, or handle it in a separate tracking db

        except Exception as e:
            print(f"Failed to import {source['id']}. Reason: {e}")

if __name__ == "__main__":
    run_importer()