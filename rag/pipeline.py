"""
rag/pipeline.py
Core RAG pipeline: query → retrieve → Gemini answer.

Uses Gemini's OpenAI-compatible endpoint — just the standard `openai` SDK
pointed at Google's API. No extra Google SDK required!

Endpoint: https://generativelanguage.googleapis.com/v1beta/openai/
Docs: https://ai.google.dev/gemini-api/docs/openai
"""
import logging
from openai import OpenAI
from config import GEMINI_API_KEY, GEMINI_MODEL, TOP_K_RESULTS
from rag.vectorstore import search

logger = logging.getLogger(__name__)

# ─── Gemini via OpenAI-compatible client ─────────────────────────────────────
_client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

# ─── Relevance threshold ─────────────────────────────────────────────────────
MIN_RELEVANCE_SCORE = 0.30   # Below this → "I don't know" response

# ─── System prompt ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are RERABot, an expert assistant on Indian Real Estate laws.
You ONLY answer questions using the RERA (Real Estate Regulatory Authority) documents provided below.

Rules:
1. Answer ONLY from the provided document excerpts. Do NOT use outside knowledge.
2. If the answer is not in the documents, say: "I don't have information about this in my RERA knowledge base. Please consult the official RERA portal."
3. Always cite the source document at the end of your answer.
4. For legal/regulatory matters, recommend users verify with an official RERA authority.
5. Be concise, clear, and helpful.
6. Format your answer using Discord markdown (bold, bullet points, etc.)."""


def _build_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a context string for the LLM."""
    if not chunks:
        return "No relevant documents found."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        meta   = chunk["metadata"]
        source = meta.get("source", "RERA")
        page   = f" | Page {meta['page']}" if "page" in meta else ""
        url    = meta.get("source_url", "")
        ref    = f"[Source {i}: {source}{page}]"
        if url:
            ref += f" ({url})"
        parts.append(f"{ref}\n{chunk['text']}")

    return "\n\n---\n\n".join(parts)


def _build_messages(question: str, context: str, history: list[dict]) -> list[dict]:
    """Build the OpenAI-format messages list (system + history + user)."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Inject conversation history (last 6 messages)
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Final user message with retrieved context
    user_content = (
        f"## RERA Document Excerpts\n{context}\n\n"
        f"## My Question\n{question}"
    )
    messages.append({"role": "user", "content": user_content})
    return messages


def _format_sources(chunks: list[dict]) -> list[str]:
    """Extract formatted source citations."""
    seen    = set()
    sources = []
    for chunk in chunks:
        meta = chunk["metadata"]
        src  = meta.get("source", "RERA")
        url  = meta.get("source_url", "")
        key  = f"{src}|{url}"
        if key not in seen:
            seen.add(key)
            label = f"📄 **{src}**"
            if url:
                label += f"\n   🔗 {url}"
            sources.append(label)
    return sources


def answer_question(
    question: str,
    history:  list[dict] | None = None,
    top_k:    int = TOP_K_RESULTS,
) -> dict:
    """
    Full RAG pipeline: retrieve → answer with Gemini (via OpenAI SDK).

    Returns:
    {
        "answer":      str,
        "sources":     list[str],
        "confident":   bool,
        "chunks_used": int,
    }
    """
    history = history or []

    # ── Step 1: Retrieve relevant chunks ──────────────────────────────────────
    chunks = search(question, top_k=top_k)

    if not chunks:
        return {
            "answer":      "⚠️ My RERA knowledge base is empty. Please ask an admin to run `/admin ingest` first.",
            "sources":     [],
            "confident":   False,
            "chunks_used": 0,
        }

    relevant  = [c for c in chunks if c["relevance"] >= MIN_RELEVANCE_SCORE]
    confident = len(relevant) > 0

    # Use relevant chunks if any, otherwise fall back to top results with warning
    context_chunks = relevant if relevant else chunks[:2]

    # ── Step 2: Build messages ────────────────────────────────────────────────
    context  = _build_context(context_chunks)
    messages = _build_messages(question, context, history)

    # ── Step 3: Call Gemini via OpenAI-compatible endpoint ────────────────────
    try:
        response = _client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=messages,
            temperature=0.2,        # Low = factual, less creative
            max_tokens=1024,
        )
        answer = response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return {
            "answer":      f"❌ Error calling Gemini API: {e}\nPlease check your API key and quota.",
            "sources":     [],
            "confident":   False,
            "chunks_used": 0,
        }

    # ── Step 4: Confidence warning ────────────────────────────────────────────
    if not confident:
        answer = "⚠️ *Low confidence — limited relevant docs found.*\n\n" + answer

    return {
        "answer":      answer,
        "sources":     _format_sources(context_chunks),
        "confident":   confident,
        "chunks_used": len(context_chunks),
    }
