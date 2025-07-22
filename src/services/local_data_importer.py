import geopandas as gpd
from sqlalchemy import create_engine
from ..config import DATABASE_URL # Import your database URL

def import_local_gis_file(file_path: str, table_name: str):
    """
    Imports a local GIS file (Shapefile, GeoJSON, etc.) into PostGIS.
    
    Args:
        file_path: The full path to your local GIS file.
        table_name: The desired name for the table in the database.
    """
    print(f"Connecting to database...")
    engine = create_engine(DATABASE_URL)
    
    try:
        print(f"Reading file: {file_path}")
        # GeoPandas reads many formats
        gdf = gpd.read_file(file_path)
        
        # --- Data Standardization ---
        # 1. Ensure a standard projection (EPSG:4326 is the web standard)
        print(f"Original CRS: {gdf.crs}")
        if gdf.crs.to_epsg() != 4326:
            print("Reprojecting to EPSG:4326...")
            gdf = gdf.to_crs(epsg=4326)
        
        # 2. Clean up column names (lowercase, no special chars)
        gdf.columns = gdf.columns.str.lower().str.replace(' ', '_').str.replace('[^a-zA-Z0-9_]', '', regex=True)

        print(f"Importing {len(gdf)} features into table '{table_name}'...")
        
        # Write to PostGIS
        gdf.to_postgis(
            name=table_name,
            con=engine,
            if_exists='replace', # Use 'replace' for first import, 'append' to add data later
            index=True,
            index_label='id'
        )
        
        print("Import successful!")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    # --- Example Usage ---
    # Assume you have your downloaded NYS parcel data in a 'data' subfolder
    # The path will depend on where you save the file.
    NYS_PARCEL_FILE_PATH = "./data/NYS_Tax_Parcels_Public/NYS_Tax_Parcels_Public.shp"
    
    import_local_gis_file(NYS_PARCEL_FILE_PATH, table_name="nys_tax_parcels")