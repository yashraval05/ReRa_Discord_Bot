"""
config.py - Central configuration for RERA Discord Bot
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
DATA_DIR  = BASE_DIR / "data"
PDF_DIR   = DATA_DIR / "pdfs"
CHROMA_DIR = DATA_DIR / "chroma_db"
LOG_DIR   = BASE_DIR / "logs"

# Create dirs if they don't exist
for d in [DATA_DIR, PDF_DIR, CHROMA_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Discord ─────────────────────────────────────────────────────────────────
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_ADMIN_USER_IDS = [
    uid.strip()
    for uid in os.getenv("DISCORD_ADMIN_USER_IDS", "").split(",")
    if uid.strip()
]

# ─── Gemini ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# ─── RAG ─────────────────────────────────────────────────────────────────────
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"   # Fast, free, CPU-friendly
COLLECTION_NAME  = "rera_knowledge_base"
CHUNK_SIZE       = 1000                  # Characters per chunk
CHUNK_OVERLAP    = 150                   # Overlap between chunks
TOP_K_RESULTS    = int(os.getenv("TOP_K_RESULTS", "5"))

# ─── Bot Behaviour ───────────────────────────────────────────────────────────
MAX_HISTORY_MESSAGES   = 6    # Last N messages kept per user (user+bot pairs)
RATE_LIMIT_SECONDS     = 8    # Minimum seconds between answers per user
MAX_DISCORD_MSG_LENGTH = 1900 # Safe Discord message length

# ─── RERA Data Sources ───────────────────────────────────────────────────────
RERA_SOURCES = {

    # ── MahaRERA (Maharashtra) ─────────────────────────────────────────────
    "maharera": {
        "label": "MahaRERA (Maharashtra)",
        "web_pages": [
            "https://maharera.maharashtra.gov.in/faq",
            "https://maharera.maharashtra.gov.in/about-act",
            "https://maharera.maharashtra.gov.in/maha-rera-act-rules",
            "https://maharera.maharashtra.gov.in/forms",
            "https://maharera.maharashtra.gov.in/registration-fees",
        ],
        # Pages that list PDF links — scraper will find and download them
        "pdf_listing_pages": [
            "https://maharera.maharashtra.gov.in/circulars",
            "https://maharera.maharashtra.gov.in/orders",
            "https://maharera.maharashtra.gov.in/judgements",
        ],
        "base_url": "https://maharera.maharashtra.gov.in",
    },

    # ── National / General RERA ────────────────────────────────────────────
    "rera_national": {
        "label": "National RERA (MoHUA)",
        "web_pages": [
            "https://rera.gov.in/",
            "https://rera.gov.in/about-rera",
            "https://rera.gov.in/real-estate-act",
        ],
        "pdf_listing_pages": [
            "https://rera.gov.in/rules-regulations",
            "https://rera.gov.in/advisory-committee",
        ],
        "base_url": "https://rera.gov.in",
    },
}
