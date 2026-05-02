"""
rag/ingestion/web_scraper.py
Scrapes RERA web pages (FAQs, Acts, Rules pages) into plain text documents.
"""
import time
import logging
import requests
from typing import Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Tags to completely remove (nav, ads, footers, scripts)
REMOVE_TAGS = [
    "nav", "header", "footer", "script", "style",
    "noscript", "aside", "form", "button", "iframe",
    "img", "svg", "meta", "link"
]


def scrape_page(url: str, source_label: str = "") -> dict | None:
    """
    Scrape a single web page and return a content dict.
    Returns: {"text": ..., "metadata": {...}} or None
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Cannot fetch {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # Remove noise elements
    for tag in soup.find_all(REMOVE_TAGS):
        tag.decompose()

    # Try to get the page title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else urlparse(url).path

    # Extract the main content area (common selectors)
    main_content = (
        soup.find("main") or
        soup.find("article") or
        soup.find(id="content") or
        soup.find(class_="content") or
        soup.find(id="main-content") or
        soup.body
    )

    if not main_content:
        logger.warning(f"No content found on {url}")
        return None

    # Get clean text
    text = main_content.get_text(separator="\n", strip=True)
    # Collapse multiple blank lines
    import re
    text = re.sub(r"\n{3,}", "\n\n", text)

    if len(text) < 100:
        logger.warning(f"Very little text on {url}, skipping")
        return None

    logger.info(f"[SCRAPED] {title} ({len(text)} chars) from {url}")
    return {
        "text": text,
        "metadata": {
            "source":     source_label or "RERA",
            "title":      title,
            "source_url": url,
            "doc_type":   "webpage",
        }
    }


def scrape_all_pages(source_config: dict, source_key: str) -> list[dict]:
    """
    Scrape all configured web pages for a RERA source.
    Returns list of content dicts.
    """
    label = source_config["label"]
    docs  = []

    for url in source_config.get("web_pages", []):
        logger.info(f"\n🌐 Scraping page: {url}")
        result = scrape_page(url, source_label=label)
        if result:
            docs.append(result)
        time.sleep(1.0)  # Respectful crawl delay

    return docs
