import logging
import json
import os
import asyncio
from playwright.async_api import async_playwright

from helpers import setup_logging_levels


# Files for persisting the links
TO_BE_PROCESSED_FILE = "to_be_processed_links.json"
VISITED_LINKS_FILE = "visited_links.json"
LINKS_FILE = "links.json"
START_PAGE = "https://www.fedlex.admin.ch/{language_code}/cc/internal-law/{index}"


async def extract_urls(page_url: str, language_code: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            java_script_enabled=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36",  # Realistic user agent
            viewport={"width": 1280, "height": 720},  # Typical viewport size
            locale="en-US"  # Set the language to US English
        )
        await context.add_init_script("""Object.defineProperty(navigator, 'webdriver', { get: () => undefined })""")
        page = await context.new_page()
        
        # Navigate to the target page
        await page.goto(page_url)
        await page.wait_for_load_state('networkidle')  # Important - lets javascript execute itself
        
        logging.info("loaded page %s", page_url)
        
        # Extract all anchor tags and their href attributes
        links = await page.eval_on_selector_all('#content a', 'elements => elements.map(el => el.href)')

        await browser.close()
        all_links = {link.split('#')[0] for link in links if not link.endswith("#context-top")}
        leaf_links = {link for link in all_links if link.endswith(language_code)}
        node_links = {link for link in all_links if not link.endswith(language_code)}
        return sorted(leaf_links), sorted(node_links)


# Helper function to load JSON data from a file
def load_from_file(file_path, default_value):
    logging.info("loading %s", file_path)
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        with open(file_path, 'r') as f:
            return json.load(f)
    return default_value


# Helper function to save JSON data to a file
def save_to_file(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=3)


async def task(output_dir: str):
    setup_logging_levels()
    language = 'fr'

    # Load the links from files if they exist
    file_to_be_processed = os.path.sep.join([output_dir, TO_BE_PROCESSED_FILE])
    file_visited = os.path.sep.join([output_dir, VISITED_LINKS_FILE])
    file_links = os.path.sep.join([output_dir, LINKS_FILE])
    initial_links = [START_PAGE.format(language_code=language, index=index) for index in range(1, 10)]
    to_be_processed_links = load_from_file(file_to_be_processed, initial_links)
    visited_links = set(load_from_file(file_visited, []))
    urls = set(load_from_file(file_links, []))
    
    while len(to_be_processed_links) > 0:
        current_link = to_be_processed_links.pop()

        # Process the link (assumed to be an async function that extracts URLs)
        leaf_links, node_links = await extract_urls(current_link, language_code=language)
        
        # Add the current link to visited links
        visited_links.add(current_link)

        # Persist the updated lists after processing the current link
        save_to_file(file_to_be_processed, to_be_processed_links)
        save_to_file(file_visited, list(visited_links))

        # Append new node links to the to-be-processed list if they haven't been visited
        for link in node_links:
            if link not in visited_links:
                to_be_processed_links.append(link)

        # Persist the lists again after adding the new links
        save_to_file(file_to_be_processed, to_be_processed_links)

        for url in leaf_links:
            urls.add(url)

        save_to_file(file_links, list(urls))
        logging.info("collected links: %d", len(file_links))
        logging.info("processed pages: %d", len(visited_links))
        logging.info("remainging pages: %d", len(to_be_processed_links))
        


def main():
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    asyncio.run(task(output_dir))
