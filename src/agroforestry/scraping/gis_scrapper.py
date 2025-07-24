import yaml
import time
import os
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "https://data.gis.ny.gov/"

def find_element_in_shadow_dom(driver, keywords):
    """
    Finds a specific element within nested shadow DOMs using a robust JavaScript function.
    This function searches for a link within a card that matches the keywords.
    """
    script = """
    function findElement(root, selector) {
        // First, search in the light DOM
        let element = root.querySelector(selector);
        if (element) return element;

        // Then, search in all shadow roots
        const walkers = [document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT)];
        while(walkers.length > 0) {
            const walker = walkers.pop();
            while(walker.nextNode()) {
                if(walker.currentNode.shadowRoot) {
                    element = walker.currentNode.shadowRoot.querySelector(selector);
                    if (element) return element;
                    walkers.push(document.createTreeWalker(walker.currentNode.shadowRoot, NodeFilter.SHOW_ELEMENT));
                }
            }
        }
        return null;
    }
    // The specific selector for the card link based on its data-test attribute
    const cardSelector = `arcgis-hub-entity-card[data-test*="${keywords}" i]`;
    const card = findElement(document.body, cardSelector);
    if (card && card.shadowRoot) {
        return card.shadowRoot.querySelector('h3.title a');
    }
    return null;
    """
    try:
        # Give the page a moment to render the complex components
        time.sleep(5) 
        element = driver.execute_script(script.replace("${keywords}", keywords))
        return element
    except Exception as e:
        print(f"JavaScript execution failed: {e}")
        return None

def find_dataset_page(driver, category, keywords):
    """Uses Selenium to search a category page and returns the dataset's URL."""
    search_url = f"{BASE_URL}/search?categories=%2Fcategories%2F{category}"
    print(f"Navigating to {search_url} to find '{keywords}'...")
    driver.get(search_url)

    try:
        # Wait for the main catalog element to signal the page is loading
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, 'arcgis-hub-catalog'))
        )
        
        # Use the robust JS function to find the link element
        link_element = find_element_in_shadow_dom(driver, keywords)
        
        if link_element:
            dataset_url = link_element.get_attribute('href')
            print(f"  Found dataset page: {dataset_url}")
            return dataset_url

    except Exception as e:
        print(f"  Error finding dataset page for '{keywords}': {e}")
    
    print(f"  Warning: Could not find dataset page for '{keywords}'.")
    return None

def extract_api_from_details_page(driver, page_url):
    """Navigates to the details page and extracts the REST API link."""
    print(f"  Navigating to details page: {page_url}")
    driver.get(page_url)
    
    try:
        view_data_source_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[data-testid="data-source-button"]'))
        )
        
        try:
            api_section = driver.find_element(By.XPATH, "//h4[text()='View API']")
            geoservice_link_element = api_section.find_element(By.XPATH, "./following-sibling::div//a[text()='GeoService']")
            api_url = geoservice_link_element.get_attribute('href')
            print("  Found GeoService link directly on page.")
            return api_url
        except Exception:
            print("  'View API' not found. Following 'View Data Source' link...")
            data_source_url = view_data_source_button.get_attribute('href')
            driver.get(data_source_url)
            
            layer_item_link = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".layer-item-title a"))
            )
            api_url = layer_item_link.get_attribute('href')
            print(f"  Found Feature Layer API link: {api_url}")
            return api_url

    except Exception as e:
        print(f"  Error extracting API link: {e}")

    return None

def construct_geojson_query_url(api_url):
    """Constructs the full GeoJSON query URL from a base REST service URL."""
    if not api_url:
        return None
        
    base_service_url = api_url.split('/query?')[0]
    
    if not base_service_url.split('/')[-1].isdigit():
        base_service_url = base_service_url.rstrip('/') + "/0"

    query_url = f"{base_service_url}/query?where=1%3D1&outFields=*&f=geojson"
    print(f"  Constructed GeoJSON query URL: {query_url}")
    return query_url

def main():
    """Main function to drive the scraping process."""
    # Build a path to the config directory relative to this file's location
    project_root = Path(__file__).resolve().parents[3]
    config_path = project_root / "config" / "target_data.yaml"
    output_path = project_root / "config" / "scraped_data_config.yaml"

    with open(config_path, 'r') as f:
        targets = yaml.safe_load(f)

    scraped_sources = []
    
    options = Options()
    brave_path = os.getenv("BRAVE_BINARY_PATH")
    if brave_path:
        options.binary_location = brave_path
    else:
        print("Warning: BRAVE_BINARY_PATH environment variable not set.")

    browser_version = os.getenv("BRAVE_VERSION")
    if not browser_version:
        raise ValueError("BRAVE_VERSION environment variable not set.")

    service = Service(ChromeDriverManager(driver_version=browser_version).install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        for target in targets:
            print(f"\nProcessing target: {target['keywords']}")
            dataset_page_url = find_dataset_page(driver, target['category'], target['keywords'])
            
            if dataset_page_url:
                api_url = extract_api_from_details_page(driver, dataset_page_url)
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
        driver.quit()

    output_data = {'sources': scraped_sources}
    with open(output_path, 'w') as f:
        yaml.dump(output_data, f, indent=2, sort_keys=False)
        
    print(f"\nScraping complete. Output written to '{output_path}'")

if __name__ == "__main__":
    main()