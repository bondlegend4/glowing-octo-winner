import os
import pytest
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException


# --- Import the functions directly from the scraper ---
from src.agroforestry.scraping.gis_scrapper import (
    find_element_in_shadow_root,
    find_dataset_page_url,
    extract_api_from_details_page,
    construct_geojson_query_url
)

# --- Pytest Fixture ---
@pytest.fixture(scope="module")
def driver():
    options = Options()
    brave_path = os.getenv("BRAVE_BINARY_PATH")
    if brave_path and os.path.exists(brave_path):
        options.binary_location = brave_path
    else:
        print("Warning: BRAVE_BINARY_PATH environment variable not set.")

    browser_version = os.getenv("BRAVE_VERSION")
    if not browser_version:
        raise ValueError("BRAVE_VERSION environment variable not set.")

    options.add_argument("--start-maximized")
    options.add_argument('log-level=1')
    service = Service(ChromeDriverManager(driver_version=browser_version).install())
    driver_instance = webdriver.Chrome(service=service, options=options)
    driver_instance.implicitly_wait(5) # Add a small implicit wait

    yield driver_instance
    print("\nTest run finished, closing browser.")
    driver_instance.quit()

def test_extract_dams_api_url(driver):
    """Tests if we can extract the final API url from a known dataset page."""
    wait = WebDriverWait(driver, 20)
    # This URL was found by the previous test
    dataset_page_url = "https://data.gis.ny.gov/datasets/5a7d83359cc842e08711215408f5b55c"

    api_url = extract_api_from_details_page(driver, wait, dataset_page_url)
    assert api_url is not None
    assert "FeatureServer" in api_url

def test_construct_query_url():
    """Tests the construction of the final GeoJSON query URL."""
    base_url = "https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Civil_Boundaries/FeatureServer"
    expected = "https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Civil_Boundaries/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson"
    assert construct_geojson_query_url(base_url) == expected
    print("\n✅ Passed: GeoJSON query URL construction is correct.")


def test_scraper_journey(driver):
    wait = WebDriverWait(driver, 20)
    start_url = "https://data.gis.ny.gov/search?categories=%2Fcategories%2Fwater&collection=dataset"

    # Step 1: Reach the webpage
    print("\n--- Step 1: Navigating to page ---")
    driver.get(start_url)
    wait.until(EC.title_contains("NYS GIS Clearinghouse"))
    print("✅ Passed: Webpage reached successfully.")

    # Step 2: Find the top-level host element
    print("\n--- Step 2: Finding top-level shadow host ---")
    catalog_host = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'arcgis-hub-catalog')))
    time.sleep(1) # Add a small pause to prevent race condition
    assert catalog_host is not None
    print("✅ Passed: Found <arcgis-hub-catalog> element.")

    # --- CORRECTED NESTED TRAVERSAL TEST ---
    # Step 3: Find the gallery host INSIDE the catalog's shadow root
    print("\n--- Step 3: Finding gallery host inside first shadow root ---")
    gallery_host = find_element_in_shadow_root(driver, catalog_host, 'arcgis-hub-gallery')
    assert gallery_host is not None
    print("✅ Passed: Found <arcgis-hub-gallery> element.")

    # Step 4: Find a specific card inside the gallery's shadow root
    print("\n--- Step 4: Finding a specific card ---")
    item_card = find_element_in_shadow_root(driver, gallery_host, 'arcgis-hub-content-card[name="Dams"]')
    assert item_card is not None
    print("✅ Passed: Found the 'Dams' item card.")

#  --- Tests ---
def test_find_dams_dataset_url(driver):
    """Tests if we can find the specific URL for the 'Dams' dataset."""
    wait = WebDriverWait(driver, 20)
    start_url = "https://data.gis.ny.gov/search?categories=%2Fcategories%2Fwater"
    keywords = "Dams"

    page_url = find_dataset_page_url(driver, wait, start_url, keywords)
    assert page_url is not None
    assert "https://data.gis.ny.gov/datasets/" in page_url