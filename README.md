# glowing-octo-winner
An automated system to plan an agroforestry system.

# NYS GIS Data Scraper

This project is a Node.js web scraper designed to extract API links for datasets from the New York State GIS data portal. It uses **Puppeteer** for browser automation and **Jest** for testing.

The scraper is engineered to handle a modern, dynamic web application with complex features like infinite scrolling, nested shadow DOMs, and content that loads asynchronously.

-----

## Features

  * **Multi-Stage Scraping**: Navigates from a search results page to a details page, and finally to an API resource page.
  * **Shadow DOM Traversal**: Built to reliably pierce multiple nested shadow DOMs to find target elements.
  * **Dynamic Content Handling**:
      * Intelligently clicks "More results" to load all datasets before searching.
      * Handles SPA (Single-Page Application) behavior where the URL doesn't change but the page content does.
      * Activates and inspects dynamic side panels and accordions.
  * **Robust Testing**: Includes a comprehensive test suite built with Jest to validate each component of the scraper logic.
  * **Resilient Selectors**: Uses a combination of CSS, `data-test` attributes, and robust XPath selectors to minimize breakage from website updates.

-----

## Tech Stack

  * **Node.js**: The runtime environment.
  * **Puppeteer**: Headless browser automation and scraping library.
  * **Jest**: JavaScript testing framework.
  * **Babel**: For transpiling modern JavaScript to ensure compatibility with Jest.

-----

## Setup and Installation

1.  **Prerequisites**: Ensure you have Node.js (v18 or higher) and npm installed.
2.  **Clone the repository**:
    ```bash
    git clone <glowing-octo-winner repo url>
    cd glowing-octo-winner
    ```
3.  **Install dependencies**:
    ```bash
    npm install
    ```

-----

## Usage

### Running the Scraper

To run the main scraper and extract the API URL for the "Dams" dataset, use the start script. The final URL will be printed to the console.

```bash
npm start
```

### Running the Tests

To validate that all functions of the scraper are working correctly, run the Jest test suite.

```bash
npm test
```

To run only a specific set of tests while debugging, you can add `.only` to a `describe` or `it` block in the `tests/gis_scraper.test.js` file. For example:

```javascript
// This will ONLY run the test for the final stage of the scraper
describe.only('scrapeApiUrlFromDetailsPage', () => {
  // ...
});
```

-----

## How It Works

The scraper's logic is broken down into modular, testable functions located in `src/agroforestry/scraping/gis_scraper.js`.

1.  **Stage 1: Finding the Dataset (`findAndScrapeUrl`)**

      * Navigates to the NYS GIS water data search page.
      * If the target dataset isn't on the first page, the `loadAllResults` function is called to click the "More results" button until all datasets are visible.
      * The `findCardOnPage` function then locates the correct dataset card by its `data-test` attribute.
      * Finally, `extractUrlFromCard` gets the initial details page URL from the card.

2.  **Stage 2: Extracting the API Link (`scrapeApiUrlFromDetailsPage`)**

      * Navigates to the details page URL obtained from Stage 1.
      * The page auto-redirects to an `/explore` URL.
      * The scraper then clicks the "View API Resources" button to reveal a dynamic list of API links.
      * It waits for the `<arcgis-copyable-input>` elements to render.
      * It loops through the rendered inputs, inspecting the shadow DOM of each one to find the element with the "GeoJSON" label.
      * Once found, it returns the `value` of that input, which is the final GeoJSON API link.

# Documentation 
docs/                 # All project documentation
├── architecture/
│   ├── system_context.md
│   ├── container_diagram.plantuml
│   └── core_functionality_sequence.plantuml
└── project_timeline.md