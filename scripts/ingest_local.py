import sys
import json
import logging
from pathlib import Path

# Make sure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATA_DIR, PDF_DIR, RERA_SOURCES
from rag.ingestion.pdf_loader import parse_pdf
from rag.ingestion.chunker import chunk_documents
from rag.vectorstore import add_chunks, get_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ingest_local")

def run_local_ingestion():
    logger.info("=" * 60)
    logger.info("🚀 Starting Local Data Ingestion (Parsing & Embedding)")
    logger.info("=" * 60)

    all_raw_docs = []
    
    # ── Step 1: Load Scraped Web Data from JSON ──────────────────────────────
    web_data_file = DATA_DIR / "web_scraped_data.json"
    if web_data_file.exists():
        logger.info("\n🌐 Loading pre-scraped web data...")
        with open(web_data_file, "r", encoding="utf-8") as f:
            web_docs = json.load(f)
            all_raw_docs.extend(web_docs)
            logger.info(f"   → Loaded {len(web_docs)} web page documents")
    else:
        logger.warning(f"⚠️  {web_data_file.name} not found! Did you copy it over?")

    # ── Step 2: Parse Downloaded PDFs ────────────────────────────────────────
    logger.info("\n📄 Parsing local PDFs in data/pdfs/ ...")
    pdf_docs = []
    
    for pdf_file in PDF_DIR.glob("*.pdf"):
        # We try to match the source from the filename, or just give a generic label
        source_label = "Local PDF"
        docs = parse_pdf(pdf_file, source_label=source_label)
        pdf_docs.extend(docs)
        
    logger.info(f"   → Parsed {len(pdf_docs)} PDF pages from local directory")
    all_raw_docs.extend(pdf_docs)

    if not all_raw_docs:
        logger.error("❌ No documents found to ingest! Check your data/ folder.")
        return

    # ── Step 3: Chunk ────────────────────────────────────────────────────────
    logger.info("\n✂️  Chunking documents...")
    chunks = chunk_documents(all_raw_docs)
    logger.info(f"   → Created {len(chunks)} chunks")

    # ── Step 4: Embed + Store in ChromaDB ────────────────────────────────────
    logger.info("\n🔢 Embedding and storing in ChromaDB (this may take a while)...")
    logger.info("   (Running on CPU with sentence-transformers — be patient!)")
    added = add_chunks(chunks)

    # ── Summary ──────────────────────────────────────────────────────────────
    stats = get_stats()
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ INGESTION COMPLETE")
    logger.info(f"   New chunks added:    {added}")
    logger.info(f"   Total chunks in DB:  {stats['total_chunks']}")
    logger.info(f"   Sources:             {len(stats['sources'])}")
    logger.info(f"{'='*60}")

if __name__ == "__main__":
    run_local_ingestion()
