import os
import re
import json
import time
import logging
import requests
import subprocess
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError

# ==========================================
# 1. Configuration and Setup
# ==========================================
TELEGRAM_BOT_TOKEN = "7835111211:AAG_11yl2GL5xQvaAjZCUNW5jwtzp7srEG8"
HF_API_TOKEN = "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"

CHAT_API_URL = "https://router.huggingface.co/v1/chat/completions"
CHAT_MODEL = "deepseek-ai/DeepSeek-V3.2-Exp"
VISION_API_URL = "https://api-inference.huggingface.co/models/google/vit-base-patch16-224"

# Set up logging exactly as specified
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==========================================
# 2. Core AI Function
# ==========================================
def query_yashbot_ai(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    system_prompt = 'You are Yash Bot. Always start your response with a simple smiling emoji (like 😊), followed by a space. Always respond in Hindi using feminine grammar. Your answers must be concise (1-2 sentences).'
    
    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    }

    for _ in range(3):
        try:
            response = requests.post(CHAT_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content')
            
            if not content:
                return "😊 माफ़ कीजिये, मुझे कोई जवाब नहीं मिला।"
            
            return content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error in Chat API: {e}")
            time.sleep(3)
        except Exception as e:
            logger.error(f"Unknown error in Chat API: {e}")
            return "😊 माफ़ कीजिये, AI ब्रेन से कनेक्ट करते समय एक अज्ञात त्रुटि हुई।"

    return "😊 माफ़ कीजिये, AI ब्रेन से कनेक्ट करते समय नेटवर्क में कोई समस्या हुई।"

# ==========================================
# 3. Vision AI Function
# ==========================================
def query_vision_model(image_bytes: bytes, caption: str) -> str:
    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}"
    }

    for _ in range(3):
        try:
            response = requests.post(VISION_API_URL, headers=headers, data=image_bytes)
            response.raise_for_status()
            result = response.json()
            
            # Extract label
            description = ""
            if isinstance(result, list) and len(result) > 0 and 'label' in result[0]:
                description = result[0]['label']
            else:
                description = "कोई वस्तु स्पष्ट रूप से पहचान में नहीं आई।"
                
            # Construct chaining prompt and call Chat API
            new_prompt = f"A user sent an image with the caption '{caption}'. My vision analysis says it contains: '{description}'. Please respond to the user based on this."
            
            return query_yashbot_ai(new_prompt)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error in Vision API: {e}")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Unknown error in Vision API: {e}")
            return "😊 छवि को प्रोसेस करते समय कोई अज्ञात त्रुट-ि हुई।"

    return "😊 छवि को प्रोसेस करते समय नेटवर्क में कोई समस्या हुई।"

# ==========================================
# 4. Local Termux Commands
# ==========================================
def handle_local_commands(text: str) -> str | None:
    text_lower = text.lower()

    # Time Command
    time_keywords = ["time", "samay", "baje", "टाइम", "समय"]
    if any(keyword in text_lower for keyword in time_keywords):
        current_time = datetime.now().strftime("%I:%M %p")
        return f"😊 सर, अभी {current_time} हुए हैं।"

    # Battery Command
    if "battery" in text_lower or "चार्ज" in text_lower:
        try:
            result = subprocess.run(['termux-battery-status'], capture_output=True, text=True, check=True)
            battery_data = json.loads(result.stdout)
            percentage = battery_data.get('percentage', 'unknown')
            return f"😊 सर, बैटरी {percentage}% पर है।"
        except Exception as e:
            logger.error(f"Termux battery command failed: {e}")
            return "😊 मैं बैटरी की जानकारी नहीं ले पा रही हूँ। कृपया सुनिश्चित करें कि Termux:API स्थापित है।"

    # Open URL Command
    match = re.search(r"(open|kholo|खोलें|खोलो)\s+([a-zA-Z0-9-]+\.[a-zA-Z]{2,}(\.[a-zA-Z]{2,})?)", text, re.IGNORECASE)
    if match:
        domain = match.group(2)
        url = domain if domain.startswith(("http://", "https://")) else f"https://{domain}"
        return f"😊 ठीक है सर, यह रहा [{match.group(2)}]({url}) का लिंक।"

    return None

# ==========================================
# 5. Telegram Handlers
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_message = f"नमस्ते {user.mention_html()}! Hi, I am Yash Bot ..."
    await update.message.reply_html(welcome_message)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    text_lower = text.lower()

    # Message Reaction
    reaction_words = ["love", "thanks", "धन्यवाद", "❤️", "😍"]
    reaction_emoji = '❤️' if any(word in text_lower for word in reaction_words) else '😊'
    
    try:
        from telegram import ReactionTypeEmoji
        await update.message.set_reaction(reaction=[ReactionTypeEmoji(reaction_emoji)])
    except Exception as e:
        logger.warning(f"Could not set reaction: {e}")

    # Control Flow: First check for local commands
    local_response = handle_local_commands(text)
    if local_response is not None:
        # Markdown parsing needed for the Open URL command output
        await update.message.reply_text(local_response, parse_mode=ParseMode.MARKDOWN)
        return

    # Fallback to AI
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    ai_response = query_yashbot_ai(text)
    await update.message.reply_text(ai_response)

async def handle_image_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Send typing action immediately
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

        # Download the highest resolution photo
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_byte_array = await file.download_as_bytearray()
        image_bytes = bytes(image_byte_array)

        # Setup caption
        caption = update.message.caption if update.message.caption else "इस तस्वीर में क्या है?"

        # Send status message
        await update.message.reply_text("😊 तस्वीर देख रही हूँ...")

        # Process image and get AI response
        vision_result = query_vision_model(image_bytes, caption)

        # Reply with the final result
        await update.message.reply_text(vision_result)

    except Exception as e:
        logger.error(f"Error handling image message: {e}")
        await update.message.reply_text("😊 तस्वीर को प्रोसेस करते समय एक अप्रत्याशित त्रुटि हुई।")

# ==========================================
# 6. Main Execution Block
# ==========================================
def main():
    # Build Application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image_message))

    # Print startup message exactly as specified
    print("JARVIS AI Bot (Full Control & Auto-Retry) is running... Press Ctrl-C to stop.")
    
    # Run polling
    application.run_polling()

if __name__ == "__main__":
    main()
