import geopandas as gpd
from sqlalchemy import create_engine
import os
import yaml
import requests
from tqdm import tqdm

class DataManager:
    """
    Imports GIS data from local files or ArcGIS REST services into databases,
    driven by a YAML configuration file and featuring a progress bar.
    """
    def __init__(self, config_path='data_config.yaml'):
        self.engines = self._get_db_engines()
        self.config = self._load_config(config_path)

    def _get_db_engines(self):
        # This private method remains the same
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
        # This private method remains the same
        print(f"Loading configuration from '{config_path}'...")
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"❌ ERROR: Configuration file not found at '{config_path}'.")
            return []
        return []

    def run_all_imports(self):
        """Iterates through the config file and imports each defined data source."""
        if not self.config:
            print("No data sources found in configuration. Exiting.")
            return

        print(f"Found {len(self.config)} data source(s) to process.")
        for item in self.config:
            source_type = item.get('source_type', 'file')
            if source_type == 'arcgis_rest':
                self._process_rest_service(item)
            else:
                self._process_local_file(item)

    def _process_local_file(self, item: dict):
        """Processes a single local file item from the configuration."""
        file_path_suffix = item.get('file_path')
        full_file_path = os.path.join("./data", file_path_suffix)
        print(f"\n===== Processing Local File: {item.get('table_name')} =====")
        if not os.path.exists(full_file_path):
            print(f"⚠️ WARNING: File not found at '{full_file_path}'. Skipping.")
            return
        
        # Reading local file can take time, so we inform the user
        print(f"Reading file '{os.path.basename(full_file_path)}'... (This may take a while for large files)")
        gdf = gpd.read_file(full_file_path, layer=item.get('layer_name'))
        self._upload_gdf_to_db(gdf, item)

    def _process_rest_service(self, item: dict):
        """Processes a single ArcGIS REST service item from the configuration."""
        print(f"\n===== Processing REST Service: {item.get('table_name')} =====")
        gdf = self._fetch_rest_service(item.get('url'), item.get('layer_name'))
        if gdf is not None and not gdf.empty:
            self._upload_gdf_to_db(gdf, item)
        else:
            print("Skipping database upload due to empty or failed download.")

    def _fetch_rest_service(self, base_url: str, layer_id: str) -> gpd.GeoDataFrame | None:
        """Fetches all features from an ArcGIS Feature Service layer with a progress bar."""
        query_url = f"{base_url}/{layer_id}/query"
        params = {
            "where": "1=1",         # Get all features
            "outFields": "*",       # Get all columns
            "outSR": "4326",        # Request data in standard WGS 84 projection
            "f": "geojson"          # Request format is GeoJSON
        }
        try:
            print(f"Requesting data from: {query_url}")
            # Use streaming to handle large responses and show progress
            response = requests.get(query_url, params=params, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024 # 1KB
            
            # Setup the progress bar with tqdm
            progress_bar = tqdm(total=total_size, unit='iB', unit_scale=True, desc="Downloading")
            
            geojson_data = b""
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                geojson_data += data
            progress_bar.close()

            if total_size != 0 and progress_bar.n != total_size:
                print("⚠️ WARNING: Download size did not match expected content length.")

            print("Download complete. Parsing GeoJSON...")
            return gpd.read_file(geojson_data)

        except requests.exceptions.RequestException as e:
            print(f"❌ ERROR: Failed to fetch data from REST service. Error: {e}")
            return None
        except Exception as e:
            print(f"❌ ERROR: Failed to parse GeoJSON. Error: {e}")
            return None
            
    def _upload_gdf_to_db(self, gdf: gpd.GeoDataFrame, item: dict):
        """Standardizes and uploads a GeoDataFrame to all configured databases."""
        table_name = item.get('table_name')
        is_spatial = item.get('is_spatial', True)
        
        # Clean column names
        gdf.columns = gdf.columns.str.lower().str.replace('[^a-zA-Z0-9_]', '', regex=True)

        for env, engine in self.engines.items():
            print(f"--- Uploading '{table_name}' to {env.upper()} ---")
            try:
                # Use to_sql for non-spatial, to_postgis for spatial
                if is_spatial:
                    gdf.to_postgis(name=table_name, con=engine, if_exists='replace', index=False)
                else:
                    gdf.to_sql(name=table_name, con=engine, if_exists='replace', index=False)
                print(f"✅ Successfully imported {len(gdf)} records.")
            except Exception as e:
                print(f"❌ ERROR importing to '{env}': {e}")
        print("=" * 40)

if __name__ == '__main__':
    data_manager = DataManager()
    data_manager.run_all_imports()