"""
rag/ingestion/pdf_loader.py
Downloads PDFs from RERA listing pages and parses them into text.
"""
import os
import re
import time
import hashlib
import logging
import requests
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _url_to_filename(url: str) -> str:
    """Create a safe, unique filename from a URL."""
    name = re.sub(r"[^\w\-_.]", "_", urlparse(url).path.strip("/"))
    name = name[-80:] if len(name) > 80 else name
    uid  = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{uid}_{name}.pdf"


def find_pdf_links(page_url: str, base_url: str) -> list[dict]:
    """
    Scrape a listing page and return all PDF links found.
    Returns: [{"url": ..., "title": ...}, ...]
    """
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Cannot fetch listing page {page_url}: {e}")
        return []

    soup  = BeautifulSoup(resp.text, "lxml")
    links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        # Resolve relative URLs
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        # Filter to PDF links only
        if href.lower().endswith(".pdf") or "pdf" in urlparse(href).query.lower():
            title = a_tag.get_text(strip=True) or urlparse(href).path.split("/")[-1]
            links.append({"url": href, "title": title[:200]})

    logger.info(f"Found {len(links)} PDF links on {page_url}")
    return links


def download_pdf(url: str, save_dir: Path, title: str = "") -> Optional[Path]:
    """Download a PDF and save to disk. Returns path or None if failed."""
    filename = _url_to_filename(url)
    save_path = save_dir / filename

    if save_path.exists():
        logger.info(f"[SKIP] Already downloaded: {filename}")
        return save_path

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()

        # Verify it's actually a PDF
        content_type = resp.headers.get("Content-Type", "")
        if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
            logger.warning(f"Skipping non-PDF response from {url}")
            return None

        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"[DOWNLOADED] {title or filename}")
        return save_path

    except Exception as e:
        logger.warning(f"Failed to download {url}: {e}")
        return None


def parse_pdf(pdf_path: Path, source_label: str = "", source_url: str = "") -> list[dict]:
    """
    Parse a PDF into a list of page dicts with text and metadata.
    Returns: [{"text": ..., "metadata": {...}}, ...]
    """
    docs = []
    try:
        doc = fitz.open(str(pdf_path))
        filename = pdf_path.name

        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if len(text) < 50:  # Skip near-empty pages
                continue

            docs.append({
                "text": text,
                "metadata": {
                    "source":       source_label or "RERA",
                    "filename":     filename,
                    "page":         page_num,
                    "total_pages":  len(doc),
                    "source_url":   source_url,
                    "doc_type":     "pdf",
                }
            })

        doc.close()
        logger.info(f"Parsed {len(docs)} pages from {filename}")

    except Exception as e:
        logger.error(f"Error parsing PDF {pdf_path}: {e}")

    return docs


def load_pdfs_from_source(
    source_config: dict,
    pdf_dir: Path,
    source_key: str,
    max_pdfs: int = 50
) -> list[dict]:
    """
    Full pipeline: find PDF links → download → parse for one RERA source.
    Returns list of page dicts ready for chunking.
    """
    all_docs = []
    label    = source_config["label"]
    base_url = source_config["base_url"]

    for listing_url in source_config.get("pdf_listing_pages", []):
        logger.info(f"\n📄 Fetching PDF list from: {listing_url}")
        pdf_links = find_pdf_links(listing_url, base_url)

        for i, link in enumerate(pdf_links[:max_pdfs]):
            pdf_path = download_pdf(link["url"], pdf_dir, link["title"])
            if pdf_path:
                docs = parse_pdf(
                    pdf_path,
                    source_label=f"{label} | {link['title']}",
                    source_url=link["url"]
                )
                all_docs.extend(docs)
            time.sleep(0.5)  # Be polite to the server

    return all_docs
