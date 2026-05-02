"""
rag/ingestion/chunker.py
Splits raw document text into overlapping chunks ready for embedding.
"""
import logging
import hashlib
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config import CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)


def _make_chunk_id(text: str, metadata: dict) -> str:
    """Create a stable unique ID for a chunk."""
    raw = f"{metadata.get('source_url','')}-{metadata.get('page','')}-{text[:100]}"
    return hashlib.md5(raw.encode()).hexdigest()


def chunk_documents(raw_docs: list[dict]) -> list[dict]:
    """
    Split a list of raw document dicts into smaller overlapping chunks.

    Input:  [{"text": "...", "metadata": {...}}, ...]
    Output: [{"id": "...", "text": "...", "metadata": {...}}, ...]
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "। ", ". ", " ", ""],  # Handles Hindi/Marathi too
        length_function=len,
    )

    chunks = []
    for doc in raw_docs:
        text     = doc["text"]
        metadata = doc.get("metadata", {})

        split_texts = splitter.split_text(text)
        for i, chunk_text in enumerate(split_texts):
            chunk_text = chunk_text.strip()
            if len(chunk_text) < 30:  # Skip tiny fragments
                continue

            chunk_metadata = {
                **metadata,
                "chunk_index": i,
                "chunk_count": len(split_texts),
            }
            chunk_id = _make_chunk_id(chunk_text, chunk_metadata)
            chunks.append({
                "id":       chunk_id,
                "text":     chunk_text,
                "metadata": chunk_metadata,
            })

    logger.info(f"Created {len(chunks)} chunks from {len(raw_docs)} documents")
    return chunks
