import os
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Helper functions from the scraper (can be moved to a shared utils file later)
def expand_shadow_root(driver, element):
    return driver.execute_script('return arguments[0].shadowRoot', element)

def find_element_in_shadow_root(driver, root_element, css_selector):
    shadow_root = expand_shadow_root(driver, root_element)
    return shadow_root.find_element(By.CSS_SELECTOR, css_selector)

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

    options.add_argument("--headless")
    options.add_argument("--start-maximized")
    service = Service(ChromeDriverManager(driver_version=browser_version).install())
    driver_instance = webdriver.Chrome(service=service, options=options)
    yield driver_instance
    driver_instance.quit()

def test_scraper_journey(driver):
    wait = WebDriverWait(driver, 20)
    start_url = "https://data.gis.ny.gov/search?categories=%2Fcategories%2Fwater&collection=dataset"
    
    # 1. Test: Can we reach the webpage?
    driver.get(start_url)
    assert "NYS GIS Clearinghouse" in driver.title
    print("\n✅ Test 1 Passed: Webpage reached successfully.")

    # 2. Test: Can we find the element right before the first shadow root?
    catalog_host = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'arcgis-hub-catalog')))
    assert catalog_host is not None
    assert catalog_host.get_attribute("data-test") == "site-search-catalog"
    print("✅ Test 2 Passed: Found <arcgis-hub-catalog> element.")

    # 3. Test: Can we traverse the shadow roots to the results container?
    gallery_host = find_element_in_shadow_root(driver, catalog_host, 'arcgis-hub-gallery')
    layout_list_host = find_element_in_shadow_root(driver, gallery_host, 'arcgis-hub-gallery-layout-list')
    card_container = find_element_in_shadow_root(driver, layout_list_host, 'ul.card-container')
    assert card_container is not None
    assert card_container.get_attribute("data-test") == "result-container"
    print("✅ Test 3 Passed: Traversed shadow DOM to find the card container.")

    # 4. Test: Can we find the list item holding the "Dams" data?
    dams_card_host = card_container.find_element(By.CSS_SELECTOR, 'arcgis-hub-entity-card[data-test="Dams"]')
    assert dams_card_host is not None
    print("✅ Test 4 Passed: Found the list item for 'Dams'.")

    # 5. Test: Can we find the link within the Dams card?
    hub_card_host = find_element_in_shadow_root(driver, dams_card_host, 'arcgis-hub-card')
    calcite_card = find_element_in_shadow_root(driver, hub_card_host, 'calcite-card')
    link_element = calcite_card.find_element(By.CSS_SELECTOR, 'h3.title a')
    dams_url = link_element.get_attribute('href')
    assert "https://data.gis.ny.gov/maps/" in dams_url
    print(f"✅ Test 5 Passed: Found Dams link: {dams_url}")

    # 6. Test: Can we follow the link and find the "View Full Details" button?
    driver.get(dams_url)
    details_button = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, 'View Full Details')))
    assert details_button.is_displayed()
    details_url = details_button.get_attribute('href')
    print(f"✅ Test 6 Passed: Found 'View Full Details' link: {details_url}")

    # 7 & 8. Test: Can we follow the details link and find the final API URL?
    driver.get(details_url)
    api_link = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-test-id="item-api-link"]')))
    final_api_url = api_link.get_attribute('href')
    assert "arcgis/rest/services" in final_api_url
    print(f"✅ Test 7 & 8 Passed: Successfully found final API URL: {final_api_url}")