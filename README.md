# 🏛️ RERA Discord Chat Bot

An AI-powered Discord bot that answers questions about **RERA** (Real Estate Regulatory Authority) and **MahaRERA** using official documents. Built with RAG (Retrieval-Augmented Generation) using **Google Gemini** + **ChromaDB** + **local sentence-transformers**.

> **Cost**: Only Gemini API costs. Everything else (embeddings, vector DB, hosting) is **FREE**.

---

## 📋 Table of Contents

- [Architecture](#architecture)
- [Setup](#setup)
- [Running the Bot](#running-the-bot)
- [Commands](#commands)
- [Adding More Documents](#adding-more-documents)
- [Cost Guide](#cost-guide)

---

## 🏗️ Architecture

```
Discord User
     │  @mention or /ask
     ▼
discord.py Bot (bot/main.py)
     │
     ▼
RAG Pipeline (rag/pipeline.py)
  ├── Embed question → sentence-transformers (LOCAL, FREE)
  ├── Search ChromaDB → top 5 relevant chunks (LOCAL, FREE)
  ├── Build prompt (question + context + history)
  └── Call Gemini Flash API → answer + citations (PAID, ~$0.10/day)
     │
     ▼
Discord Response (formatted embed with sources)
```

---

## ⚙️ Setup

### 1. Prerequisites

- Python 3.11+
- A Discord account + server (admin access)
- A Google AI Studio account (free)

### 2. Clone / Open the project

```bash
cd C:\Users\PC\Downloads\Rera
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> ⏱️ First install may take ~5 minutes (sentence-transformers is large)

### 4. Get your API keys

#### 🤖 Discord Bot Token
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → name it "RERA Bot"
3. Go to **Bot** tab → click **Add Bot**
4. Under **Token** → click **Reset Token** → copy it
5. Under **Privileged Gateway Intents**, enable:
   - ✅ **Message Content Intent**
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Read Messages/View Channels`, `Embed Links`, `Read Message History`
7. Copy the generated URL → open it → add bot to your server

#### 🧠 Gemini API Key (FREE tier)
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click **Create API Key** → copy it
3. Free tier: **1,500 requests/day, 15 req/min** (more than enough for a bot)

### 5. Configure environment

```bash
copy .env.example .env
```

Edit `.env`:
```env
DISCORD_BOT_TOKEN=your_discord_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
DISCORD_ADMIN_USER_IDS=your_discord_user_id_here
```

> **Get your Discord User ID**: Settings → Advanced → Enable Developer Mode → Right-click your name → Copy User ID

---

## 🚀 Running the Bot

### Step 1 — Ingest RERA Documents (do this ONCE)

```bash
python scripts/ingest.py
```

This will:
- Scrape MahaRERA and national RERA web pages
- Download PDFs from circulars/orders pages
- Parse, chunk, and embed everything into ChromaDB
- Takes **5–15 minutes** depending on your internet speed

> You can re-run this anytime to pick up new documents. It skips duplicates automatically.

### Step 2 — Start the Bot

```bash
python bot/main.py
```

You should see:
```
✅ Logged in as RERA Bot#1234 (ID: ...)
✅ Synced 7 slash commands
```

---

## 💬 Commands

| Command | Description |
|---|---|
| `/ask [question]` | Ask any RERA/MahaRERA question |
| `/search [topic]` | Search document excerpts |
| `/sources` | List all indexed documents |
| `/clear` | Clear your conversation history |
| `/help` | Show help message |
| `@RERABot [question]` | Mention the bot anywhere |

### Admin Commands

| Command | Description |
|---|---|
| `/admin ingest` | Re-ingest all RERA documents |
| `/admin stats` | Show knowledge base statistics |
| `/admin add-pdf [url] [label]` | Add a specific PDF by URL |
| `/admin clear-history` | Clear all user histories |

---

## 📚 Adding More Documents

### Add a PDF by URL (via Discord)
```
/admin add-pdf url:https://example.com/rera-circular.pdf label:MahaRERA Circular 2024
```

### Add more sources in `config.py`

Edit `RERA_SOURCES` in `config.py` to add more pages or sources:

```python
"my_custom_source": {
    "label": "My RERA Source",
    "web_pages": ["https://..."],
    "pdf_listing_pages": ["https://..."],
    "base_url": "https://...",
}
```

Then re-run: `python scripts/ingest.py`

### Add local PDFs

Place PDF files in `data/pdfs/` then run:

```bash
python -c "
from rag.ingestion.pdf_loader import parse_pdf
from rag.ingestion.chunker import chunk_documents
from rag.vectorstore import add_chunks
from pathlib import Path

docs = parse_pdf(Path('data/pdfs/my-file.pdf'), 'My Source', '')
chunks = chunk_documents(docs)
added = add_chunks(chunks)
print(f'Added {added} chunks')
"
```

---

## 💰 Cost Guide

| Item | Cost |
|---|---|
| ChromaDB (local) | **FREE** |
| sentence-transformers embeddings | **FREE** |
| discord.py | **FREE** |
| Gemini 1.5 Flash (free tier) | **FREE** up to 1,500 req/day |
| Gemini 1.5 Flash (paid) | ~$0.075 per 1M input tokens |
| Rough estimate: 100 questions/day | **~$0.05–0.15/day** |

> **Tip**: The free tier (1,500 req/day at 15 req/min) is enough for most small servers.

---

## 📁 Project Structure

```
Rera/
├── bot/
│   ├── main.py              # Bot entry point
│   ├── commands.py          # All slash commands
│   └── response_formatter.py
├── rag/
│   ├── ingestion/
│   │   ├── pdf_loader.py    # PDF download + parse
│   │   ├── web_scraper.py   # Web page scraping
│   │   └── chunker.py       # Text splitting
│   ├── vectorstore.py       # ChromaDB
│   └── pipeline.py          # RAG + Gemini
├── scripts/
│   └── ingest.py            # Run this first!
├── data/
│   ├── pdfs/                # Downloaded PDFs
│   └── chroma_db/           # Vector store (auto-created)
├── logs/                    # Log files (auto-created)
├── config.py                # All configuration
├── requirements.txt
├── .env.example
└── .env                     # YOUR API KEYS (don't commit!)
```

---

## 🔧 Troubleshooting

**Bot not responding to slash commands?**
> Wait ~1 hour after first start for Discord to propagate commands globally. Or test in a specific server by using guild-specific sync.

**`No module named 'fitz'`?**
> Run: `pip install PyMuPDF`

**Gemini rate limit error?**
> You're hitting 15 req/min. The bot has a built-in 8s cooldown per user. For high traffic, upgrade to Gemini paid tier.

**Empty knowledge base?**
> Run `python scripts/ingest.py` first before starting the bot.
