import os
import telebot

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    markup.row("📊 Indikator Kepatuhan")
    markup.row("📱 Antrean Online")
    markup.row("📲 Mobile JKN")
    markup.row("📚 Buku Panduan")
    markup.row("📢 Sosial Media")
    markup.row("📈 Sibling")
    markup.row("ℹ️ Informasi Lain-lain")
    
    bot.send_message(
        message.chat.id,
        "Selamat datang di Bot Monitoring Cabang.\nSilakan pilih menu:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: True)
def menu_handler(message):
    if message.text == "📚 Buku Panduan":
        bot.send_message(message.chat.id, "Link Buku Panduan:\nhttps://drive.google.com/")
    
    elif message.text == "📢 Sosial Media":
        bot.send_message(message.chat.id,
            "Sosial Media:\n\n"
            "📍 Lokal:\n"
            "Instagram: https://instagram.com/\n"
            "Tiktok: https://tiktok.com/\n\n"
            "📍 Nasional:\n"
            "Instagram: https://instagram.com/\n"
            "Tiktok: https://tiktok.com/"
        )
    
    else:
        bot.send_message(message.chat.id, "Fitur sedang dikembangkan.")

bot.infinity_polling()
