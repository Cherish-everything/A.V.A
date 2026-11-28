from telegram import Update
import requests
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters 
import os
from pathlib import Path
from core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from core.timeutil import today
from core.chat_loop import reply

OUTPUT_DIR = Path(__file__).parent.parent / "skills" / "output"
NOTES_FILE = Path(__file__).parent.parent / "logs" / "telegram_notes.txt"

async def handle_text_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"Saving note to path: {NOTES_FILE.resolve()}")
    with open(NOTES_FILE, 'a', encoding="utf-8") as f:
        f.write(f"Note:{user_text}\n")

    await update.message.reply_text(f"Note saved successfully: \"{user_text}\"")

async def handle_voice_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    voice_dir = Path(__file__).parent.parent / "logs" / "VN"   
    voice_dir.mkdir(parents=True, exist_ok=True)

    file_path = voice_dir / f"VN_{voice.file_unique_id}.mp3"
    await file.download_to_drive(str(file_path))
    await update.message.reply_text(f"Voice note recieved and saved: {voice.duration}s")

async def send_briefing(update: Update, context:ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    today_str = str(today())

    target_filename = f"morning_brief_{today_str}.png"
    latest_image = OUTPUT_DIR / target_filename

    if not latest_image.is_file():
        await update.message.reply_text(f"No morning brief generated for today ({today_str}) yet. Run A.V.A to fetch data.")
        return
    
    with open(latest_image, 'rb') as photo:
        await context.bot.send_photo(chat_id=chat_id, photo=photo, caption="Today's Morning Brief")

def push_briefing_to_telegram(image_path: str):
    """Directly sends the generated briefing image to your Telegram chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    
    with open(image_path, "rb") as photo:
        response = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": f"🗞️ Good morning! Here is your Daily Chronicle for {today()}."
            },
            files={"photo": photo}
        )
    
    if response.status_code == 200:
        print("Briefing pushed to Telegram successfully!")
    else:
        print(f"Failed to send Telegram brief: {response.text}")

async def handle_incoming_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_id = update.message.chat_id

    # 1. If the message starts with /note, save it to the notes file as before
    if user_text.startswith("/note"):
        note_content = user_text[len("/note"):].strip()
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTES_FILE, 'a', encoding="utf-8") as f:
            f.write(f"Note:{note_content}\n")
        await update.message.reply_text(f"Note saved successfully: \"{note_content}\"")
        return

    # 2. Otherwise, treat it as an incoming prompt for A.V.A (if AFK)
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    # Run A.V.A's reply loop with is_afk=False so it returns the response directly here
    try:
        response_text = reply(user_prompt=user_text, history=[], is_afk=False)
        await update.message.reply_text(response_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error processing prompt: {str(e)}")

def start_telegram():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("briefing", send_briefing))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_incoming_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice_note))

    print("Telegram running...")
    app.run_polling()