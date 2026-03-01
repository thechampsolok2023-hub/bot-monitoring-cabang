import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# ===============================
# MENU UTAMA
# ===============================
def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Indikator Kepatuhan", callback_data="indikator"),
        InlineKeyboardButton("📈 Sibling (Capaian)", callback_data="sibling"),
        InlineKeyboardButton("📱 Antrean Online", callback_data="antrean"),
        InlineKeyboardButton("📲 Mobile JKN", callback_data="mobile"),
        InlineKeyboardButton(
            "📚 Buku Panduan",
            url="https://drive.google.com/file/d/1KPgdy9cC3INueoxmCF8TBGXCKwxIr8nz/view?usp=sharing"
        ),
        InlineKeyboardButton("📢 Sosial Media", callback_data="sosmed"),
        InlineKeyboardButton("ℹ️ Informasi Lainnya", callback_data="info"),
    )
    return markup


# ===============================
# START MESSAGE
# ===============================
@bot.message_handler(commands=['start'])
def start(message):
    nama = message.from_user.first_name
    tanggal = datetime.now().strftime("%d %B %Y")

    welcome_text = (
        f"👋 *Selamat Datang, {nama}*\n\n"
        "🏥 *SISTEM MONITORING & EVALUASI FASKES*\n"
        "Kantor Cabang Solok\n\n"
        f"📅 {tanggal}\n\n"
        "Sistem ini digunakan untuk:\n"
        "• Monitoring indikator kepatuhan\n"
        "• Evaluasi layanan digital\n"
        "• Analisis capaian & area of improvement\n"
        "• Dokumentasi hasil customer visit\n\n"
        "_Monitoring hari ini menentukan mutu layanan esok hari._\n\n"
        "Silakan pilih menu yang tersedia di bawah ini:"
    )

    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )


# ===============================
# CALLBACK HANDLER
# ===============================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):

    # ===== INDIKATOR =====
    if call.data == "indikator":
        bot.send_message(
            call.message.chat.id,
            "📊 *Indikator Kepatuhan*\n\n"
            "Data capaian akan ditampilkan di sini.\n"
            "(Terhubung dengan Google Sheet)",
            parse_mode="Markdown"
        )

    # ===== SIBLING =====
    elif call.data == "sibling":
        bot.send_message(
            call.message.chat.id,
            "📈 *Sibling Monitoring*\n\n"
            "• Capaian\n"
            "• Area of Improvement\n"
            "• Hasil Customer Visit\n\n"
            "Menu detail akan segera aktif.",
            parse_mode="Markdown"
        )

    # ===== ANTREAN =====
    elif call.data == "antrean":
        bot.send_message(
            call.message.chat.id,
            "📱 Monitoring Antrean Online\n\n"
            "Status dan optimalisasi layanan antrean.",
        )

    # ===== MOBILE JKN =====
    elif call.data == "mobile":
        bot.send_message(
            call.message.chat.id,
            "📲 Monitoring Mobile JKN\n\n"
            "Data pemanfaatan dan aktivasi layanan digital.",
        )

    # ===== SOSIAL MEDIA =====
    elif call.data == "sosmed":
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("📍 Lokal - JKN Solok Raya", callback_data="lokal"),
            InlineKeyboardButton("📍 Nasional - BPJS RI", callback_data="nasional"),
            InlineKeyboardButton("⬅️ Kembali ke Menu Utama", callback_data="back")
        )
        bot.edit_message_text(
            "📢 *Sosial Media Resmi*\n\nSilakan pilih kategori:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif call.data == "lokal":
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton(
                "Instagram Lokal",
                url="https://www.instagram.com/jkn_solokraya?igsh=Y2xjdDNqbjhsZ2Vp"
            ),
            InlineKeyboardButton(
                "Tiktok Lokal",
                url="https://www.tiktok.com/@jknsolokraya?_r=1"
            ),
            InlineKeyboardButton("⬅️ Kembali", callback_data="sosmed")
        )
        bot.edit_message_text(
            "📍 *JKN Solok Raya*",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif call.data == "nasional":
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton(
                "Instagram BPJS RI",
                url="https://www.instagram.com/bpjskesehatan_ri?igsh=bzFud2o2NXhsMG1p"
            ),
            InlineKeyboardButton(
                "Tiktok BPJS RI",
                url="https://www.tiktok.com/@bpjskesehatan_ri?_r=1"
            ),
            InlineKeyboardButton("⬅️ Kembali", callback_data="sosmed")
        )
        bot.edit_message_text(
            "📍 *BPJS Kesehatan RI*",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    # ===== KEMBALI =====
    elif call.data == "back":
        bot.edit_message_text(
            "Silakan pilih menu:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu()
        )

    # ===== INFORMASI =====
    elif call.data == "info":
        bot.send_message(
            call.message.chat.id,
            "ℹ️ Informasi tambahan akan diperbarui secara berkala.\n\n"
            "Untuk bantuan teknis, silakan hubungi Admin Cabang."
        )

    bot.answer_callback_query(call.id)


bot.infinity_polling()
