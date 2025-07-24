import uvicorn
import typer
from agroforestry.scraping import gis_scraper
from agroforestry.data import importer # Assuming you will create an importer.py

app = typer.Typer()

@app.command()
def run_api():
    """
    Starts the FastAPI server.
    """
    print("Starting FastAPI server at http://127.0.0.1:8000")
    uvicorn.run("src.agroforestry.api.endpoints:app", host="127.0.0.1", port=8000, reload=True)

@app.command()
def scrape_sources():
    """
    Runs the GIS web scraper to find data source links.
    """
    print("Starting the GIS scraper...")
    gis_scraper.main()

# @app.command()
# def import_data():
#     """
#     Runs the data importer to load data from sources defined in the config.
#     """
#     print("Starting the data importer...")
#     importer.run_importer()

if __name__ == "__main__":
    app()