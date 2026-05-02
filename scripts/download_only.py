import sys
import json
import time
import logging
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from pathlib import Path

# Make sure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import RERA_SOURCES, PDF_DIR, DATA_DIR
from rag.ingestion.web_scraper import scrape_page
from rag.ingestion.pdf_loader import find_pdf_links, download_pdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("download_only")


def deep_crawl_website(base_url: str, source_label: str, max_pages: int = 50) -> list[dict]:
    """
    Crawls a website starting from base_url, following internal links,
    and scraping text from each HTML page.
    """
    visited = set()
    queue = [base_url]
    docs = []
    
    logger.info(f"\n🕸️ Starting deep crawl on {base_url} (max {max_pages} pages)...")
    
    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        
        # Clean URL (remove fragments like #section)
        url = url.split("#")[0]
        if url in visited:
            continue
            
        visited.add(url)
        
        # Skip known non-HTML extensions just in case
        if any(url.lower().endswith(ext) for ext in [".pdf", ".jpg", ".png", ".zip", ".exe"]):
            continue
            
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}
            resp = requests.get(url, headers=headers, timeout=10)
            
            if "text/html" not in resp.headers.get("Content-Type", "").lower():
                continue
                
            # Use the existing scrape_page logic to extract clean text
            result = scrape_page(url, source_label)
            if result:
                docs.append(result)
                
            # Find new internal links to add to the queue
            soup = BeautifulSoup(resp.text, "lxml")
            for a_tag in soup.find_all("a", href=True):
                href = urljoin(url, a_tag["href"]).split("#")[0]
                
                # Ensure the link belongs to the same base domain
                if href.startswith(base_url) and href not in visited and href not in queue:
                    queue.append(href)
                    
            time.sleep(0.5)  # Be polite to the server
            
        except Exception as e:
            logger.warning(f"Failed to crawl {url}: {e}")
            continue
            
    logger.info(f"✅ Deep crawl finished. Scraped {len(docs)} web pages from {base_url}")
    return docs


def run_download(max_pdfs_per_source: int = 30, max_web_pages_per_source: int = 50):
    logger.info("=" * 60)
    logger.info("🚀 Starting Deep Data Download Phase")
    logger.info("=" * 60)

    web_data_file = DATA_DIR / "web_scraped_data.json"
    all_web_docs = []

    for source_key, source_config in RERA_SOURCES.items():
        label = source_config["label"]
        base_url = source_config["base_url"]
        
        # Skip if the domain is known to be completely dead
        if "rera.gov.in" in base_url:
            logger.warning(f"Skipping {label} because the domain is offline.")
            continue
            
        logger.info(f"\n{'─'*50}")
        logger.info(f"📂 Processing source: {label}")
        logger.info(f"{'─'*50}")

        # ── Step 1: Deep Crawl Website Data ──────────────────────────────────
        web_docs = deep_crawl_website(base_url, source_label=label, max_pages=max_web_pages_per_source)
        all_web_docs.extend(web_docs)
        
        # ── Step 2: Download PDFs ONLY (no parsing yet) ──────────────────────
        pdf_count = len(source_config.get("pdf_listing_pages", []))
        if pdf_count > 0:
            logger.info(f"\n📄 Downloading PDFs from listing pages...")
            for listing_url in source_config.get("pdf_listing_pages", []):
                pdf_links = find_pdf_links(listing_url, base_url)
                
                for link in pdf_links[:max_pdfs_per_source]:
                    # This just downloads and saves the PDF to disk without parsing
                    download_pdf(link["url"], PDF_DIR, link["title"])

    # Save the scraped web data to a JSON file so it can be transferred
    logger.info(f"\n💾 Saving all {len(all_web_docs)} web pages to {web_data_file.name}...")
    with open(web_data_file, "w", encoding="utf-8") as f:
        json.dump(all_web_docs, f, indent=4, ensure_ascii=False)

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ DOWNLOAD COMPLETE")
    logger.info(f"   PDFs saved to: {PDF_DIR}")
    logger.info(f"   Web data saved to: {web_data_file}")
    logger.info(f"   You can now copy the entire 'data' folder to your other computer.")
    logger.info(f"{'='*60}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Deep crawl & download RERA data (PDFs & Web HTML).")
    parser.add_argument("--max-pdfs", type=int, default=30, help="Max PDFs per source (default: 30)")
    parser.add_argument("--max-pages", type=int, default=50, help="Max Web pages to scrape per source (default: 50)")
    args = parser.parse_args()
    run_download(max_pdfs_per_source=args.max_pdfs, max_web_pages_per_source=args.max_pages)
