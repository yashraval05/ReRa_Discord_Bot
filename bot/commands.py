"""
bot/commands.py
All Discord slash commands for the RERA bot.
"""
import time
import logging
import asyncio
import discord
from discord import app_commands
from config import DISCORD_ADMIN_USER_IDS, RATE_LIMIT_SECONDS
from rag.pipeline import answer_question
from rag.vectorstore import search, get_stats
from bot.response_formatter import (
    build_answer_embed,
    build_search_embed,
    build_stats_embed,
    build_error_embed,
    build_processing_embed,
)

logger = logging.getLogger(__name__)

# ─── Per-user state ───────────────────────────────────────────────────────────
user_history:     dict[int, list[dict]] = {}   # user_id -> conversation history
user_last_call:   dict[int, float]      = {}   # user_id -> timestamp


def _is_admin(user_id: int) -> bool:
    return str(user_id) in DISCORD_ADMIN_USER_IDS


def _check_rate_limit(user_id: int) -> float:
    """Returns 0 if ok, else the seconds remaining to wait."""
    last = user_last_call.get(user_id, 0)
    elapsed = time.time() - last
    if elapsed < RATE_LIMIT_SECONDS:
        return round(RATE_LIMIT_SECONDS - elapsed, 1)
    return 0


def _update_history(user_id: int, role: str, content: str):
    if user_id not in user_history:
        user_history[user_id] = []
    user_history[user_id].append({"role": role, "content": content})
    # Keep last 10 messages (5 exchanges)
    if len(user_history[user_id]) > 10:
        user_history[user_id] = user_history[user_id][-10:]


