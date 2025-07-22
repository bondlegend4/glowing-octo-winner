import os
from dotenv import load_dotenv

# Load environment variables from the .env file in the root directory
load_dotenv()

# Database URL constructed from environment variables
DATABASE_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:"
    f"{os.getenv('POSTGRES_PASSWORD')}@localhost:5432/"
    f"{os.getenv('POSTGRES_DB')}"
)