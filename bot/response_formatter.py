"""
bot/response_formatter.py
Formats RAG answers into Discord-friendly embeds and messages.
"""
import discord
from config import MAX_DISCORD_MSG_LENGTH


def _split_message(text: str, limit: int = MAX_DISCORD_MSG_LENGTH) -> list[str]:
    """Split long text into Discord-safe chunks."""
    if len(text) <= limit:
        return [text]

    parts = []
    while len(text) > limit:
        # Try to split at a newline near the limit
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        parts.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        parts.append(text)
    return parts


def build_answer_embed(
    question: str,
    result:   dict,
    username: str,
) -> list[discord.Embed]:
    """
    Build Discord Embed(s) for a RAG answer.
    Returns a list of embeds (multiple if answer is very long).
    """
    answer    = result["answer"]
    sources   = result.get("sources", [])
    confident = result.get("confident", True)

    # Color: green = confident, orange = low confidence, red = error
    if "❌" in answer:
        color = discord.Color.red()
    elif confident:
        color = discord.Color.from_rgb(0, 180, 120)   # RERA green
    else:
        color = discord.Color.orange()

    # Split long answers
    answer_parts = _split_message(answer, limit=1900)

    embeds = []
    for i, part in enumerate(answer_parts):
        embed = discord.Embed(
            description=part,
            color=color,
        )

        if i == 0:
            # First embed gets the title and question
            short_q = question[:200] + "..." if len(question) > 200 else question
            embed.title = f"🏛️ RERA Assistant"
            embed.add_field(name="❓ Question", value=f"> {short_q}", inline=False)

        if i == len(answer_parts) - 1 and sources:
            # Last embed gets the sources
            sources_text = "\n".join(sources[:5])   # Max 5 sources
            if len(sources_text) > 1000:
                sources_text = sources_text[:997] + "..."
            embed.add_field(name="📚 Sources", value=sources_text, inline=False)

        embed.set_footer(
            text=f"Asked by {username} • Powered by Gemini + RERA Knowledge Base"
        )
        embeds.append(embed)

    return embeds


def build_search_embed(query: str, chunks: list[dict]) -> discord.Embed:
    """Build an embed showing top search results (without LLM)."""
    embed = discord.Embed(
        title=f"🔍 RERA Knowledge Base Search",
        description=f"Results for: **{query[:100]}**",
        color=discord.Color.blurple(),
    )

    if not chunks:
        embed.add_field(name="No results", value="Nothing found for your query.", inline=False)
        return embed

    for i, chunk in enumerate(chunks[:4], 1):
        meta      = chunk["metadata"]
        source    = meta.get("source", "RERA")
        relevance = int(chunk["relevance"] * 100)
        snippet   = chunk["text"][:300].replace("\n", " ") + "..."

        embed.add_field(
            name=f"Result {i} — {source} ({relevance}% match)",
            value=snippet,
            inline=False,
        )

    return embed


def build_stats_embed(stats: dict) -> discord.Embed:
    """Build a knowledge base stats embed."""
    embed = discord.Embed(
        title="📊 RERA Knowledge Base Stats",
        color=discord.Color.from_rgb(0, 150, 200),
    )
    embed.add_field(name="📦 Total Chunks",    value=str(stats["total_chunks"]), inline=True)
    embed.add_field(name="🧠 Embedding Model", value=stats["embedding_model"],   inline=True)

    if stats["sources"]:
        sources_text = "\n".join(f"• {s}" for s in sorted(stats["sources"])[:15])
        embed.add_field(name="📂 Sources Indexed", value=sources_text or "None", inline=False)

    if stats["doc_types"]:
        embed.add_field(
            name="📄 Document Types",
            value=", ".join(stats["doc_types"]),
            inline=True
        )

    return embed


def build_error_embed(message: str) -> discord.Embed:
    return discord.Embed(
        title="❌ Error",
        description=message,
        color=discord.Color.red(),
    )


def build_processing_embed(question: str) -> discord.Embed:
    """Shown while the bot is thinking."""
    short_q = question[:150] + "..." if len(question) > 150 else question
    return discord.Embed(
        title="🔄 Searching RERA Knowledge Base...",
        description=f"> {short_q}\n\n*Please wait a moment...*",
        color=discord.Color.greyple(),
    )
