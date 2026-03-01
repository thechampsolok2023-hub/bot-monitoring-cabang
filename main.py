import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# ===== MENU UTAMA =====
def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Indikator Kepatuhan", callback_data="indikator"),
        InlineKeyboardButton("📱 Antrean Online", callback_data="antrean"),
        InlineKeyboardButton("📲 Mobile JKN", callback_data="mobile"),
        InlineKeyboardButton("📈 Sibling", callback_data="sibling"),
        InlineKeyboardButton("📚 Buku Panduan", url="https://drive.google.com/"),
        InlineKeyboardButton("📢 Sosial Media", callback_data="sosmed"),
        InlineKeyboardButton("ℹ️ Informasi Lain-lain", callback_data="info"),
    )
    return markup


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "🤖 *SISTEM MONITORING FASKES CABANG*\n\n"
        "Selamat datang 👋\n"
        "Terima kasih telah menggunakan sistem monitoring resmi.\n\n"
        "Silakan pilih menu di bawah ini:",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )


# ===== CALLBACK HANDLER =====
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):

    # === SUBMENU SOSIAL MEDIA ===
    if call.data == "sosmed":
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("📍 Lokal", callback_data="lokal"),
            InlineKeyboardButton("📍 Nasional", callback_data="nasional"),
            InlineKeyboardButton("⬅️ Kembali", callback_data="back")
        )
        bot.edit_message_text(
            "📢 *Sosial Media*\n\nSilakan pilih kategori:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif call.data == "lokal":
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("Instagram Lokal", url="https://instagram.com/"),
            InlineKeyboardButton("Tiktok Lokal", url="https://tiktok.com/"),
            InlineKeyboardButton("⬅️ Kembali", callback_data="sosmed")
        )
        bot.edit_message_text(
            "📍 *Sosial Media Lokal*",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif call.data == "nasional":
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("Instagram Nasional", url="https://instagram.com/"),
            InlineKeyboardButton("Tiktok Nasional", url="https://tiktok.com/"),
            InlineKeyboardButton("⬅️ Kembali", callback_data="sosmed")
        )
        bot.edit_message_text(
            "📍 *Sosial Media Nasional*",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif call.data == "back":
        bot.edit_message_text(
            "🤖 *SISTEM MONITORING FASKES CABANG*\n\n"
            "Silakan pilih menu di bawah ini:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )

    else:
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "Menu sedang dikembangkan.")

bot.infinity_polling()
