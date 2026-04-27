import os, json, logging, requests
import geopandas as gpd
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def prepare_arcgis_url(url):
    """
    Standardizes ArcGIS URLs. If a layer index is missing, it defaults to 0.
    """
    url = url.strip().split('?')[0].rstrip('/') # Strip existing queries
    if "FeatureServer" in url:
        if url.endswith("FeatureServer"):
            return f"{url}/0/query"
        return f"{url}/query"
    return url

def fetch_paginated_geojson(base_url):
    """
    Fetches all features from an ArcGIS service using pagination.
    """
    all_features = []
    offset = 0
    limit = 1000 # Standard ArcGIS page size
    
    while True:
        params = {'where': '1=1', 'outFields': '*', 'f': 'geojson', 'resultOffset': offset, 'resultRecordCount': limit}
        response = requests.get(base_url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        features = data.get('features', [])
        all_features.extend(features)
        
        logging.info(f"  Fetched {len(all_features)} records so far...")
        
        # Check if we should continue
        if not data.get('exceededTransferLimit') or len(features) < limit:
            break
        offset += limit
        
    return gpd.GeoDataFrame.from_features(all_features, crs="EPSG:4326")

def main():
    load_dotenv()
    engine = create_engine(f"postgresql://{os.environ['DB_USER']}:{os.environ['DB_PASS']}@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}")
    
    with open('data/sources.json', 'r') as f:
        manifest = json.load(f)

    for definition in manifest.get('source_definitions', []):
        for category in definition.get('categories', []):
            for dataset in category.get('datasets', []):
                if not dataset.get('imported'): continue
                
                table_name = dataset['id'].lower().replace('-', '_')
                if inspect(engine).has_table(table_name):
                    logging.info(f"Skipping {table_name} (Already exists)")
                    continue

                try:
                    query_url = prepare_arcgis_url(dataset['scraped_url'])
                    gdf = fetch_paginated_geojson(query_url)
                    logging.info(f"Writing {len(gdf)} records to {table_name}...")
                    gdf.to_postgis(name=table_name, con=engine, if_exists='replace')
                except Exception as e:
                    logging.error(f"Failed {dataset['id']}: {e}")

if __name__ == "__main__":
    main()