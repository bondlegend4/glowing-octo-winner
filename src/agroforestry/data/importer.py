import os
import json
import logging
import hashlib
import requests
import geopandas as gpd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

# Enhanced logging configuration to include the function name
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AgroImporter")

def get_db_engine():
    """
    Constructs a SQLAlchemy engine. 
    Now includes a fallback to load .env.production if standard variables are missing.
    """
    # Fallback logic: If DB_USER isn't in the environment, try loading the production file
    if not os.environ.get('DB_USER'):
        load_dotenv() # Tries default .env
        if not os.environ.get('DB_USER'):
            # If still missing, try the specific production file
            load_dotenv('.env.production')
    try:
        db_user = os.environ['DB_USER']
        db_pass = os.environ['DB_PASS']
        db_host = os.environ['DB_HOST']
        db_port = os.environ['DB_PORT']
        db_name = os.environ['DB_NAME']
        connection_str = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        return create_engine(connection_str)
    except KeyError as e:
        logger.error(f"Environment variable not set: {e}")
        raise

def load_source_manifest(path):
    """Satisfies test requirements and modularizes manifest loading."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Could not load manifest at {path}: {e}")
        raise

def get_safe_table_name(base_id, layer_name=""):
    """
    Generates a PostgreSQL-safe table name. 
    Targets 50 chars to leave room for auto-generated PostGIS index names (idx_..._geometry).
    """
    clean_base = base_id.lower().replace('-', '_')
    clean_layer = layer_name.lower().replace(' ', '_').replace('-', '_')
    
    full_name = f"{clean_base}_{clean_layer}" if layer_name else clean_base
    
    # Standard PostgreSQL limit is 63, but we target 50 for index safety
    if len(full_name) <= 50:
        return full_name
        
    suffix_hash = hashlib.md5(full_name.encode()).hexdigest()[:6]
    # Truncate to 43 chars + 1 underscore + 6 hash chars = 50 total
    return f"{full_name[:43]}_{suffix_hash}"

def get_layers_from_service(base_url):
    """
    Queries the ArcGIS service metadata to find all available layers.
    """
    root_url = base_url.split('/query')[0].rstrip('/')
    metadata_url = f"{root_url}/layers?f=json"
    try:
        response = requests.get(metadata_url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get('layers', [])
    except Exception as e:
        logger.error(f"Could not discover layers for {base_url}: {e}")
    return []

def prepare_layer_url(base_url, layer_id):
    """
    Constructs a valid GeoJSON query URL for a specific layer ID.
    """
    root_url = base_url.split('/FeatureServer')[0]
    return f"{root_url}/FeatureServer/{layer_id}/query?where=1%3D1&outFields=*&f=geojson"

def import_from_geojson_api(url, target_table):
    logger.info(f"Initiating fetch for '{target_table}' from {url}...")
    logger.debug(f"Target URL: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 AgroforestryBot/1.0'}
        response = requests.get(url, headers=headers, timeout=90)
        
        # Log the status and content type for debugging
        logger.info(f"Response Status: {response.status_code} | Content-Type: {response.headers.get('Content-Type')}")

        if response.status_code != 200:
            logger.error(f"HTTP ERROR {response.status_code} for {target_table}")
            logger.error(f"Server Response Snippet: {response.text[:500]}") # Help diagnose 'Bad Request'
            return None

        # Check for empty or non-JSON responses
        if not response.text.strip().startswith('{'):
            logger.error(f"Invalid GeoJSON response for {target_table}. Expected JSON but got: {response.text[:100]}...")
            return None

        return gpd.read_file(response.text)
    except requests.exceptions.Timeout:
        logger.error(f"TIMEOUT: Server took too long to respond for {target_table}")
    except Exception as e:
        logger.error(f"FAILED to fetch {target_table}: {str(e)}")
    return None

def load_gdf_to_postgis(gdf, table_name, engine):
    if gdf is None or gdf.empty:
        logger.warning(f"No valid data to load into {table_name}.")
        return
    
    if inspect(engine).has_table(table_name):
        logger.info(f"Table '{table_name}' already exists. Skipping.")
        return

    try:
        logger.info(f"Writing {len(gdf)} features to {table_name}...")
        gdf.to_crs(epsg=4326).to_postgis(name=table_name, con=engine, if_exists='fail', index=True)
        logger.info(f"SUCCESS: {table_name} populated.")
    except Exception as e:
        logger.error(f"DATABASE WRITE ERROR for {table_name}: {e}")
        raise

def main(manifest_path=None):
    load_dotenv()
    if manifest_path is None:
        manifest_path = os.path.join('data', 'sources.json')
    
    manifest = load_source_manifest(manifest_path)
    engine = get_db_engine()
    
for definition in manifest.get('source_definitions', []):
        for category in definition.get('categories', []):
            for dataset in category.get('datasets', []):
                if not dataset.get('imported'): continue
                
                base_url = dataset.get('scraped_url', '')
                if "FeatureServer" in base_url and "/query" not in base_url:
                    layers = get_layers_from_service(base_url)
                    for layer in layers:
                        # Use the 50-char safe naming for discovered layers
                        table_name = get_safe_table_name(dataset['id'], layer['name'])
                        url = prepare_layer_url(base_url, layer['id'])
                        gdf = import_from_geojson_api(url, table_name)
                        if gdf is not None:
                            load_gdf_to_postgis(gdf, table_name, engine)
                else:
                    # UPDATED: Use get_safe_table_name here too for Specific Mode
                    table_name = get_safe_table_name(dataset['id'])
                    gdf = import_from_geojson_api(base_url, table_name)
                    load_gdf_to_postgis(gdf, table_name, engine)

if __name__ == "__main__":
    main()