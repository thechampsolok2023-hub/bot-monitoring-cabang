import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import gspread
from google.oauth2.service_account import Credentials
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
import pandas as pd
import os

# =============================
# KONFIGURASI
# =============================

BOT_TOKEN = "ISI_TOKEN_BOT_KAMU"
SPREADSHEET_ID = "1FiGTCl-Nny3Eqr657Q1luTQMDNwczxr-R9z1PgiorI0"
WORKSHEET_NAME = "INDIKATOR_FKRTL"

bot = telebot.TeleBot(BOT_TOKEN)

# =============================
# GOOGLE SHEETS CONNECT
# =============================

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)

# =============================
# MENU UTAMA GRID
# =============================

def home_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📊 Monitoring", "📈 Ranking")
    markup.row("📱 Antrian Online", "📲 Mobile JKN")
    markup.row("📘 Buku Panduan", "🌐 Sosial Media")
    return markup

# =============================
# WELCOME MESSAGE RESMI
# =============================

@bot.message_handler(commands=['start'])
def start(message):
    text = (
        "🏥 *SISTEM MONITORING FKRTL*\n"
        "_Monitoring • Evaluasi • Transparansi_\n\n"
        "Selamat datang di sistem resmi pemantauan\n"
        "indikator kepatuhan layanan Fasilitas Kesehatan\n"
        "Rujukan Tingkat Lanjut (FKRTL).\n\n"
        "Platform ini membantu memastikan kualitas layanan\n"
        "berbasis data yang akurat dan real-time.\n\n"
        "Silakan pilih menu di bawah ini."
    )

    bot.send_message(
        message.chat.id,
        text,
        reply_markup=home_menu(),
        parse_mode="Markdown"
    )

# =============================
# MENU MONITORING
# =============================

@bot.message_handler(func=lambda m: m.text == "📊 Monitoring")
def monitoring_menu(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🏥 Per RS", "🏢 Seluruh RS")
    markup.row("🏠 Home")
    bot.send_message(message.chat.id, "Pilih jenis monitoring:", reply_markup=markup)

# =============================
# INPUT BULAN
# =============================

@bot.message_handler(func=lambda m: m.text in ["🏥 Per RS", "🏢 Seluruh RS"])
def input_bulan(message):
    bot.send_message(message.chat.id, "Ketik nama bulan (contoh: Januari)")
    bot.register_next_step_handler(message, proses_bulan, message.text)

def proses_bulan(message, mode):
    bulan = message.text
    data = sheet.get_all_values()
    hasil = []

    for row in data[1:]:
        if row[0].lower() == bulan.lower():
            hasil.append(row)

    if not hasil:
        bot.send_message(message.chat.id, "Data tidak ditemukan.")
        return

    if mode == "🏥 Per RS":
        teks = "📊 *Monitoring Per RS*\n\n"
        for r in hasil:
            nilai = float(r[16])
            warna = "🟢" if nilai >= 80 else "🔴"
            teks += f"{warna} {r[1]} : {nilai}%\n"

        bot.send_message(message.chat.id, teks, parse_mode="Markdown")

    if mode == "🏢 Seluruh RS":
        total = sum(float(r[16]) for r in hasil)
        avg = total / len(hasil)
        warna = "🟢" if avg >= 80 else "🔴"

        teks = (
            f"📊 *Monitoring Seluruh RS*\n\n"
            f"{warna} Rata-rata Kepatuhan: {round(avg,2)}%"
        )

        bot.send_message(message.chat.id, teks, parse_mode="Markdown")

# =============================
# RANKING + GRAFIK
# =============================

@bot.message_handler(func=lambda m: m.text == "📈 Ranking")
def ranking(message):
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    df["Nilai Kepatuhan"] = df["Nilai Kepatuhan"].astype(float)

    top = df.sort_values("Nilai Kepatuhan", ascending=False).head(10)

    plt.figure()
    plt.bar(top["NamaPPK"], top["Nilai Kepatuhan"])
    plt.xticks(rotation=90)
    plt.title("Top 10 Ranking Kepatuhan")
    plt.tight_layout()
    plt.savefig("ranking.png")
    plt.close()

    bot.send_photo(message.chat.id, open("ranking.png", "rb"))

# =============================
# EXPORT PDF
# =============================

def export_pdf(data, filename="laporan.pdf"):
    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    elements = []

    for row in data:
        elements.append(Paragraph(str(row), styles["Normal"]))
        elements.append(Spacer(1, 0.2 * inch))

    doc.build(elements)
    return filename

# =============================
# MENU TAMBAHAN
# =============================

@bot.message_handler(func=lambda m: m.text == "📱 Antrian Online")
def antrian(message):
    bot.send_message(message.chat.id, "Menu Monitoring Antrian Online tersedia.")

@bot.message_handler(func=lambda m: m.text == "📲 Mobile JKN")
def mobile(message):
    bot.send_message(message.chat.id, "Menu Monitoring Mobile JKN tersedia.")

@bot.message_handler(func=lambda m: m.text == "📘 Buku Panduan")
def buku(message):
    bot.send_message(message.chat.id, "Buku Panduan dapat diakses melalui link resmi instansi.")

@bot.message_handler(func=lambda m: m.text == "🌐 Sosial Media")
def sosial(message):
    bot.send_message(message.chat.id, "Ikuti sosial media resmi untuk informasi terbaru.")

@bot.message_handler(func=lambda m: m.text == "🏠 Home")
def back_home(message):
    start(message)

# =============================
# RUN BOT
# =============================

print("Bot berjalan...")
bot.infinity_polling()
