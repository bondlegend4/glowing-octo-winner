import geopandas as gpd
from sqlalchemy import create_engine
import os
import fiona
import yaml # You'll need the PyYAML library

class DataManager:
    """
    Handles importing GIS data from various sources into local and cloud databases
    based on a YAML configuration file.
    """
    def __init__(self, config_path='data-config.yaml'):
        self.engines = self._get_db_engines()
        self.config = self._load_config(config_path)

    def _get_db_engines(self):
        # This private method remains the same as before
        engines = {}
        try:
            LOCAL_DB_USER, LOCAL_DB_PASS, LOCAL_DB_HOST, LOCAL_DB_NAME = (
                os.getenv('POSTGRES_USER'), os.getenv('POSTGRES_PASSWORD'),
                'localhost', os.getenv('POSTGRES_DB')
            )
            local_url = f"postgresql+psycopg2://{LOCAL_DB_USER}:{LOCAL_DB_PASS}@{LOCAL_DB_HOST}:5432/{LOCAL_DB_NAME}"
            engines['local'] = create_engine(local_url)
        except Exception as e:
            print(f"Could not create local engine: {e}")

        try:
            PROD_DB_USER, PROD_DB_PASS, PROD_DB_HOST, PROD_DB_NAME = (
                os.getenv('SUPABASE_USER'), os.getenv('SUPABASE_PASSWORD'),
                os.getenv('SUPABASE_HOST'), os.getenv('SUPABASE_DB')
            )
            if all([PROD_DB_USER, PROD_DB_PASS, PROD_DB_HOST]):
                prod_url = f"postgresql+psycopg2://{PROD_DB_USER}:{PROD_DB_PASS}@{PROD_DB_HOST}:5432/{PROD_DB_NAME}"
                engines['production'] = create_engine(prod_url)
        except Exception as e:
            print(f"Could not create production engine: {e}")
        return engines

    def _load_config(self, config_path):
        """Loads and validates the YAML configuration file."""
        print(f"Loading configuration from '{config_path}'...")
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"❌ ERROR: Configuration file not found at '{config_path}'.")
            return []
        except Exception as e:
            print(f"❌ ERROR: Could not parse YAML file. Error: {e}")
            return []

    def run_all_imports(self):
        """
        Iterates through the config file and imports each defined data source.
        """
        if not self.config:
            print("No data sources found in configuration. Exiting.")
            return

        print(f"Found {len(self.config)} data source(s) to process.")
        for item in self.config:
            self._import_item(item)

    def _import_item(self, item: dict):
        """Processes and imports a single item from the configuration."""
        # Get properties from the config item
        file_path_suffix = item.get('file_path')
        layer_name = item.get('layer_name')
        table_name = item.get('table_name')
        is_spatial = item.get('is_spatial', True) # Default to spatial

        # Construct full file path
        full_file_path = os.path.join("./data", file_path_suffix)

        print(f"\n===== Processing: {table_name} ({'Spatial' if is_spatial else 'Table'}) =====")
        if not os.path.exists(full_file_path):
            print(f"⚠️ WARNING: File not found at '{full_file_path}'. Skipping.")
            return

        try:
            # Read the data file
            print(f"Reading file '{os.path.basename(full_file_path)}', layer: '{layer_name}'...")
            gdf = gpd.read_file(full_file_path, layer=layer_name)

            # Standardize data
            gdf.columns = gdf.columns.str.lower().str.replace('[^a-zA-Z0-9_]', '', regex=True)
            if is_spatial and gdf.crs and gdf.crs.to_epsg() != 4326:
                print("Reprojecting to EPSG:4326...")
                gdf = gdf.to_crs(epsg=4326)

            # Upload to all databases
            for env, engine in self.engines.items():
                print(f"--- Uploading to {env.upper()} ---")
                try:
                    if is_spatial:
                        gdf.to_postgis(name=table_name, con=engine, if_exists='replace', index=True, index_label='id')
                    else:
                        gdf.to_sql(name=table_name, con=engine, if_exists='replace', index=True, index_label='id')
                    print(f"✅ Successfully imported {len(gdf)} records to '{env}'.")
                except Exception as e:
                    print(f"❌ ERROR importing to '{env}': {e}")
            print("=" * 40)
        except Exception as e:
            print(f"An unexpected error occurred processing '{table_name}': {e}")


if __name__ == '__main__':
    # The main execution is now incredibly simple.
    # Just create a DataManager and tell it to run.
    data_manager = DataManager()
    data_manager.run_all_imports()