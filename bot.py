# -*- coding: utf-8 -*-
#!/usr/bin/env python3
import logging
import re
import os
import requests
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from pyrogram.errors import FloodWait, RPCError

# Bot credentials - get from environment variables
API_ID = int(os.getenv("API_ID", "22922577"))
API_HASH = os.getenv("API_HASH", "ff5513f0b7e10b92a940bd107e1ac32a")
BOT_TOKEN = os.getenv("BOT_TOKEN", "7859842889:AAFSn3HZFBRe48MR9LnndoVrX4WCQeo2Ulg")

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

    def format_html(self, data, cover_url=None):
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
        
        return formatted_output, cover_url

class AnimeSearch:
    def __init__(self):
        self.url = "https://graphql.anilist.co"
    
    def search_anime(self, query: str, page: int = 1, per_page: int = 10):
        query_str = '''
        query ($search: String, $page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            pageInfo {
              total
              currentPage
              lastPage
              hasNextPage
            }
            media(search: $search, type: ANIME) {
              id
              format
              title {
                romaji
                english
              }
              episodes
              status
              startDate {
                year
                month
                day
              }
              endDate {
                year
                month
                day
              }
              duration
              averageScore
              genres
              description
              siteUrl
              coverImage {
                large
                extraLarge
              }
            }
          }
        }
        '''
        variables = {"search": query, "page": page, "perPage": per_page}
        try:
            response = requests.post(self.url, json={"query": query_str, "variables": variables}, timeout=10)
            if response.status_code != 200:
                return None
            return response.json()["data"]["Page"]
        except Exception as e:
            logger.error(f"Error searching anime: {str(e)}")
            return None

    def get_anime_by_id(self, anime_id: int):
        query_str = '''
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
            format
            title {
              romaji
              english
            }
            episodes
            status
            startDate {
              year
              month
              day
            }
            endDate {
              year
              month
              day
            }
            duration
            averageScore
            genres
            description
            siteUrl
            coverImage {
              large
              extraLarge
            }
          }
        }
        '''
        variables = {"id": anime_id}
        try:
            response = requests.post(self.url, json={"query": query_str, "variables": variables}, timeout=10)
            if response.status_code != 200:
                return None
            return response.json()["data"]["Media"]
        except Exception as e:
            logger.error(f"Error getting anime by ID: {str(e)}")
            return None

