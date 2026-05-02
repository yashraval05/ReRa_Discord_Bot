"""
bot/main.py
Discord bot entry point — handles events and @mention responses.
"""
import asyncio
import logging
import sys
import discord
from discord import app_commands
from config import DISCORD_BOT_TOKEN, RATE_LIMIT_SECONDS
from bot.commands import register_commands, user_history, user_last_call, _check_rate_limit, _update_history
from bot.response_formatter import build_answer_embed, build_error_embed
from rag.pipeline import answer_question

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/rera_bot.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("rera_bot")


# ─── Bot class ────────────────────────────────────────────────────────────────
class RERABot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True          # Needed for @mention reading
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self._synced = False

    async def setup_hook(self):
        """Called before the bot connects — registers slash commands."""
        register_commands(self.tree)
        logger.info("Slash commands registered")

    async def on_ready(self):
        logger.info(f"✅ Logged in as {self.user} (ID: {self.user.id})")

        # Sync slash commands once
        if not self._synced:
            synced = await self.tree.sync()
            self._synced = True
            logger.info(f"✅ Synced {len(synced)} slash commands")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="/ask your RERA question"
            )
        )

    async def on_message(self, message: discord.Message):
        """Handle @mention messages as /ask queries."""
        # Ignore self and bots
        if message.author.bot or message.author == self.user:
            return

        # Only respond to @mentions
        if self.user not in message.mentions:
            return

        # Strip the @mention from the message
        question = message.content
        for mention_str in [f"<@{self.user.id}>", f"<@!{self.user.id}>"]:
            question = question.replace(mention_str, "").strip()

        if not question:
            await message.reply(
                "👋 Hi! Ask me a RERA question, e.g.:\n"
                "*`@RERABot What are the penalties for delayed possession?`*\n\n"
                "Or use **`/help`** to see all commands.",
                mention_author=False
            )
            return

        # Rate limit
        user_id = message.author.id
        wait = _check_rate_limit(user_id)
        if wait > 0:
            await message.reply(
                f"⏳ Please wait **{wait}s** before asking again.",
                mention_author=False
            )
            return

        # Show typing indicator while processing
        async with message.channel.typing():
            import time
            user_last_call[user_id] = time.time()
            history = user_history.get(user_id, [])

            try:
                loop   = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: answer_question(question, history)
                )

                _update_history(user_id, "user", question)
                _update_history(user_id, "assistant", result["answer"][:500])

                embeds = build_answer_embed(question, result, str(message.author))
                await message.reply(embeds=embeds[:3], mention_author=False)

            except Exception as e:
                logger.exception(f"Error handling mention: {e}")
                await message.reply(
                    embed=build_error_embed(f"Something went wrong: {e}"),
                    mention_author=False
                )


# ─── Run ─────────────────────────────────────────────────────────────────────
def main():
    if not DISCORD_BOT_TOKEN:
        logger.error("❌ DISCORD_BOT_TOKEN is not set! Please edit your .env file.")
        sys.exit(1)

    bot = RERABot()
    try:
        bot.run(DISCORD_BOT_TOKEN, log_handler=None)
    except discord.LoginFailure:
        logger.error("❌ Invalid Discord bot token. Please check your .env file.")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")


if __name__ == "__main__":
    main()
