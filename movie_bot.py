import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ConversationHandler, 
    filters, ContextTypes
)
from telegram.constants import ParseMode

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot tokeni (BotFather dan oling)
BOT_TOKEN = "8818398233:AAHinD_UrgkeoxOXGVeWjG3xneofcHLJf1I"

# Conversation holatlari
(
    ADMIN_MAIN, ADD_MOVIE_CODE, ADD_MOVIE_FILE, ADD_MOVIE_CAPTION, 
    ADD_MOVIE_LINK, ADD_CHANNEL_LINK, ADD_CHANNEL_CONFIRM,
    BROADCAST_MESSAGE, CHECK_SUBSCRIPTION, ENTER_MOVIE_CODE
) = range(10)

# Ma'lumotlar bazasini sozlash
def init_database():
    conn = sqlite3.connect('kino_bot.db')
    c = conn.cursor()
    
    # Adminlar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS admins
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  added_by INTEGER,
                  added_date TEXT)''')
    
    # Kinolar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS movies
                 (code TEXT PRIMARY KEY,
                  file_id TEXT,
                  caption TEXT,
                  link TEXT,
                  added_by INTEGER,
                  added_date TEXT)''')
    
    # Majburiy kanallar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS required_channels
                 (channel_id TEXT PRIMARY KEY,
                  channel_link TEXT,
                  channel_name TEXT,
                  added_by INTEGER,
                  added_date TEXT)''')
    
    # Foydalanuvchilar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  joined_date TEXT)''')
    
    # Foydalanuvchi holati jadvali (majburiy kanallarni tekshirish uchun)
    c.execute('''CREATE TABLE IF NOT EXISTS user_status
                 (user_id INTEGER PRIMARY KEY,
                  last_code TEXT,
                  checked_date TEXT)''')
    
    conn.commit()
    conn.close()

# Ma'lumotlar bazasini ishga tushirish
init_database()