class AnimeBot:
    def __init__(self):
        self.formatter = AnimeFormatter()
        self.anime_search = AnimeSearch()
        self.user_sessions = {}  # Store user search sessions
        
        # Initialize Pyrogram client
        self.app = Client(
            "anime_formatter_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            in_memory=True
        )
        
        self.setup_handlers()

    def setup_handlers(self):
        # Command handlers
        @self.app.on_message(filters.command("start") & filters.private)
        async def start_command(client, message: Message):
            help_text = """🎌 <b>Anime Formatter Bot</b> 🎌

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

Or simply send an anime title to search from AniList database!

The bot will format it with:
• Bold headings with special characters
• Truncated synopsis (max 5 lines)
• Standard quality and audio options
• Clean, professional layout
• Cover photos from AniList

<b>💠 Powered By :</b> <a href="https://t.me/Animes2u">Animes2u</a>"""
            await message.reply_text(help_text)

        # Manual format handler
        @self.app.on_message(filters.text & filters.private & filters.regex(r'‣\s*Genres\s*:'))
        async def handle_manual_format(client, message: Message):
            try:
                message_text = message.text
                logger.info(f"Processing manual format from user {message.from_user.id}")
                anime_data = self.formatter.parse_anime_info(message_text)
                if anime_data:
                    formatted_text, _ = self.formatter.format_html(anime_data)
                    await message.reply_text(formatted_text)
                    logger.info("Successfully formatted and sent anime information")
                else:
                    error_message = """❌ <b>Invalid Format</b>

Please use the correct format. Send /start to see the example format.

Make sure your message includes:
• Anime title
• All required fields (‣ Genres, ‣ Type, etc.)
• Synopsis section
• Proper line breaks between sections

Or simply send an anime title to search!"""
                    await message.reply_text(error_message)
                    logger.warning("Invalid format received")
            except Exception as e:
                logger.exception(f"Error processing message: {str(e)}")
                await message.reply_text(
                    "❌ <b>Error occurred</b>\n\nSomething went wrong while processing your message. Please try again with the correct format.\n\nUse /start to see the example."
                )

        # Search handler
        @self.app.on_message(filters.text & filters.private & ~filters.command & ~filters.regex(r'‣\s*Genres\s*:'))
        async def handle_search(client, message: Message):
            try:
                query = message.text.strip()
                user_id = message.from_user.id
                
                if len(query) < 3:
                    await message.reply_text("❌ Please enter at least 3 characters to search.")
                    return
                
                # Search anime
                result = self.anime_search.search_anime(query, page=1)
                
                if not result or not result.get("media"):
                    await message.reply_text("❌ No anime found with that name.")
                    return
                
                # Store search session
                self.user_sessions[user_id] = {
                    "query": query,
                    "current_page": 1,
                    "total_pages": result["pageInfo"]["lastPage"],
                    "results": result["media"]
                }
                
                # Create keyboard with results
                keyboard = self._create_search_keyboard(result["media"], user_id, 1, result["pageInfo"])
                
                await message.reply_text(
                    f"🎞 Found {len(result['media'])} results for '{query}':\n\nSelect an anime:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
            except Exception as e:
                logger.exception(f"Error handling search: {str(e)}")
                await message.reply_text("❌ Error searching for anime. Please try again.")

        # Callback query handler
        @self.app.on_callback_query()
        async def handle_callback_query(client, callback_query: CallbackQuery):
            data = callback_query.data
            user_id = callback_query.from_user.id
            
            try:
                if data.startswith("select_"):
                    # User selected an anime
                    anime_id = int(data.split("_")[1])
                    await self._handle_anime_selection(callback_query, anime_id)
                    
                elif data.startswith("page_"):
                    # User wants to change page
                    parts = data.split("_")
                    target_user_id = int(parts[1])
                    page_number = int(parts[2])
                    
                    if user_id != target_user_id:
                        await callback_query.answer("This search session is not yours.", show_alert=True)
                        return
                    
                    await self._handle_page_change(callback_query, user_id, page_number)
                    
            except Exception as e:
                logger.exception(f"Error handling callback: {str(e)}")
                await callback_query.answer("Error processing your request.", show_alert=True)

    def _create_search_keyboard(self, results, user_id, current_page, page_info):
        """Create inline keyboard for search results with pagination"""
        keyboard = []
        
        # Add anime buttons
        for anime in results:
            title = anime["title"]["english"] or anime["title"]["romaji"]
            format_type = anime.get("format", "Unknown")
            label = f"{title} ({format_type})"
            # Truncate if too long
            if len(label) > 50:
                label = label[:47] + "..."
            keyboard.append([InlineKeyboardButton(label, callback_data=f"select_{anime['id']}")])
        
        # Add pagination buttons
        pagination_row = []
        if current_page > 1:
            pagination_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page_{user_id}_{current_page-1}"))
        
        pagination_row.append(InlineKeyboardButton(f"Page {current_page}/{page_info['lastPage']}", callback_data="current_page"))
        
        if page_info.get("hasNextPage", False):
            pagination_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{user_id}_{current_page+1}"))
        
        if pagination_row:
            keyboard.append(pagination_row)
        
        return keyboard

    async def _handle_anime_selection(self, callback_query: CallbackQuery, anime_id: int):
        """Handle when user selects an anime from search results"""
        anime = self.anime_search.get_anime_by_id(anime_id)
        
        if not anime:
            await callback_query.message.edit_text("❌ Couldn't load anime details.")
            return
        
        # Format the anime data in the same style as manual input
        formatted_text, cover_url = self._format_anime_from_api(anime)
        
        # Send message with cover photo if available
        if cover_url:
            try:
                await callback_query.message.reply_photo(
                    photo=cover_url,
                    caption=formatted_text
                )
                await callback_query.message.edit_text("✅ Anime formatted successfully!")
            except Exception as e:
                logger.warning(f"Could not send photo, sending text only: {str(e)}")
                await callback_query.message.edit_text(formatted_text)
        else:
            await callback_query.message.edit_text(formatted_text)

    async def _handle_page_change(self, callback_query: CallbackQuery, user_id: int, page_number: int):
        """Handle pagination in search results"""
        session = self.user_sessions.get(user_id)
        if not session:
            await callback_query.message.edit_text("❌ Search session expired. Please search again.")
            return
        
        # Search for the new page
        result = self.anime_search.search_anime(session["query"], page=page_number)
        
        if not result or not result.get("media"):
            await callback_query.message.edit_text("❌ No results found for this page.")
            return
        
        # Update session
        session["current_page"] = page_number
        session["results"] = result["media"]
        self.user_sessions[user_id] = session
        
        # Create new keyboard
        keyboard = self._create_search_keyboard(result["media"], user_id, page_number, result["pageInfo"])
        
        await callback_query.message.edit_text(
            f"🎞 Found results for '{session['query']}':\n\nSelect an anime:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def _format_anime_from_api(self, anime):
        """Format anime data from API into the desired format"""
        title = anime["title"]["english"] or anime["title"]["romaji"]
        genres = ", ".join(anime.get("genres", [])) if anime.get("genres") else "Unknown"
        anime_type = anime.get("format", "Unknown")
        rating = f"{anime.get('averageScore', 'N/A')}%" if anime.get('averageScore') else "N/A"
        status = anime.get("status", "Unknown").replace("_", " ").title()
        
        # Format dates
        start_date = self._format_date(anime.get("startDate", {}))
        end_date = self._format_date(anime.get("endDate", {}))
        
        runtime = f"{anime.get('duration', 'Unknown')} min" if anime.get('duration') else "Unknown"
        episodes = anime.get("episodes", "Unknown")
        
        # Clean description
        description = anime.get("description", "No synopsis available.")
        description = re.sub(r'<.*?>', '', description)  # Remove HTML tags
        description = description.replace('\n', ' ').strip()
        
        # Get cover image URL
        cover_url = None
        if anime.get("coverImage"):
            cover_url = anime["coverImage"].get("extraLarge") or anime["coverImage"].get("large")
        
        # Use the existing formatter to format the final output
        manual_format_text = f"""{title}

‣ Genres : {genres}
‣ Type : {anime_type}
‣ Average Rating : {rating}
‣ Status : {status}
‣ First aired : {start_date}
‣ Last aired : {end_date}
‣ Runtime : {runtime}
‣ No of episodes : {episodes}

‣ Synopsis : {description}

(Source: AniList)"""
        
        # Parse and format using existing formatter
        anime_data = self.formatter.parse_anime_info(manual_format_text)
        if anime_data:
            return self.formatter.format_html(anime_data, cover_url)
        else:
            # Fallback format with proper line gap
            return f"""<b>{title}</b>
────────────────────────
<b>❃ Season :</b> 1
<b>❃ Audio :</b> ᴊᴀᴘ | ᴇɴɢ | ᴛᴇʟ | ʜɪɴ | ᴛᴀᴍ
<b>❃ Quality :</b> 480ᴘ | 720ᴘ | 1080ᴘ | 4ᴋ
<b>❃ Episodes :</b> {episodes}

<b>‣ Synopsis :</b> {self.formatter.truncate_synopsis(description)}
────────────────────────
<b>💠 Powered By :</b> <a href="https://t.me/Animes2u">Animes2u</a>""", cover_url

    def _format_date(self, date_dict):
        """Format date from API response"""
        if not date_dict or not date_dict.get("year"):
            return "Unknown"
        
        year = date_dict["year"]
        month = date_dict.get("month", 1)
        day = date_dict.get("day", 1)
        
        return f"{year}-{month:02d}-{day:02d}"

    async def run(self):
        """Run the bot"""
        logger.info("🤖 Anime Formatter Bot is starting...")
        try:
            await self.app.start()
            logger.info("Bot started successfully!")
            await idle()
        except Exception as e:
            logger.error(f"Failed to start bot: {str(e)}")
            raise
        finally:
            await self.app.stop()

def main():
    try:
        bot = AnimeBot()
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {str(e)}")
        raise

if __name__ == '__main__':
    main()
