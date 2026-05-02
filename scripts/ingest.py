"""
scripts/ingest.py
One-time (and schedulable) ingestion script.
Run this BEFORE starting the bot:  python scripts/ingest.py

It will:
  1. Scrape MahaRERA & National RERA web pages
  2. Find and download PDFs from listing pages
  3. Parse, chunk, embed, and store everything in ChromaDB
"""
import sys
import logging
from pathlib import Path

# Make sure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import RERA_SOURCES, PDF_DIR
from rag.ingestion.web_scraper import scrape_all_pages
from rag.ingestion.pdf_loader import load_pdfs_from_source
from rag.ingestion.chunker import chunk_documents
from rag.vectorstore import add_chunks, get_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ingest")


def run_ingestion(max_pdfs_per_source: int = 30) -> dict:
    """
    Full ingestion pipeline for all RERA sources.
    Returns summary stats dict.
    """
    logger.info("=" * 60)
    logger.info("🚀 Starting RERA Knowledge Base Ingestion")
    logger.info("=" * 60)

    all_raw_docs = []

    for source_key, source_config in RERA_SOURCES.items():
        label = source_config["label"]
        logger.info(f"\n{'─'*50}")
        logger.info(f"📂 Processing source: {label}")
        logger.info(f"{'─'*50}")

        # ── Step 1: Scrape web pages ─────────────────────────────────────────
        logger.info(f"\n🌐 Scraping {len(source_config.get('web_pages', []))} web pages...")
        web_docs = scrape_all_pages(source_config, source_key)
        logger.info(f"   → Got {len(web_docs)} web page documents")
        all_raw_docs.extend(web_docs)

        # ── Step 2: Download and parse PDFs ──────────────────────────────────
        pdf_count = len(source_config.get("pdf_listing_pages", []))
        if pdf_count > 0:
            logger.info(f"\n📄 Scanning {pdf_count} PDF listing page(s)...")
            pdf_docs = load_pdfs_from_source(
                source_config, PDF_DIR, source_key, max_pdfs=max_pdfs_per_source
            )
            logger.info(f"   → Got {len(pdf_docs)} PDF page documents")
            all_raw_docs.extend(pdf_docs)

    logger.info(f"\n{'='*60}")
    logger.info(f"📊 Total raw documents collected: {len(all_raw_docs)}")

    if not all_raw_docs:
        logger.warning("⚠️  No documents collected. Check your internet connection or RERA URLs.")
        return {"added": 0, "docs": 0}

    # ── Step 3: Chunk ─────────────────────────────────────────────────────────
    logger.info("\n✂️  Chunking documents...")
    chunks = chunk_documents(all_raw_docs)
    logger.info(f"   → Created {len(chunks)} chunks")

    # ── Step 4: Embed + Store in ChromaDB ────────────────────────────────────
    logger.info("\n🔢 Embedding and storing in ChromaDB (this may take a while)...")
    logger.info("   (Running on CPU with sentence-transformers — be patient!)")
    added = add_chunks(chunks)

    # ── Summary ───────────────────────────────────────────────────────────────
    stats = get_stats()
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ INGESTION COMPLETE")
    logger.info(f"   New chunks added:    {added}")
    logger.info(f"   Total chunks in DB:  {stats['total_chunks']}")
    logger.info(f"   Sources:             {len(stats['sources'])}")
    logger.info(f"{'='*60}")

    return {"added": added, "docs": len(all_raw_docs), "total": stats["total_chunks"]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest RERA documents into ChromaDB")
    parser.add_argument("--max-pdfs", type=int, default=30, help="Max PDFs per source (default: 30)")
    args = parser.parse_args()
    run_ingestion(max_pdfs_per_source=args.max_pdfs)
