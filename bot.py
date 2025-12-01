
import logging
import re
import os
import requests
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN", "7859842889:AAFSn3HZFBRe48MR9LnndoVrX4WCQeo2Ulg")

GRAPHQL_API_URL = "https://animmes2uapi.vercel.app/api/graphql"

ANILIST_IMG_CDN = "https://img.anili.st"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AnimeFormatter:
    def __init__(self):
        self.input_pattern = re.compile(
            r'(?P<title>.*?)\s*\n\s*\n?'
            r'[‣•]\s*Genres\s*:\s*(?P<genres>.*?)\s*\n'
            r'[‣•]\s*Type\s*:\s*(?P<type>.*?)\s*\n'
            r'[‣•]\s*Average Rating\s*:\s*(?P<rating>.*?)\s*\n'
            r'[‣•]\s*Status\s*:\s*(?P<status>.*?)\s*\n'
            r'[‣•]\s*First aired\s*:\s*(?P<first_aired>.*?)\s*\n'
            r'[‣•]\s*Last aired\s*:\s*(?P<last_aired>.*?)\s*\n'
            r'[‣•]\s*Runtime\s*:\s*(?P<runtime>.*?)\s*\n'
            r'[‣•]\s*No of episodes\s*:\s*(?P<episodes>.*?)\s*\n\s*\n?'
            r'[‣•]\s*Synopsis\s*:\s*(?P<synopsis>.*)',
            re.DOTALL | re.IGNORECASE
        )

    def parse_anime_info(self, text):
        text = text.strip()
        match = self.input_pattern.search(text)
        if not match:
            return None

        data = {k: (v.strip() if v else "") for k, v in match.groupdict().items()}
        return data
    def extract_episode_count(self, episodes_text):
        """Extract episode count from text, handling various formats"""
        if not episodes_text:
            return "—"
        
        # Try to find numbers in the text
        numbers = re.findall(r'\d+', episodes_text)
        if numbers:
            # Use the last number found (most likely the episode count)
            return numbers[-1]
        
        # Check for common patterns
        if re.search(r'\b(ongoing|airing|tba)\b', episodes_text, re.IGNORECASE):
            return "—"
        
        return "—"
    def convert_to_small_caps(self, text):
        """Convert text to small caps style for synopsis"""
        if not text:
            return ""
        
        # Small caps mapping
        small_caps_map = {
            'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ',
            'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ',
            'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ',
            's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
            'y': 'ʏ', 'z': 'ᴢ',
            'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ғ',
            'G': 'ɢ', 'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ',
            'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ',
            'S': 's', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x',
            'Y': 'ʏ', 'Z': 'ᴢ'
        }
        
        result = []
        for char in text:
            if char in small_caps_map:
                result.append(small_caps_map[char])
            else:
                result.append(char)
        
        return ''.join(result)

    def truncate_synopsis(self, synopsis, max_chars=500):
        """Truncate synopsis to fit in blockquote"""
        if not synopsis:
            return ""
        
        # Clean source references
        synopsis = re.sub(r'\(Source:.*?\)', '', synopsis, flags=re.IGNORECASE | re.DOTALL).strip()
        
        # Truncate if too long
        if len(synopsis) > max_chars:
            synopsis = synopsis[:max_chars].rstrip() + "..."
        
        # Convert to small caps
        return self.convert_to_small_caps(synopsis)


   def format_html(self, data, cover_url=None, anime_id=None):
        title = data.get('title', 'Unknown Title')
        synopsis = self.truncate_synopsis(data.get('synopsis', ''))
        episodes = self.extract_episode_count(data.get('episodes', ''))
        
        # Format with exact style requested
        formatted_output = f"""<b>{title}</b>
────────────────────────
<b>➤ Season :</b> <code>1</code>
<b>➢ Audio :</b> <code>Jap • Eng • Hin • Tel • Tam</code>
<b>➤ Quality :</b><code> 480ᴘ • 720ᴘ • 1080ᴘ</code>
<b>➥ Episodes :</b> {episodes}
<blockquote expandable><b>➟ sʏɴᴏᴘsɪs :</b> <i>{synopsis}</i></blockquote>
────────────────────────
💠 <b>Powered By</b> : @OtakusFlix"""
        
        # If we have anime_id but no cover_url, generate one from AniList CDN
        if not cover_url and anime_id:
            cover_url = f"{ANILIST_IMG_CDN}/media/{anime_id}"
        
        return formatted_output, cover_url

