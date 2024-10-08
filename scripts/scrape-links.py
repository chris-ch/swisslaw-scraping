
import requests
import bs4
import logging

from helpers import setup_logging_levels


START_PAGE_DE = "https://www.fedlex.admin.ch/de/cc/internal-law/1"
START_PAGE_EN = "https://www.fedlex.admin.ch/en/cc/internal-law/1"
START_PAGE_FR = "https://www.fedlex.admin.ch/fr/cc/internal-law/1"
START_PAGE_IT = "https://www.fedlex.admin.ch/it/cc/internal-law/1"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Connection": "keep-alive",
    "Referer": "https://google.com"
}


def main():
    setup_logging_levels()
    
    # Step 1: Send an HTTP request to the URL
    response = requests.get(START_PAGE_DE, headers=HEADERS)

    # Step 2: Check if the request was successful
    if response.status_code == 200:
        # Step 3: Load the page content into BeautifulSoup
        soup = bs4.BeautifulSoup(response.content, 'html.parser')

        # Step 4: You can now use BeautifulSoup to parse and manipulate the HTML
        print(soup.prettify())  # This will print the formatted HTML structure of the page
    else:
        logging.error(f"Failed to retrieve the page. Status code: {response.status_code}")