def register_commands(tree: app_commands.CommandTree):
    """Register all slash commands on the bot's command tree."""

    # ── /ask ─────────────────────────────────────────────────────────────────
    @tree.command(
        name="ask",
        description="Ask a RERA or MahaRERA question. Get an AI answer from official documents."
    )
    @app_commands.describe(question="Your RERA question (e.g. 'What are the penalties for delayed possession?')")
    async def ask_command(interaction: discord.Interaction, question: str):
        user_id = interaction.user.id

        # Rate limit check
        wait = _check_rate_limit(user_id)
        if wait > 0:
            await interaction.response.send_message(
                f"⏳ Please wait **{wait}s** before asking again.",
                ephemeral=True
            )
            return

        # Acknowledge immediately (Discord requires response within 3s)
        await interaction.response.defer(thinking=True)

        user_last_call[user_id] = time.time()
        history = user_history.get(user_id, [])

        try:
            # Run the blocking RAG pipeline in a thread pool
            loop   = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: answer_question(question, history)
            )

            # Update conversation history
            _update_history(user_id, "user", question)
            _update_history(user_id, "assistant", result["answer"][:500])

            embeds = build_answer_embed(question, result, str(interaction.user))
            await interaction.followup.send(embeds=embeds[:3])   # Discord max 10 embeds

        except Exception as e:
            logger.exception(f"Error in /ask command: {e}")
            await interaction.followup.send(
                embed=build_error_embed(f"Something went wrong: {e}")
            )

    # ── /search ───────────────────────────────────────────────────────────────
    @tree.command(
        name="search",
        description="Search the RERA knowledge base and see matching document excerpts."
    )
    @app_commands.describe(query="Topic or keyword to search (e.g. 'promoter registration')")
    async def search_command(interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)

        try:
            loop   = asyncio.get_event_loop()
            chunks = await loop.run_in_executor(None, lambda: search(query, top_k=4))
            embed  = build_search_embed(query, chunks)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.exception(f"Error in /search: {e}")
            await interaction.followup.send(embed=build_error_embed(str(e)))

    # ── /sources ──────────────────────────────────────────────────────────────
    @tree.command(
        name="sources",
        description="List all RERA sources indexed in the knowledge base."
    )
    async def sources_command(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            loop  = asyncio.get_event_loop()
            stats = await loop.run_in_executor(None, get_stats)
            embed = build_stats_embed(stats)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(embed=build_error_embed(str(e)))

    # ── /clear ────────────────────────────────────────────────────────────────
    @tree.command(
        name="clear",
        description="Clear your conversation history with the bot."
    )
    async def clear_command(interaction: discord.Interaction):
        user_history.pop(interaction.user.id, None)
        await interaction.response.send_message(
            "✅ Your conversation history has been cleared.", ephemeral=True
        )

    # ── /help ─────────────────────────────────────────────────────────────────
    @tree.command(
        name="help",
        description="Show how to use the RERA bot."
    )
    async def help_command(interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏛️ RERA Bot — Help",
            description=(
                "I'm an AI assistant specialized in Indian Real Estate laws.\n"
                "I answer questions using **official RERA & MahaRERA documents**."
            ),
            color=discord.Color.from_rgb(0, 180, 120),
        )
        embed.add_field(
            name="Commands",
            value=(
                "**`/ask [question]`** — Ask any RERA/MahaRERA question\n"
                "**`/search [topic]`** — Search document excerpts directly\n"
                "**`/sources`** — See all indexed documents\n"
                "**`/clear`** — Clear your chat history\n"
                "**`/help`** — Show this message\n"
                "\n*Admins only:*\n"
                "**`/admin ingest`** — Re-ingest RERA documents\n"
                "**`/admin stats`** — Detailed KB stats\n"
                "**`/admin add-pdf`** — Add a PDF by URL"
            ),
            inline=False,
        )
        embed.add_field(
            name="💡 Tips",
            value=(
                "• You can also **@mention** me anywhere in the server\n"
                "• I remember your last 5 messages for follow-up questions\n"
                "• I always cite the source document for my answers"
            ),
            inline=False,
        )
        embed.set_footer(text="Powered by Gemini Flash + ChromaDB + MahaRERA/RERA documents")
        await interaction.response.send_message(embed=embed)

    # ── /admin (group) ────────────────────────────────────────────────────────
    admin_group = app_commands.Group(name="admin", description="Admin commands (restricted)")

    @admin_group.command(name="stats", description="Show detailed knowledge base statistics.")
    async def admin_stats(interaction: discord.Interaction):
        if not _is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        stats = await asyncio.get_event_loop().run_in_executor(None, get_stats)
        embed = build_stats_embed(stats)
        await interaction.followup.send(embed=embed)

    @admin_group.command(name="ingest", description="Re-ingest all RERA documents from the web.")
    async def admin_ingest(interaction: discord.Interaction):
        if not _is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        await interaction.response.send_message(
            "⏳ Starting RERA ingestion... This may take **5–15 minutes**.\n"
            "I'll DM you when done.", ephemeral=True
        )

        async def _run_ingest():
            try:
                from scripts.ingest import run_ingestion
                loop = asyncio.get_event_loop()
                stats = await loop.run_in_executor(None, run_ingestion)
                try:
                    await interaction.user.send(
                        f"✅ **Ingestion complete!**\n"
                        f"📦 Chunks added: **{stats.get('added', 0)}**\n"
                        f"📄 Documents processed: **{stats.get('docs', 0)}**"
                    )
                except Exception:
                    pass  # DM might be disabled
            except Exception as e:
                logger.exception("Ingestion error")
                try:
                    await interaction.user.send(f"❌ Ingestion failed: {e}")
                except Exception:
                    pass

        asyncio.create_task(_run_ingest())

    @admin_group.command(name="add-pdf", description="Add a PDF to the knowledge base by URL.")
    @app_commands.describe(url="Direct PDF URL", label="A short label for this document")
    async def admin_add_pdf(interaction: discord.Interaction, url: str, label: str = "Manual Upload"):
        if not _is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        try:
            from pathlib import Path
            from config import PDF_DIR
            from rag.ingestion.pdf_loader import download_pdf, parse_pdf
            from rag.ingestion.chunker import chunk_documents
            from rag.vectorstore import add_chunks

            loop = asyncio.get_event_loop()

            def _ingest_one():
                path = download_pdf(url, PDF_DIR, label)
                if not path:
                    return 0
                docs   = parse_pdf(path, source_label=label, source_url=url)
                chunks = chunk_documents(docs)
                return add_chunks(chunks)

            added = await loop.run_in_executor(None, _ingest_one)
            await interaction.followup.send(
                f"✅ Added **{added}** chunks from:\n📄 {label}\n🔗 {url}"
            )
        except Exception as e:
            logger.exception("Error adding PDF")
            await interaction.followup.send(embed=build_error_embed(str(e)))

    @admin_group.command(name="clear-history", description="Clear ALL users' conversation history.")
    async def admin_clear_history(interaction: discord.Interaction):
        if not _is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        user_history.clear()
        await interaction.response.send_message("✅ All user conversation histories cleared.")

    tree.add_command(admin_group)
