import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# --- Environment Configuration ---
# Set an environment variable 'ENV_MODE' to 'local' or 'production'
# Defaults to 'local' if not set.
ENV_MODE = os.getenv('ENV_MODE', 'local')

# --- Database Connection ---
DATABASE_URL = ""

if ENV_MODE == 'production':
    # Supabase Connection Details (get these from your Supabase project dashboard)
    # The connection string format is: postgresql://postgres:[YOUR-PASSWORD]@[YOUR-HOST]:5432/postgres
    PROD_DB_USER = os.getenv('SUPABASE_USER')
    PROD_DB_PASS = os.getenv('SUPABASE_PASSWORD')
    PROD_DB_HOST = os.getenv('SUPABASE_HOST')
    PROD_DB_NAME = os.getenv('SUPABASE_DB')
    DATABASE_URL = f"postgresql+psycopg2://{PROD_DB_USER}:{PROD_DB_PASS}@{PROD_DB_HOST}:5432/{PROD_DB_NAME}"
else:
    # Local Docker Connection Details (from your other .env file)
    LOCAL_DB_USER = os.getenv('POSTGRES_USER')
    LOCAL_DB_PASS = os.getenv('POSTGRES_PASSWORD')
    LOCAL_DB_HOST = 'localhost' # The service name in docker-compose is 'postgres', but from your host machine it's 'localhost'
    LOCAL_DB_NAME = os.getenv('POSTGRES_DB')
    DATABASE_URL = f"postgresql+psycopg2://{LOCAL_DB_USER}:{LOCAL_DB_PASS}@{LOCAL_DB_HOST}:5432/{LOCAL_DB_NAME}"

# --- API Keys ---
REGRID_API_TOKEN = os.getenv('REGRID_API_TOKEN')

print(f"--- Running in {ENV_MODE.upper()} mode ---")