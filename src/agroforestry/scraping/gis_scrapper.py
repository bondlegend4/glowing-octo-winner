import os
import time
from pathlib import Path
import yaml
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- HELPER FUNCTIONS ---

def expand_shadow_root(driver, element):
    """Expands and returns the shadow root of a given web element."""
    return driver.execute_script('return arguments[0].shadowRoot', element)

def find_element_in_shadow_root(driver, root_element, css_selector):
    """Finds a single element within a shadow root."""
    shadow_root = expand_shadow_root(driver, root_element)
    return shadow_root.find_element(By.CSS_SELECTOR, css_selector)

def find_dataset_page_url(driver, wait, start_url, keywords):
    """
    Navigates to the start URL and finds the specific dataset's main page URL.
    Returns the URL as a string or None if not found.
    """
    print(f"Navigating to search page: {start_url}")
    driver.get(start_url)
    
    try:
        # 1. Get to the main catalog container
        catalog_host = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'arcgis-hub-catalog')))

        # 2. Traverse shadow DOMs to get to the list of results
        gallery_host = find_element_in_shadow_root(driver, catalog_host, 'arcgis-hub-gallery')
        layout_list_host = find_element_in_shadow_root(driver, gallery_host, 'arcgis-hub-gallery-layout-list')
        card_container = find_element_in_shadow_root(driver, layout_list_host, 'ul.card-container')

        # 3. Find the specific card by its data-test attribute (keywords)
        print(f"Searching for card with keywords: '{keywords}'")
        card_selector = f'arcgis-hub-entity-card[data-test="{keywords}"]'
        dataset_card_host = wait.until(lambda d: card_container.find_element(By.CSS_SELECTOR, card_selector))
        
        # 4. Traverse into the card's shadow DOM to find the link
        hub_card_host = find_element_in_shadow_root(driver, dataset_card_host, 'arcgis-hub-card')
        calcite_card = find_element_in_shadow_root(driver, hub_card_host, 'calcite-card')
        
        link_element = calcite_card.find_element(By.CSS_SELECTOR, 'h3.title a')
        page_url = link_element.get_attribute('href')
        print(f"Found dataset page link: {page_url}")
        return page_url
    except Exception as e:
        print(f"Error finding dataset page for '{keywords}': {e}")
        return None

def extract_api_from_details_page(driver, wait, dataset_page_url):
    """
    Navigates to the dataset page, clicks through to details, and extracts the final API URL.
    Returns the API URL string or None if not found.
    """
    print(f"Navigating to dataset page: {dataset_page_url}")
    driver.get(dataset_page_url)
    try:
        # 5. Find and click the "View Full Details" button
        details_button = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, 'View Full Details')))
        details_url = details_button.get_attribute('href')
        print(f"Found 'View Full Details' link: {details_url}")
        driver.get(details_url)

        # 6. On the about page, find the API link
        api_link = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-test-id="item-api-link"]')))
        final_api_url = api_link.get_attribute('href')
        print(f"Successfully extracted API URL: {final_api_url}")
        return final_api_url
    except Exception as e:
        print(f"Error extracting API URL from '{dataset_page_url}': {e}")
        return None

def construct_geojson_query_url(api_url):
    """
    Constructs a GeoJSON query URL from a standard ArcGIS REST service URL.
    Example: .../FeatureServer/0 -> .../FeatureServer/0/query?f=geojson
    """
    if not api_url:
        return None
    
    # A simple, robust way to add the query parameter
    if '?' in api_url:
        return f"{api_url}&f=geojson"
    else:
        return f"{api_url}/query?f=geojson"

# --- MAIN DRIVER FUNCTION ---

def main():
    """Main function to drive the scraping process."""
    # Build paths relative to this file's location
    project_root = Path(__file__).resolve().parents[3] # Assumes /root/src/agroforestry/scraping and /root/config/{files}
    config_path = project_root / "config" / "target_data.yaml"
    output_path = project_root / "config" / "scraped_data_config.yaml"

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    targets = config.get('data_sources_to_scrape', [])
    scraped_sources = []
    # --- Your Improved Browser Setup ---
    options = Options()
    brave_path = os.getenv("BRAVE_BINARY_PATH")
    if brave_path and os.path.exists(brave_path):
        options.binary_location = brave_path
    else:
        print("Warning: BRAVE_BINARY_PATH environment variable not set.")

    browser_version = os.getenv("BRAVE_VERSION")
    if not browser_version:
        raise ValueError("BRAVE_VERSION environment variable not set.")

    options.add_argument("--headless")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager(driver_version=browser_version).install())
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 20)
    
    try:
        for target in targets:
            print(f"\nProcessing target: {target['keywords']}")
            
            # The start URL is now dynamic based on the target's category
            start_url = f"https://data.gis.ny.gov/search?categories=%2Fcategories%2F{target['category']}"

            dataset_page_url = find_dataset_page_url(driver, wait, start_url, target['keywords'])
            
            if dataset_page_url:
                api_url = extract_api_from_details_page(driver, wait, dataset_page_url)
                geojson_url = construct_geojson_query_url(api_url)
                
                if geojson_url:
                    source_id = f"nys_{target['purpose']}_{target['keywords'].lower().replace(' ', '_')}"
                    scraped_sources.append({
                        'id': source_id,
                        'purpose': target['purpose'],
                        'type': 'rest_api',
                        'url': geojson_url,
                        'imported': False
                    })
    finally:
        print("\nClosing browser...")
        driver.quit()

    output_data = {'sources': scraped_sources}
    with open(output_path, 'w') as f:
        yaml.dump(output_data, f, indent=2, sort_keys=False)
        
    print(f"Scraping complete. Output written to '{output_path}'")

if __name__ == "__main__":
    main()