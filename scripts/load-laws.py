import logging
import json
import os
import asyncio
from typing import Optional
from playwright.async_api import async_playwright
from urllib.parse import urlparse
from pathlib import Path

import requests

from helpers import setup_logging_levels


def load_from_file(file_path: str):
    logging.info("loading %s", file_path)
    with open(file_path, 'r') as f:
        return json.load(f)
    return default_value


async def extract_xml_url(page_url: str) -> Optional[str]:
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)  # Set headless=False if you want to see the browser
        page = await browser.new_page()

        # Open the page
        await page.goto(page_url)

        # Wait for the table to be available in the DOM
        await page.wait_for_selector('#versionContent')

        # Find the table row that contains the circle with the soft-green class
        row = await page.query_selector('table#versionContent tr:has(td > span.circle.soft-green)')

        # If the row is found, locate the XML link in the row and extract the href attribute
        if row:
            xml_link = await row.query_selector('a:has-text("XML")')
            if xml_link:
                xml_url = await xml_link.get_attribute('href')
                logging.info(f"extracted XML URL: {xml_url}")
            else:
                logging.error("no XML link found in the selected row")
                xml_url = None
        else:
            logging.error("no row with 'soft-green' circle found")
            xml_url = None

        # Close browser
        await browser.close()
    return xml_url


async def task(links_file: str, output_dir: Path):

    urls = load_from_file(links_file)
    logging.info("%d urls to be processed", len(urls))
    
    count_files = sum(1 for _ in output_dir.rglob('*') if _.is_file())
    logging.info("%d files already retrieved under %s", count_files, output_dir)
    
    for url in urls:
        parsed_url = urlparse(url)
        target_path = output_dir.joinpath(parsed_url.path[1:])
        if target_path.exists():
            if any(target_path.iterdir()):
                continue

        logging.info("processing %s to be saved under %s", url, target_path)
        target_xml_url = await extract_xml_url(url)
        if target_xml_url:
            xml_file_name = target_xml_url.split('/')[-1]  # Get the last part of the URL as the file name
            xml_file_path = target_path / xml_file_name
            response = requests.get("/".join([parsed_url.scheme + "://" + parsed_url.hostname, target_xml_url]))
            status = response.status_code
            content = response.content
        else:
            status = 200
            content = b'<?xml version="1.0" encoding="UTF-8"?><unavailable/>'
            xml_file_path = target_path / "unavailble.xml"
        
        if status == 200:
            target_path.mkdir(parents=True, exist_ok=True)
            with open(xml_file_path, 'wb') as f:
                f.write(content)
            logging.info("file saved successfully at %s", xml_file_path)
        else:
            logging.error("failed to download the file (status code: %s)", response.status_code)


def main():
    setup_logging_levels()
    output_dir = Path("output/downloads").absolute()
    links_file = "output/links.json"
    logging.info("saving downloaded xml files under %s", output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    asyncio.run(task(links_file, output_dir))
