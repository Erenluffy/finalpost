# -*- coding: utf-8 -*-
#!/usr/bin/env python3
import logging
import re
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Bot credentials - get from environment variables
API_ID = '25956970'
API_HASH = '5fb73e6994d62ba1a7b8009991dd74b6'
BOT_TOKEN = os.getenv("BOT_TOKEN", "7859842889:AAG5jD89VW5xEo9qXT8J0OsB-byL5aJTqZM")

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AnimeFormatter:
    def __init__(self):
        self.input_pattern = re.compile(
            r'(?P<title>.*?)\s*\n\s*\n?'
            r'‣\s*Genres\s*:\s*(?P<genres>.*?)\s*\n'
            r'‣\s*Type\s*:\s*(?P<type>.*?)\s*\n'
            r'‣\s*Average Rating\s*:\s*(?P<rating>.*?)\s*\n'
            r'‣\s*Status\s*:\s*(?P<status>.*?)\s*\n'
            r'‣\s*First aired\s*:\s*(?P<first_aired>.*?)\s*\n'
            r'‣\s*Last aired\s*:\s*(?P<last_aired>.*?)\s*\n'
            r'‣\s*Runtime\s*:\s*(?P<runtime>.*?)\s*\n'
            r'‣\s*No of episodes\s*:\s*(?P<episodes>.*?)\s*\n\s*\n?'
            r'‣\s*Synopsis\s*:\s*(?P<synopsis>.*)',
            re.DOTALL | re.IGNORECASE
        )

    def parse_anime_info(self, text):
        text = text.strip()
        match = self.input_pattern.search(text)
        if not match:
            return None
        
        data = {k: (v.strip() if v else "") for k, v in match.groupdict().items()}
        return data

    def truncate_synopsis(self, synopsis, max_lines=5):
        if not synopsis:
            return ""
        synopsis = re.sub(r'\(Source:.*?\)', '', synopsis, flags=re.IGNORECASE | re.DOTALL).strip()
        sentences = re.split(r'(?<=[.!?])\s+', synopsis)
        result_lines = []
        current_line = ""
        max_chars_per_line = 70

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(current_line + " " + sentence) > max_chars_per_line and current_line:
                result_lines.append(current_line.strip())
                current_line = sentence
                if len(result_lines) >= max_lines:
                    break
            else:
                current_line = current_line + " " + sentence if current_line else sentence

        if current_line.strip() and len(result_lines) < max_lines:
            result_lines.append(current_line.strip())

        return " ".join(result_lines[:max_lines])

    def format_html(self, data):
        synopsis = self.truncate_synopsis(data.get('synopsis', ''))
        episodes = re.sub(r'[^\d]', '', data.get('episodes', '0')) or "0"
        formatted_output = f"""<b>{data.get('title', 'Unknown Title')}</b>
────────────────────────
<b>❃ Season :</b> 1
<b>❃ Audio :</b> ᴊᴀᴘ | ᴇɴɢ | ᴛᴇʟ | ʜɪɴ | ᴛᴀᴍ
<b>❃ Quality :</b> 480ᴘ | 720ᴘ | 1080ᴘ | 4ᴋ
<b>❃ Episodes :</b> {episodes}
<b>‣ Synopsis :</b> {synopsis}
────────────────────────
<b>💠 Powered By :</b> <a href="https://t.me/Animes2u">Animes2u</a>"""
        return formatted_output

class TelegramBot:
    def __init__(self):
        self.formatter = AnimeFormatter()
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """\U0001F38C <b>Anime Formatter Bot</b> \U0001F38C

Send anime information in this exact format:

<pre>Anime Title | Alternative Title

‣ Genres : Action, Sci-Fi
‣ Type : TV
‣ Average Rating : 82
‣ Status : FINISHED
‣ First aired : 2024-4-13
‣ Last aired : 2024-6-29
‣ Runtime : 24 minutes
‣ No of episodes : 12

‣ Synopsis : Your anime synopsis here...

(Source: Some Source)</pre>

The bot will format it with:
• Bold headings with special characters
• Truncated synopsis (max 5 lines)
• Standard quality and audio options
• Clean, professional layout

<b>💠 Powered By :</b> <a href="https://t.me/Animes2u">Animes2u</a>"""
        await update.message.reply_text(help_text, parse_mode='HTML', disable_web_page_preview=True)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            message_text = update.message.text
            logger.info(f"Processing message from user {update.effective_user.id}")
            anime_data = self.formatter.parse_anime_info(message_text)
            if anime_data:
                formatted_text = self.formatter.format_html(anime_data)
                await update.message.reply_text(
                    formatted_text,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                logger.info("Successfully formatted and sent anime information")
            else:
                error_message = """\u274C <b>Invalid Format</b>

Please use the correct format. Send /start to see the example format.

Make sure your message includes:
• Anime title
• All required fields (‣ Genres, ‣ Type, etc.)
• Synopsis section
• Proper line breaks between sections"""
                await update.message.reply_text(error_message, parse_mode='HTML')
                logger.warning("Invalid format received")
        except Exception as e:
            logger.exception(f"Error processing message: {str(e)}")
            await update.message.reply_text(
                "\u274C <b>Error occurred</b>\n\nSomething went wrong while processing your message. Please try again with the correct format.\n\nUse /start to see the example.",
                parse_mode='HTML'
            )

    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    def run_polling(self):
        """Run the bot in polling mode (for development)"""
        logger.info("🤖 Anime Formatter Bot is starting in polling mode...")
        try:
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
        except Exception as e:
            logger.error(f"Failed to start bot: {str(e)}")
            raise

    async def run_webhook(self):
        """Run the bot in webhook mode (for production)"""
        logger.info("🤖 Anime Formatter Bot is starting in webhook mode...")
        
        # Get port from environment variable or default to 8000 for Koyeb
        port = int(os.environ.get('PORT', 8000))
        
        # Set webhook URL - you'll need to set KOYEB_APP_URL in your environment variables
        webhook_url = os.getenv('KOYEB_APP_URL', '')
        if not webhook_url:
            logger.error("KOYEB_APP_URL environment variable is not set")
            return
            
        webhook_url = f"{webhook_url}/{BOT_TOKEN}"
        
        try:
            # Set webhook
            await self.application.bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True
            )
            
            logger.info(f"Webhook set to: {webhook_url}")
            
            # Start the webhook server
            await self.application.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path=BOT_TOKEN,
                webhook_url=webhook_url,
                drop_pending_updates=True
            )
        except Exception as e:
            logger.error(f"Failed to start webhook: {str(e)}")
            raise

# For Koyeb deployment - create a simple HTTP server for health checks
from aiohttp import web

async def health_check(request):
    return web.Response(text="Bot is running!")

def create_health_check_app():
    app = web.Application()
    app.router.add_get('/health', health_check)
    return app

async def run_health_check_server():
    """Run a simple health check server for Koyeb"""
    app = create_health_check_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Use a different port for health checks (8080)
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Health check server started on port 8080")

async def main():
    # Check if we're running in production (Koyeb)
    is_production = os.getenv('KOYEB_APP_URL') is not None
    
    bot = TelegramBot()
    
    if is_production:
        # In production, run both webhook and health check server
        import asyncio
        await asyncio.gather(
            bot.run_webhook(),
            run_health_check_server()
        )
    else:
        # In development, use polling
        bot.run_polling()

if __name__ == '__main__':
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {str(e)}")
        raise
