"""
rag/vectorstore.py
ChromaDB vector store with local sentence-transformer embeddings (FREE).
"""
import logging
from typing import Optional
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from config import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL, TOP_K_RESULTS

logger = logging.getLogger(__name__)

# ─── Singleton client & collection ───────────────────────────────────────────
_client:     Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection]       = None


def _get_embedding_function():
    return SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
        device="cpu",           # CPU-only, no GPU needed
        normalize_embeddings=True,
    )


def get_collection() -> chromadb.Collection:
    """Return (or create) the shared ChromaDB collection."""
    global _client, _collection
    if _collection is not None:
        return _collection

    logger.info(f"🗃️  Connecting to ChromaDB at {CHROMA_DIR} ...")
    _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    _collection = _client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(f"✅ Collection '{COLLECTION_NAME}' ready — {_collection.count()} chunks stored")
    return _collection


def add_chunks(chunks: list[dict]) -> int:
    """
    Add chunks to the vector store. Skips duplicates (by ID).
    Returns number of newly added chunks.
    """
    if not chunks:
        return 0

    collection = get_collection()

    # Get existing IDs to avoid duplicates
    existing_ids = set(collection.get(include=[])["ids"])

    new_chunks = [c for c in chunks if c["id"] not in existing_ids]
    if not new_chunks:
        logger.info("No new chunks to add (all duplicates)")
        return 0

    ids       = [c["id"]       for c in new_chunks]
    documents = [c["text"]     for c in new_chunks]
    metadatas = [c["metadata"] for c in new_chunks]

    # ChromaDB auto-embeds via the embedding_function we set
    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    logger.info(f"✅ Added {len(new_chunks)} new chunks (skipped {len(chunks) - len(new_chunks)} duplicates)")
    return len(new_chunks)


def search(query: str, top_k: int = TOP_K_RESULTS) -> list[dict]:
    """
    Semantic search over stored RERA chunks.
    Returns: [{"text": ..., "metadata": ..., "distance": ...}, ...]
    """
    collection = get_collection()

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for text, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append({
            "text":      text,
            "metadata":  meta,
            "distance":  dist,          # Lower = more similar (cosine)
            "relevance": 1 - dist,      # 0–1 score
        })

    return output


def get_stats() -> dict:
    """Return stats about the knowledge base."""
    collection = get_collection()
    count = collection.count()

    # Get unique sources
    if count > 0:
        all_meta  = collection.get(include=["metadatas"])["metadatas"]
        sources   = list({m.get("source", "Unknown") for m in all_meta})
        doc_types = list({m.get("doc_type", "unknown") for m in all_meta})
    else:
        sources   = []
        doc_types = []

    return {
        "total_chunks": count,
        "sources":      sources,
        "doc_types":    doc_types,
        "embedding_model": EMBEDDING_MODEL,
        "collection":   COLLECTION_NAME,
    }


def clear_collection():
    """⚠️ Delete all data from the collection."""
    global _collection
    collection = get_collection()
    collection.delete(where={"doc_type": {"$in": ["pdf", "webpage"]}})
    logger.warning("🗑️  Cleared collection")
