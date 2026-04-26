import os
import json
import logging
import requests
import geopandas as gpd
from sqlalchemy import create_engine

# 1. Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 2. Database Connection Function (CORRECTED)
def get_db_engine():
    """
    Creates and returns a SQLAlchemy engine using database credentials
    from environment variables. Raises an error if variables are not set.
    """
    try:
        # Using os.environ[...] will raise a KeyError if the variable is not found
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
        logging.error(f"FATAL: Environment variable not set: {e}. Please configure your database credentials.")
        raise
    except Exception as e:
        logging.error(f"Failed to create database engine: {e}")
        raise

# 3. Manifest Loading Function
def load_source_manifest(filepath):
    """
    Loads and parses the source manifest JSON file with the new structure.
    """
    logging.info(f"Loading source manifest from: {filepath}")
    try:
        with open(filepath, 'r') as f:
            manifest = json.load(f)
        
        sources_to_import = []
        for definition in manifest.get('source_definitions', []):
            for category in definition.get('categories', []):
                for dataset in category.get('datasets', []):
                    if dataset.get('imported') and 'scraped_url' in dataset:
                        if 'f=geojson' in dataset['scraped_url']:
                            source_obj = {
                                'name': dataset.get('id', 'unknown'),
                                'url': dataset['scraped_url'],
                                'target_table': dataset.get('id', 'unknown').lower().replace('-', '_')
                            }
                            sources_to_import.append(source_obj)
                        else:
                            logging.warning(f"Skipping non-GeoJSON source: {dataset.get('id')}")

        logging.info(f"Successfully loaded and parsed {len(sources_to_import)} GeoJSON data sources from manifest.")
        return sources_to_import
    except FileNotFoundError:
        logging.error(f"Manifest file not found at: {filepath}")
        return []
    except json.JSONDecodeError:
        logging.error(f"Malformed JSON in manifest file: {filepath}")
        return []
    except Exception as e:
        logging.error(f"An unexpected error occurred while loading the manifest: {e}")
        return []

# 4. GeoJSON API Handler
def import_from_geojson_api(url, target_table):
    """
    Fetches data from a GeoJSON API and returns it as a GeoDataFrame.
    """
    logging.info(f"Fetching GeoJSON from: {url}")
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        gdf = gpd.read_file(response.text)
        logging.info(f"Successfully downloaded and parsed data for '{target_table}'.")
        return gdf
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download data from {url}: {e}")
        return None
    except Exception as e:
        logging.error(f"Failed to parse GeoJSON for '{target_table}': {e}")
        return None

# 5. Database Loading Function
def load_gdf_to_postgis(gdf, table_name, engine):
    """
    Loads a GeoDataFrame into a PostGIS database.
    """
    if gdf.empty:
        logging.warning(f"GeoDataFrame for '{table_name}' is empty. Skipping database load.")
        return

    try:
        logging.info(f"Writing {len(gdf)} records to table '{table_name}'...")
        gdf_proj = gdf.to_crs(epsg=4326)
        gdf_proj.to_postgis(
            name=table_name,
            con=engine,
            if_exists='replace',
            index=True
        )
        logging.info(f"Successfully wrote data to '{table_name}'.")
    except Exception as e:
        logging.error(f"Failed to write to database for table '{table_name}': {e}")

# 6. Main Execution Workflow
def main():
    """
    Main function to orchestrate the ETL pipeline.
    """
    logging.info("Starting importer service workflow...")
    
    manifest_path = 'sources.json'
    sources = load_source_manifest(manifest_path)
    
    if not sources:
        logging.warning("No data sources to import. Exiting.")
        return

    try:
        db_engine = get_db_engine()
    except Exception:
        logging.error("Could not connect to the database. Aborting.")
        return
        
    for source in sources:
        logging.info(f"--- Processing source: {source['name']} ---")
        try:
            gdf = import_from_geojson_api(source['url'], source['target_table'])
            
            if gdf is not None:
                load_gdf_to_postgis(gdf, source['target_table'], db_engine)
            else:
                logging.warning(f"Skipping database load for '{source['name']}' due to download/parse failure.")

        except Exception as e:
            logging.error(f"An unexpected error occurred while processing '{source['name']}'. Error: {e}")

    logging.info("Importer service workflow finished.")

if __name__ == "__main__":
    main()