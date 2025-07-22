from beam import endpoint, Image
import os
import geopandas as gpd
from sqlalchemy import create_engine
from supabase import create_client, Client

# 1. Define the container image directly
GIS_PROCESSOR_IMAGE = Image(
    python_version="python3.10",
    python_packages=[
        "geopandas",
        "sqlalchemy",
        "psycopg2-binary",
        "supabase",
        "pyogrio",
        "fiona",
    ],
)

# 2. Define the endpoint using the image and resource requests
@endpoint(
    name="process-file",
    # *** THIS IS THE FIX ***
    # The CPU value should be an integer, not a string.
    cpu=4,
    memory="16Gi",
    image=GIS_PROCESSOR_IMAGE,
    secrets=["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "DATABASE_CONNECTION_STRING"],
)
def process_gis_file(**inputs):
    """
    Beam endpoint to process a GIS file from Supabase Storage.
    Initializes clients on every call.
    """
    # --- Get Authentication & File Info ---
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    database_connection_string = os.environ.get("DATABASE_CONNECTION_STRING")

    bucket_name = inputs.get("bucket")
    file_path = inputs.get("path")

    if not all([supabase_url, supabase_service_key, database_connection_string, bucket_name, file_path]):
        error_message = "Missing required configuration. Check secrets and inputs."
        print(f"❌ {error_message}")
        return {"error": error_message}

    print(f"🚀 Received request to process: {bucket_name}/{file_path}")

    # --- Initialize Clients ---
    print("Initializing clients...")
    supabase: Client = create_client(supabase_url, supabase_service_key)
    db_engine = create_engine(database_connection_string)
    print("✅ Clients initialized.")

    # Define a temporary path inside the container
    local_temp_path = f"/tmp/{os.path.basename(file_path)}"
    table_name = os.path.basename(file_path).split('.')[0].lower()
    
    try:
        # --- Download File ---
        print(f"Downloading {file_path} from Supabase Storage...")
        with open(local_temp_path, 'wb+') as f:
            res = supabase.storage.from_(bucket_name).download(file_path)
            f.write(res)
        print("✅ Download complete.")

        # --- Process the File ---
        print(f"Reading file with GeoPandas...")
        target_layer = 'NYS_Tax_Parcels_Public' # Assuming the main parcel data layer
        gdf = gpd.read_file(local_temp_path, layer=target_layer)
        print("✅ File loaded into GeoDataFrame.")

        # --- Standardize data ---
        gdf.columns = gdf.columns.str.lower().str.replace('[^a-zA-Z0-9_]', '', regex=True)
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            print("Reprojecting to EPSG:4326...")
            gdf = gdf.to_crs(epsg=4326)

        # --- Insert Data into PostGIS ---
        print(f"Uploading {len(gdf)} records to table '{table_name}'...")
        gdf.to_postgis(
            name=table_name,
            con=db_engine,
            if_exists='replace',
            index=False,
            chunksize=10000
        )
        print("✅ Successfully imported data to PostGIS.")
        
        return {"status": "success", "message": f"Successfully processed {file_path}."}

    except Exception as e:
        error_message = f"An error occurred: {e}"
        print(f"❌ {error_message}")
        return {"status": "error", "message": str(e)}
    finally:
        # --- Clean up ---
        if os.path.exists(local_temp_path):
            os.remove(local_temp_path)
            print("🧹 Cleaned up temporary file.")