class AnimeSearch:
    def __init__(self):
        self.api_url = GRAPHQL_API_URL

    def _execute_graphql_query(self, query, variables):
        """Execute GraphQL query to the API"""
        try:
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            payload = {
                "query": query,
                "variables": variables
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=15
            )
            
            if response.status_code != 200:
                logger.error(f"GraphQL API failed with status {response.status_code}: {response.text}")
                return None
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during GraphQL query: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)} - Response: {response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in GraphQL query: {str(e)}")
            return None

    def search_anime(self, query: str, page: int = 1, per_page: int = 10):
        """Search anime using GraphQL API"""
        graphql_query = """
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
              # We only need the ID for cover image URL generation
            }
          }
        }
        """
        
        variables = {
            "search": query,
            "page": page,
            "perPage": per_page
        }
        
        result = self._execute_graphql_query(graphql_query, variables)
        
        if not result or "errors" in result:
            logger.error(f"GraphQL query errors: {result.get('errors') if result else 'No result'}")
            return None
            
        if "data" in result and "Page" in result["data"]:
            return result["data"]["Page"]
        
        return None

    def get_anime_by_id(self, anime_id: int):
        """Get anime details by ID using GraphQL API"""
        graphql_query = """
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
            # We only need the ID for cover image URL generation
          }
        }
        """
        
        variables = {"id": anime_id}
        
        result = self._execute_graphql_query(graphql_query, variables)
        
        if not result or "errors" in result:
            logger.error(f"GraphQL query errors for ID {anime_id}: {result.get('errors') if result else 'No result'}")
            return None
            
        if "data" in result and "Media" in result["data"]:
            return result["data"]["Media"]
        
        return None

class TelegramBot:
    def __init__(self):
        self.formatter = AnimeFormatter()
        self.anime_search = AnimeSearch()
        self.user_sessions = {}  # Store user search sessions
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

Or simply send an anime title to search from AniList database!

The bot will format it with:
• Bold headings with special characters
• Truncated synopsis (max 5 lines)
• Standard quality and audio options
• Clean, professional layout
• Cover photos from AniList

<b>💠 Powered By :</b> <a href="https://t.me/Animes2u">Animes2u</a>"""
        await update.message.reply_text(help_text, parse_mode='HTML', disable_web_page_preview=True)

    async def handle_manual_format(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle manual anime formatting"""
        try:
            message_text = update.message.text
            logger.info(f"Processing manual format from user {update.effective_user.id}")
            anime_data = self.formatter.parse_anime_info(message_text)
            if anime_data:
                formatted_text, _ = self.formatter.format_html(anime_data)
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
• Proper line breaks between sections

Or simply send an anime title to search!"""
                await update.message.reply_text(error_message, parse_mode='HTML')
                logger.warning("Invalid format received")
        except Exception as e:
            logger.exception(f"Error processing message: {str(e)}")
            await update.message.reply_text(
                "\u274C <b>Error occurred</b>\n\nSomething went wrong while processing your message. Please try again with the correct format.\n\nUse /start to see the example.",
                parse_mode='HTML'
            )

    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle anime search requests"""
        try:
            query = update.message.text.strip()
            user_id = update.effective_user.id

            if len(query) < 3:
                await update.message.reply_text("❌ Please enter at least 3 characters to search.")
                return

            result = self.anime_search.search_anime(query, page=1)

            if not result or not result.get("media"):
                await update.message.reply_text("❌ No anime found with that name.")
                return

            self.user_sessions[user_id] = {
                "query": query,
                "current_page": 1,
                "total_pages": result["pageInfo"]["lastPage"],
                "results": result["media"]
            }

            keyboard = self._create_search_keyboard(result["media"], user_id, 1, result["pageInfo"])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"🎞 Found {len(result['media'])} results for '{query}':\n\nSelect an anime:",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

        except Exception as e:
            logger.exception(f"Error handling search: {str(e)}")
            await update.message.reply_text("❌ Error searching for anime. Please try again.")

    def _create_search_keyboard(self, results, user_id, current_page, page_info):
        """Create inline keyboard for search results with pagination"""
        keyboard = []

        for anime in results:
            title = anime["title"]["english"] or anime["title"]["romaji"]
            format_type = anime.get("format", "Unknown")
            label = f"{title} ({format_type})"
            if len(label) > 50:
                label = label[:47] + "..."
            keyboard.append([InlineKeyboardButton(label, callback_data=f"select_{anime['id']}")])

        pagination_row = []
        if current_page > 1:
            pagination_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page_{user_id}_{current_page-1}"))

        pagination_row.append(InlineKeyboardButton(f"Page {current_page}/{page_info['lastPage']}", callback_data="current_page"))

        if page_info.get("hasNextPage", False):
            pagination_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{user_id}_{current_page+1}"))

        if pagination_row:
            keyboard.append(pagination_row)

        return keyboard

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses"""
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = query.from_user.id

        try:
            if data.startswith("select_"):
                # User selected an anime
                anime_id = int(data.split("_")[1])
                await self._handle_anime_selection(query, anime_id)

            elif data.startswith("page_"):
                # User wants to change page
                parts = data.split("_")
                target_user_id = int(parts[1])
                page_number = int(parts[2])

                if user_id != target_user_id:
                    await query.edit_message_text("❌ This search session is not yours.")
                    return

                await self._handle_page_change(query, user_id, page_number)

        except Exception as e:
            logger.exception(f"Error handling callback: {str(e)}")
            await query.edit_message_text("❌ Error processing your request.")

    async def _handle_anime_selection(self, query, anime_id):
        """Handle when user selects an anime from search results"""
        anime = self.anime_search.get_anime_by_id(anime_id)

        if not anime:
            await query.edit_message_text("❌ Couldn't load anime details.")
            return

        # Format the anime data in the same style as manual input
        formatted_text, cover_url = self._format_anime_from_api(anime, anime_id)

        # Send message with cover photo if available
        if cover_url:
            try:
                # Test if the cover URL is accessible
                test_response = requests.head(cover_url, timeout=5)
                if test_response.status_code == 200:
                    await query.message.reply_photo(
                        photo=cover_url,
                        caption=formatted_text,
                        parse_mode='HTML'
                    )
                    await query.edit_message_text("✅ Anime formatted successfully!")
                else:
                    # If cover URL doesn't work, send text only
                    logger.warning(f"Cover URL not accessible: {cover_url}")
                    await query.message.reply_text(
                        formatted_text,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                    await query.edit_message_text("✅ Anime formatted (cover image not available)")
            except Exception as e:
                logger.warning(f"Could not send photo, sending text only: {str(e)}")
                await query.message.reply_text(
                    formatted_text,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                await query.edit_message_text("✅ Anime formatted (without cover)")
        else:
            await query.message.reply_text(
                formatted_text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            await query.edit_message_text("✅ Anime formatted (no cover available)")

    async def _handle_page_change(self, query, user_id, page_number):
        """Handle pagination in search results"""
        session = self.user_sessions.get(user_id)
        if not session:
            await query.edit_message_text("❌ Search session expired. Please search again.")
            return

        # Search for the new page
        result = self.anime_search.search_anime(session["query"], page=page_number)

        if not result or not result.get("media"):
            await query.edit_message_text("❌ No results found for this page.")
            return

        # Update session
        session["current_page"] = page_number
        session["results"] = result["media"]
        self.user_sessions[user_id] = session

        # Create new keyboard
        keyboard = self._create_search_keyboard(result["media"], user_id, page_number, result["pageInfo"])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎞 Found results for '{session['query']}':\n\nSelect an anime:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

   # Update the _format_anime_from_api method in TelegramBot class:
def _format_anime_from_api(self, anime, anime_id=None):
    """Format anime data from API into the desired format"""
    title = anime["title"]["english"] or anime["title"]["romaji"]
    description = anime.get("description", "No synopsis available.")
    description = re.sub(r'<.*?>', '', description)  # Remove HTML tags
    description = description.replace('\n', ' ').strip()
    
    episodes = str(anime.get("episodes", "—")) if anime.get("episodes") else "—"

    # Generate cover URL from AniList CDN
    cover_url = None
    if anime_id:
        cover_url = f"{ANILIST_IMG_CDN}/media/{anime_id}"
    
    # Use formatter to format
    manual_format_text = f"""{title}

‣ Genres : Sample
‣ Type : TV
‣ Average Rating : 100
‣ Status : Ongoing
‣ First aired : Unknown
‣ Last aired : Unknown
‣ Runtime : 24 min
‣ No of episodes : {episodes}

‣ Synopsis : {description}

(Source: AniList)"""

    anime_data = self.formatter.parse_anime_info(manual_format_text)
    if anime_data:
        return self.formatter.format_html(anime_data, cover_url, anime_id)
    else:
        # Fallback format
        synopsis = self.formatter.truncate_synopsis(description)
        return f"""<b>{title}</b>
────────────────────────
<b>➤ Season :</b> <code>1</code>
<b>➢ Audio :</b> <code>Jap • Eng • Hin • Tel • Tam</code>
<b>➤ Quality :</b><code> 480ᴘ • 720ᴘ • 1080ᴘ</code>
<b>➥ Episodes :</b> {episodes}
<blockquote expandable><b>➟ sʏɴᴏᴘsɪs :</b> <i>{synopsis}</i></blockquote>
────────────────────────
💠 <b>Powered By</b> : @OtakusFlix""", cover_url
    def _format_date(self, date_dict):
        """Format date from API response"""
        if not date_dict or not date_dict.get("year"):
            return "Unknown"

        year = date_dict["year"]
        month = date_dict.get("month", 1)
        day = date_dict.get("day", 1)

        return f"{year}-{month:02d}-{day:02d}"

    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start_command))

        # Add handler for manual formatting (specific pattern)
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & 
                filters.Regex(r'‣\s*Genres\s*:') &  # Match the manual format pattern
                ~filters.COMMAND, 
                self.handle_manual_format
            )
        )

        # Add handler for search queries (other text messages)
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & 
                ~filters.Regex(r'‣\s*Genres\s*:') &  # Not manual format
                ~filters.COMMAND, 
                self.handle_search
            )
        )

        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))

    def run(self):
        """Run the bot in polling mode"""
        logger.info("🤖 Anime Formatter Bot is starting...")
        logger.info(f"Using GraphQL API: {GRAPHQL_API_URL}")
        logger.info(f"Using AniList CDN for cover images: {ANILIST_IMG_CDN}")
        try:
            # Test API connection
            test_result = self.anime_search.search_anime("naruto", page=1, per_page=1)
            if test_result:
                logger.info("✅ GraphQL API connection successful!")
            else:
                logger.warning("⚠️ GraphQL API test failed, but continuing anyway...")
            
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
        except Exception as e:
            logger.error(f"Failed to start bot: {str(e)}")
            raise

def main():
    try:
        bot = TelegramBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {str(e)}")
        raise

if __name__ == '__main__':
    main()
