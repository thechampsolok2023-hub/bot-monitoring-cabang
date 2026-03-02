import os
import telebot
import json
import gspread
import matplotlib.pyplot as plt
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google.oauth2.service_account import Credentials
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet

# ================= ENV =================
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN tidak ditemukan")

creds_env = os.getenv("GOOGLE_CREDENTIALS")
if not creds_env:
    raise ValueError("GOOGLE_CREDENTIALS tidak ditemukan")

bot = telebot.TeleBot(TOKEN)

# ================= GOOGLE =================
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(creds_env)
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

SPREADSHEET_ID = "1FiGTCl-Nny3Eqr657Q1luTQMDNwczxr-R9z1PgiorI0"
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

print("Google Sheet Connected ✅")

# ================= UTIL =================
def get_data():
    return sheet.get_all_records()

def safe_edit(chat_id, message_id, text, markup=None):
    try:
        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except:
        pass

# ================= MENU UTAMA =================
def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Indikator Kepatuhan", callback_data="indikator"),
        InlineKeyboardButton("🏥 Antrian Online", callback_data="antrian"),
        InlineKeyboardButton("📱 Mobile JKN", callback_data="mobile"),
        InlineKeyboardButton("ℹ️ Informasi Lain-lain", callback_data="info"),
        InlineKeyboardButton("📘 Buku Panduan", callback_data="buku"),
        InlineKeyboardButton("🌐 Sosial Media", callback_data="sosmed"),
    )
    return markup

def home_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏠 Home", callback_data="home"))
    return markup

def bulan_menu():
    markup = InlineKeyboardMarkup(row_width=3)
    bulan_list = ["Jan","Feb","Mar","Apr","Mei","Jun",
                  "Jul","Agu","Sep","Okt","Nov","Des"]
    buttons = [InlineKeyboardButton(b, callback_data=f"bulan_{b}") for b in bulan_list]
    markup.add(*buttons)
    markup.add(InlineKeyboardButton("🏠 Home", callback_data="home"))
    return markup

# ================= START =================
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "🏥 *SISTEM MONITORING FKRTL*\n"
        "BPJS Kesehatan\n\n"
        "Selamat datang di sistem monitoring indikator kepatuhan dan layanan fasilitas kesehatan rujukan tingkat lanjutan.\n\n"
        "Sistem ini menyediakan informasi evaluasi kinerja rumah sakit berdasarkan data yang terintegrasi.\n\n"
        "Silakan pilih menu utama di bawah ini:",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    data = get_data()

    # ===== HOME =====
    if call.data == "home":
        safe_edit(
            call.message.chat.id,
            call.message.message_id,
            "🏠 *Menu Utama*\nSilakan pilih layanan:",
            main_menu()
        )

    # ===== INDIKATOR =====
    elif call.data == "indikator":
        safe_edit(
            call.message.chat.id,
            call.message.message_id,
            "📊 *Indikator Kepatuhan*\n\nSilakan pilih bulan:",
            bulan_menu()
        )

    # ===== PILIH BULAN =====
    elif call.data.startswith("bulan_"):
        bulan = call.data.split("_")[1]
        hasil = []

        for row in data:
            if str(row.get("BULAN","")).lower() == bulan.lower():
                nama = row.get("NamaPPK","-")
                nilai = float(row.get("Nilai Kepatuhan",0))
                hasil.append((nama,nilai))

        if not hasil:
            bot.answer_callback_query(call.id,"Data tidak ada")
            return

        hasil.sort(key=lambda x: x[1], reverse=True)

        text = f"📊 *Ranking Kepatuhan Bulan {bulan}*\n\n"
        total = 0

        for i,(nama,nilai) in enumerate(hasil,1):
            icon = "🟢" if nilai >= 85 else "🔴"
            text += f"{i}. {nama} - {icon} {nilai}\n"
            total += nilai

        rata = round(total/len(hasil),2)
        terbaik = hasil[0]
        terendah = hasil[-1]

        text += f"\n📈 Rata-rata: *{rata}*"
        text += f"\n🏆 Tertinggi: {terbaik[0]} ({terbaik[1]})"
        text += f"\n⚠️ Terendah: {terendah[0]} ({terendah[1]})"

        # Grafik
        names = [x[0] for x in hasil]
        values = [x[1] for x in hasil]

        plt.figure()
        plt.bar(names, values)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig("ranking.png")
        plt.close()

        bot.send_photo(call.message.chat.id, open("ranking.png","rb"))
        bot.send_message(
            call.message.chat.id,
            text,
            parse_mode="Markdown",
            reply_markup=home_button()
        )

    # ===== MENU LAIN TERHUBUNG SHEET =====
    elif call.data in ["antrian","mobile","info","buku","sosmed"]:

        mapping = {
            "antrian":"Antrian Online",
            "mobile":"Mobile JKN",
            "info":"Informasi Lain-lain",
            "buku":"Buku Panduan",
            "sosmed":"Sosial Media"
        }

        kolom = mapping[call.data]
        text = f"📌 *{kolom}*\n\n"

        total = 0
        count = 0

        for row in data:
            nilai = float(row.get(kolom,0))
            icon = "🟢" if nilai >= 85 else "🔴"
            text += f"{row.get('NamaPPK','-')} : {icon} {nilai}\n"
            total += nilai
            count += 1

        if count > 0:
            rata = round(total/count,2)
            text += f"\n📊 Rata-rata: *{rata}*"

        safe_edit(
            call.message.chat.id,
            call.message.message_id,
            text,
            home_button()
        )

    bot.answer_callback_query(call.id)

print("Bot Running ✅")
bot.infinity_polling()
