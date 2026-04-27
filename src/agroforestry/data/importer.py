import os
import json
import logging
import requests
import geopandas as gpd
from sqlalchemy import create_engine
from dotenv import load_dotenv  # Added for .env support

# 1. Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 2. Database Connection Function
def get_db_engine():
    """
    Creates and returns a SQLAlchemy engine using database credentials
    from environment variables.
    """
    try:
        # load_dotenv() is called in main() to populate these
        db_user = os.environ['DB_USER']
        db_pass = os.environ['DB_PASS']
        db_host = os.environ['DB_HOST']
        db_port = os.environ['DB_PORT']
        db_name = os.environ['DB_NAME']
        
        connection_str = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        engine = create_engine(connection_str)
        logging.info("Successfully created database engine.")
        return engine
    except KeyError as e:
        logging.error(f"FATAL: Environment variable not set: {e}. Please check your .env file.")
        raise
    except Exception as e:
        logging.error(f"Failed to create database engine: {e}")
        raise

# 3. Manifest Loading Function
def load_source_manifest(filepath):
    """
    Loads and parses the source manifest JSON file.
    """
    logging.info(f"Loading source manifest from: {filepath}")
    try:
        with open(filepath, 'r') as f:
            manifest = json.load(f)
        
        sources_to_import = []
        for definition in manifest.get('source_definitions', []):
            # Handle both nested 'categories' and direct 'datasets' structures
            dataset_list = []
            if 'categories' in definition:
                for category in definition.get('categories', []):
                    dataset_list.extend(category.get('datasets', []))
            else:
                dataset_list = definition.get('datasets', [])

            for dataset in dataset_list:
                if dataset.get('imported') and 'scraped_url' in dataset:
                    # We only want GeoJSON for this phase
                    if 'f=geojson' in dataset['scraped_url'].lower() or 'geojson' in dataset['scraped_url'].lower():
                        source_obj = {
                            'name': dataset.get('id', 'unknown'),
                            'url': dataset['scraped_url'],
                            'target_table': dataset.get('id', 'unknown').lower().replace('-', '_')
                        }
                        sources_to_import.append(source_obj)
        
        logging.info(f"Successfully parsed {len(sources_to_import)} data sources.")
        return sources_to_import
    except FileNotFoundError:
        logging.error(f"Manifest file not found at: {filepath}")
        return []
    except Exception as e:
        logging.error(f"An unexpected error occurred loading manifest: {e}")
        return []

# 4. GeoJSON API Handler
def import_from_geojson_api(url, target_table):
    logging.info(f"Fetching GeoJSON from: {url}")
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        gdf = gpd.read_file(response.text)
        return gdf
    except Exception as e:
        logging.error(f"Failed to download/parse data for '{target_table}': {e}")
        return None

# 5. Database Loading Function
def load_gdf_to_postgis(gdf, table_name, engine):
    if gdf is None or gdf.empty:
        return
    try:
        logging.info(f"Writing {len(gdf)} records to table '{table_name}'...")
        # Standardize to WGS84 for web mapping
        gdf_proj = gdf.to_crs(epsg=4326)
        gdf_proj.to_postgis(name=table_name, con=engine, if_exists='replace', index=True)
        logging.info(f"Successfully wrote data to '{table_name}'.")
    except Exception as e:
        logging.error(f"Failed to write to database for '{table_name}': {e}")

# 6. Main Execution Workflow
def main():
    logging.info("Starting importer service workflow...")
    
    # Load .env file from the current directory (project root)
    load_dotenv()
    
    # Updated path to reflect your actual directory structure
    # This looks for sources.json inside the 'data' folder from where you run the script
    manifest_path = os.path.join('data', 'sources.json') 
    
    sources = load_source_manifest(manifest_path)
    
    if not sources:
        logging.warning("No data sources to import. Exiting.")
        return

    try:
        db_engine = get_db_engine()
    except Exception:
        # get_db_engine already logs the fatal error
        return
        
    for source in sources:
        logging.info(f"--- Processing: {source['name']} ---")
        gdf = import_from_geojson_api(source['url'], source['target_table'])
        
        if gdf is not None:
            load_gdf_to_postgis(gdf, source['target_table'], db_engine)
        else:
            logging.warning(f"Skipping database load for '{source['name']}' due to download failure.")

    logging.info("Importer service workflow finished.")

if __name__ == "__main__":
    main()