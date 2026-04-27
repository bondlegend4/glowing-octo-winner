import os
import json
import logging
import requests
import geopandas as gpd
from sqlalchemy import create_engine, inspect # Added inspect
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_db_engine():
    try:
        db_user, db_pass = os.environ['DB_USER'], os.environ['DB_PASS']
        db_host, db_port = os.environ['DB_HOST'], os.environ['DB_PORT']
        db_name = os.environ['DB_NAME']
        connection_str = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        return create_engine(connection_str)
    except KeyError as e:
        logging.error(f"FATAL: Environment variable not set: {e}")
        raise

def prepare_arcgis_url(url):
    """
    Ensures ArcGIS FeatureServer URLs are properly formatted for GeoJSON queries.
    """
    url = url.strip()
    if "FeatureServer" in url and "query" not in url:
        # If it doesn't end in a layer index (e.g., /0), we default to 0
        if url.endswith("FeatureServer") or url.endswith("FeatureServer/"):
            base = url.rstrip('/')
            url = f"{base}/0/query?where=1%3D1&outFields=*&f=geojson"
        else:
            # If it already has a layer index, just append the query
            url = f"{url.rstrip('/')}/query?where=1%3D1&outFields=*&f=geojson"
    return url

def load_source_manifest(filepath):
    try:
        with open(filepath, 'r') as f:
            manifest = json.load(f)
        sources = []
        for definition in manifest.get('source_definitions', []):
            for category in definition.get('categories', []):
                for dataset in category.get('datasets', []):
                    if dataset.get('imported'):
                        sources.append({
                            'name': dataset.get('id', 'unknown'),
                            'url': prepare_arcgis_url(dataset.get('scraped_url', '')),
                            'target_table': dataset.get('id', 'unknown').lower().replace('-', '_')
                        })
        return sources
    except Exception as e:
        logging.error(f"Error loading manifest: {e}")
        return []

def import_from_geojson_api(url, target_table):
    logging.info(f"Fetching data for {target_table}...")
    try:
        # ArcGIS can be sensitive to headers
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        return gpd.read_file(response.text)
    except Exception as e:
        logging.error(f"Failed to fetch {target_table}: {e}")
        return None

def load_gdf_to_postgis(gdf, table_name, engine):
    if gdf is None or gdf.empty: return
    
    # SAFEGUARD: Check if table exists before writing
    if inspect(engine).has_table(table_name):
        logging.info(f"Table '{table_name}' already exists. Skipping.")
        return

    try:
        logging.info(f"Writing {len(gdf)} records to {table_name}...")
        gdf.to_crs(epsg=4326).to_postgis(name=table_name, con=engine, if_exists='fail', index=True)
    except Exception as e:
        logging.error(f"Database write error: {e}")
        raise # Re-raise for test suite

def main():
    load_dotenv()
    sources = load_source_manifest(os.path.join('data', 'sources.json'))
    if not sources: return
    
    engine = get_db_engine()
    for source in sources:
        gdf = import_from_geojson_api(source['url'], source['target_table'])
        load_gdf_to_postgis(gdf, source['target_table'], engine)

if __name__ == "__main__":
    main()