# Adminlarni tekshirish funksiyasi
def is_admin(user_id):
    conn = sqlite3.connect('kino_bot.db')
    c = conn.cursor()
    c.execute("SELECT * FROM admins WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

# Foydalanuvchini saqlash
def save_user(user_id, username, first_name):
    conn = sqlite3.connect('kino_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date) VALUES (?, ?, ?, ?)",
              (user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# Majburiy kanallarni tekshirish
async def check_subscription(user_id, context):
    conn = sqlite3.connect('kino_bot.db')
    c = conn.cursor()
    c.execute("SELECT channel_id FROM required_channels")
    channels = c.fetchall()
    conn.close()
    
    not_subscribed = []
    
    for channel in channels:
        channel_id = channel[0]
        try:
            member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_subscribed.append(channel_id)
        except:
            not_subscribed.append(channel_id)
    
    return not_subscribed

# START komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.username, user.first_name)
    
    # Majburiy kanallarni tekshirish
    not_subscribed = await check_subscription(user.id, context)
    
    if not_subscribed:
        # Majburiy kanallar ro'yxatini chiqarish
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        channels = c.execute("SELECT channel_link, channel_name FROM required_channels").fetchall()
        conn.close()
        
        keyboard = []
        for channel in channels:
            keyboard.append([InlineKeyboardButton(f"📢 {channel[1]}", url=channel[0])])
        
        keyboard.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_subs")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=reply_markup
        )
        return CHECK_SUBSCRIPTION
    else:
        await update.message.reply_text(
            "🎬 Kino kodini yuboring:\n\n"
            "Misol: 103"
        )
        return ENTER_MOVIE_CODE

# Obunani tekshirish
async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    not_subscribed = await check_subscription(user_id, context)
    
    if not_subscribed:
        # Hali ham obuna bo'lmagan kanallar bor
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        channels = c.execute("SELECT channel_link, channel_name FROM required_channels").fetchall()
        conn.close()
        
        keyboard = []
        for channel in channels:
            keyboard.append([InlineKeyboardButton(f"📢 {channel[1]}", url=channel[0])])
        
        keyboard.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_subs")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ Hali ham quyidagi kanallarga obuna bo'lmagansiz:",
            reply_markup=reply_markup
        )
    else:
        await query.edit_message_text(
            "✅ Obuna muvaffaqiyatli tekshirildi!\n\n"
            "🎬 Endi kino kodini yuboring:"
        )
        return ENTER_MOVIE_CODE

# Kino kodini qabul qilish
async def enter_movie_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip()
    
    # Majburiy kanallarni qayta tekshirish
    not_subscribed = await check_subscription(user_id, context)
    if not_subscribed:
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        channels = c.execute("SELECT channel_link, channel_name FROM required_channels").fetchall()
        conn.close()
        
        keyboard = []
        for channel in channels:
            keyboard.append([InlineKeyboardButton(f"📢 {channel[1]}", url=channel[0])])
        
        keyboard.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_subs")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚠️ Siz kanallardan chiqib ketgansiz. Iltimos, qayta obuna bo'ling:",
            reply_markup=reply_markup
        )
        return CHECK_SUBSCRIPTION
    
    # Kino kodini bazadan qidirish
    conn = sqlite3.connect('kino_bot.db')
    c = conn.cursor()
    c.execute("SELECT file_id, caption, link FROM movies WHERE code = ?", (code,))
    movie = c.fetchone()
    conn.close()
    
    if movie:
        file_id, caption, link = movie
        
        # Foydalanuvchi holatini saqlash
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO user_status (user_id, last_code, checked_date) VALUES (?, ?, ?)",
                  (user_id, code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        
        # Kinoni yuborish (forward qilishni bloklash)
        try:
            await update.message.reply_video(
                video=file_id,
                caption=caption,
                protect_content=True  # Bu forward va yuklab olishni bloklaydi
            )
            
            if link:
                await update.message.reply_text(f"🔗 Qo'shimcha link: {link}")
                
        except Exception as e:
            await update.message.reply_text("❌ Kino yuborishda xatolik yuz berdi.")
    else:
        await update.message.reply_text("❌ Bunday kod mavjud emas. Qayta urinib ko'ring:")

# Admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Siz admin emassiz!")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Admin qo'shish", callback_data="add_admin")],
        [InlineKeyboardButton("🎬 Kino qo'shish", callback_data="add_movie")],
        [InlineKeyboardButton("📢 Majburiy kanal qo'shish", callback_data="add_channel")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton("📨 Reklama yuborish", callback_data="broadcast")],
        [InlineKeyboardButton("👥 Adminlar ro'yxati", callback_data="list_admins")],
        [InlineKeyboardButton("📋 Kinolar ro'yxati", callback_data="list_movies")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👨‍💻 Admin panel:", reply_markup=reply_markup)
    return ADMIN_MAIN

# Admin qo'shish
async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🆕 Yangi admin ID sini yuboring:\n"
        "(Admin bo'ladigan foydalanuvchining Telegram ID sini yozing)"
    )
    return ADD_CHANNEL_LINK  # Bu holatni qayta ishlatamiz

async def add_admin_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.message.text.strip()
    
    try:
        admin_id = int(admin_id)
        current_user = update.effective_user.id
        
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO admins (user_id, added_by, added_date) VALUES (?, ?, ?)",
                  (8505118420, current_user, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Admin muvaffaqiyatli qo'shildi! ID: {admin_id}")
        
        # Admin panelga qaytish
        keyboard = [
            [InlineKeyboardButton("⬅️ Admin panelga qaytish", callback_data="back_to_admin")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Admin panel:", reply_markup=reply_markup)
        
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri ID formati. Qayta urinib ko'ring:")

# Kino qo'shish
async def add_movie_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("🎬 Kino kodini kiriting (masalan: 103):")
    return ADD_MOVIE_CODE

async def add_movie_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    context.user_data['movie_code'] = code
    
    await update.message.reply_text("📹 Endi kinoni yuboring (video fayl):")
    return ADD_MOVIE_FILE

async def add_movie_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        file_id = update.message.video.file_id
        context.user_data['movie_file_id'] = file_id
        
        await update.message.reply_text("📝 Kino haqida matn yozing (caption):")
        return ADD_MOVIE_CAPTION
    else:
        await update.message.reply_text("❌ Iltimos, video fayl yuboring!")
        return ADD_MOVIE_FILE

async def add_movie_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.text
    context.user_data['movie_caption'] = caption
    
    keyboard = [
        [InlineKeyboardButton("✅ Ha", callback_data="add_link_yes")],
        [InlineKeyboardButton("❌ Yo'q", callback_data="add_link_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("🔗 Qo'shimcha link qo'shasizmi?", reply_markup=reply_markup)
    return ADD_MOVIE_LINK

async def add_movie_link_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("🔗 Linkni yuboring:")
    return ADD_MOVIE_LINK

async def add_movie_link_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Kinoni bazaga saqlash
    await save_movie_to_db(context, query.from_user.id, link=None)
    
    await query.edit_message_text("✅ Kino muvaffaqiyatli qo'shildi!")

async def add_movie_link_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    
    # Kinoni bazaga saqlash
    await save_movie_to_db(context, update.effective_user.id, link)
    
    await update.message.reply_text("✅ Kino muvaffaqiyatli qo'shildi!")

async def save_movie_to_db(context, admin_id, link=None):
    code = context.user_data.get('movie_code')
    file_id = context.user_data.get('movie_file_id')
    caption = context.user_data.get('movie_caption')
    
    conn = sqlite3.connect('kino_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO movies (code, file_id, caption, link, added_by, added_date) VALUES (?, ?, ?, ?, ?, ?)",
              (code, file_id, caption, link, admin_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# Majburiy kanal qo'shish
async def add_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📢 Kanal yoki guruh linkini yuboring:\n"
        "Misol: https://t.me/kanal_nomi"
    )
    return ADD_CHANNEL_LINK

async def add_channel_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    context.user_data['channel_link'] = link
    
    # Kanal ID sini olish
    try:
        chat = await context.bot.get_chat(link)
        channel_id = str(chat.id)
        channel_name = chat.title
        
        context.user_data['channel_id'] = channel_id
        context.user_data['channel_name'] = channel_name
        
        keyboard = [
            [InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_channel")],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_channel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📢 Kanal topildi: {channel_name}\n\n"
            f"ID: {channel_id}\n"
            f"Link: {link}\n\n"
            "Botni ushbu kanalga admin qilganingizga ishonch hosil qiling!",
            reply_markup=reply_markup
        )
        return ADD_CHANNEL_CONFIRM
        
    except Exception as e:
        await update.message.reply_text(
            "❌ Kanal topilmadi. Iltimos:\n"
            "1. Kanalga botni admin qiling\n"
            "2. Kanal linki to'g'ri ekanligiga ishonch hosil qiling\n"
            "3. Qayta urinib ko'ring"
        )
        return ADD_CHANNEL_LINK

async def confirm_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    channel_id = context.user_data.get('channel_id')
    channel_link = context.user_data.get('channel_link')
    channel_name = context.user_data.get('channel_name')
    admin_id = query.from_user.id
    
    conn = sqlite3.connect('kino_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO required_channels (channel_id, channel_link, channel_name, added_by, added_date) VALUES (?, ?, ?, ?, ?)",
              (channel_id, channel_link, channel_name, admin_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    await query.edit_message_text("✅ Majburiy kanal muvaffaqiyatli qo'shildi!")

async def cancel_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("❌ Bekor qilindi.")

# Statistika
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = sqlite3.connect('kino_bot.db')
    c = conn.cursor()
    
    users_count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    movies_count = c.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    admins_count = c.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    channels_count = c.execute("SELECT COUNT(*) FROM required_channels").fetchone()[0]
    
    today = datetime.now().strftime("%Y-%m-%d")
    today_users = c.execute("SELECT COUNT(*) FROM users WHERE joined_date LIKE ?", (f"{today}%",)).fetchone()[0]
    
    conn.close()
    
    stats_text = f"""
📊 BOT STATISTIKASI

👥 Foydalanuvchilar: {users_count}
📅 Bugun qo'shilgan: {today_users}
🎬 Kinolar soni: {movies_count}
👨‍💻 Adminlar: {admins_count}
📢 Majburiy kanallar: {channels_count}
    """
    
    await query.edit_message_text(stats_text)

# Reklama yuborish
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📨 Reklama xabarini yuboring:\n"
        "(Bu xabar BARCHA foydalanuvchilarga boradi)"
    )
    return BROADCAST_MESSAGE

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    conn = sqlite3.connect('kino_bot.db')
    c = conn.cursor()
    users = c.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    
    success = 0
    failed = 0
    
    for user in users:
        try:
            await message.copy(chat_id=user[0])
            success += 1
        except:
            failed += 1
    
    await update.message.reply_text(
        f"✅ Reklama yuborildi!\n"
        f"Yuborildi: {success}\n"
        f"Xatolik: {failed}"
    )

# Adminlar ro'yxati
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = sqlite3.connect('kino_bot.db')
    c = conn.cursor()
    admins = c.execute("SELECT user_id, added_by, added_date FROM admins").fetchall()
    conn.close()
    
    if admins:
        text = "👥 Adminlar ro'yxati:\n\n"
        for admin in admins:
            text += f"🆔 ID: {admin[0]}\n"
            text += f"👤 Qo'shgan: {admin[1]}\n"
            text += f"📅 Sana: {admin[2]}\n\n"
    else:
        text = "Adminlar mavjud emas."
    
    await query.edit_message_text(text)

# Kinolar ro'yxati
async def list_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = sqlite3.connect('kino_bot.db')
    c = conn.cursor()
    movies = c.execute("SELECT code, added_by, added_date FROM movies ORDER BY added_date DESC LIMIT 20").fetchall()
    conn.close()
    
    if movies:
        text = "🎬 So'nggi 20 ta kino:\n\n"
        for movie in movies:
            text += f"📌 Kod: {movie[0]}\n"
            text += f"👤 Admin: {movie[1]}\n"
            text += f"📅 Sana: {movie[2]}\n\n"
    else:
        text = "Kinolar mavjud emas."
    
    await query.edit_message_text(text)

# Admin panelga qaytish
async def back_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("➕ Admin qo'shish", callback_data="add_admin")],
        [InlineKeyboardButton("🎬 Kino qo'shish", callback_data="add_movie")],
        [InlineKeyboardButton("📢 Majburiy kanal qo'shish", callback_data="add_channel")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton("📨 Reklama yuborish", callback_data="broadcast")],
        [InlineKeyboardButton("👥 Adminlar ro'yxati", callback_data="list_admins")],
        [InlineKeyboardButton("📋 Kinolar ro'yxati", callback_data="list_movies")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("👨‍💻 Admin panel:", reply_markup=reply_markup)

# Asosiy funksiya
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('admin', admin_panel)
        ],
        states={
            ADMIN_MAIN: [
                CallbackQueryHandler(add_admin_start, pattern="^add_admin$"),
                CallbackQueryHandler(add_movie_start, pattern="^add_movie$"),
                CallbackQueryHandler(add_channel_start, pattern="^add_channel$"),
                CallbackQueryHandler(show_stats, pattern="^stats$"),
                CallbackQueryHandler(broadcast_start, pattern="^broadcast$"),
                CallbackQueryHandler(list_admins, pattern="^list_admins$"),
                CallbackQueryHandler(list_movies, pattern="^list_movies$")
            ],
            ADD_MOVIE_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_code)
            ],
            ADD_MOVIE_FILE: [
                MessageHandler(filters.VIDEO, add_movie_file)
            ],
            ADD_MOVIE_CAPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_caption)
            ],
            ADD_MOVIE_LINK: [
                CallbackQueryHandler(add_movie_link_yes, pattern="^add_link_yes$"),
                CallbackQueryHandler(add_movie_link_no, pattern="^add_link_no$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_link_process)
            ],
            ADD_CHANNEL_LINK: [
                CallbackQueryHandler(add_admin_process, pattern=None),  # Admin qo'shish uchun
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_link)
            ],
            ADD_CHANNEL_CONFIRM: [
                CallbackQueryHandler(confirm_channel, pattern="^confirm_channel$"),
                CallbackQueryHandler(cancel_channel, pattern="^cancel_channel$")
            ],
            CHECK_SUBSCRIPTION: [
                CallbackQueryHandler(check_subscription_callback, pattern="^check_subs$")
            ],
            ENTER_MOVIE_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_movie_code)
            ],
            BROADCAST_MESSAGE: [
                MessageHandler(filters.ALL, broadcast_message)
            ]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    app.add_handler(conv_handler)
    
    # Qo'shimcha handlerlar
    app.add_handler(CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$"))
    
    print("🤖 Bot ishga tushdi...")
    app.run_polling()

if __name__ == '__main__':
    main()
