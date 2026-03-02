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

@bot.message_handler(commands=['start'])
def start(message):

    nama_user = message.from_user.full_name

    bot.send_message(
        message.chat.id,
        f"🏥 *SISTEM MONITORING FKRTL*\n"
        f"BPJS Kesehatan\n"
        f"Kantor Cabang Solok\n\n"
        f"Yth. *{nama_user}*,\n\n"
        "Selamat datang di Sistem Monitoring Fasilitas Kesehatan Rujukan Tingkat Lanjutan (FKRTL).\n\n"
        "Sistem ini digunakan untuk memantau dan mengevaluasi indikator kepatuhan serta kinerja layanan rumah sakit berdasarkan data terintegrasi.\n\n"
        "Silakan memilih menu utama untuk mengakses informasi yang dibutuhkan.",
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
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("📊 Seluruh RS", callback_data="indikator_all"),
            InlineKeyboardButton("🏥 Per Rumah Sakit", callback_data="indikator_per"),
            InlineKeyboardButton("🏠 Home", callback_data="home")
        )

        safe_edit(
            call.message.chat.id,
            call.message.message_id,
            "📊 *Indikator Kepatuhan*\n\nSilakan pilih tampilan:",
            markup
        )

    # ===== SELURUH RS =====
    elif call.data == "indikator_all":
        safe_edit(
            call.message.chat.id,
            call.message.message_id,
            "📊 *Seluruh RS*\n\nSilakan pilih bulan:",
            bulan_menu()
        )

    # ===== PER RUMAH SAKIT =====
    elif call.data == "indikator_per":

        rs_list = sorted(set(row.get("NamaPPK","-") for row in data))
        markup = InlineKeyboardMarkup(row_width=1)

        for rs in rs_list:
            markup.add(
                InlineKeyboardButton(rs, callback_data=f"detailrs_{rs}")
            )

        markup.add(InlineKeyboardButton("🏠 Home", callback_data="home"))

        safe_edit(
            call.message.chat.id,
            call.message.message_id,
            "🏥 *Pilih Rumah Sakit:*",
            markup
        )

    # ===== DETAIL PER RS =====
    elif call.data.startswith("detailrs_"):

        rs = call.data.replace("detailrs_","")
        text = f"🏥 *{rs}*\n\n"

        total = 0
        count = 0

        for row in data:
            if row.get("NamaPPK","") == rs:
                bulan = row.get("BULAN","-")
                nilai = float(row.get("Nilai Kepatuhan",0))
                icon = "🟢" if nilai >= 85 else "🔴"
                text += f"{bulan} : {icon} {nilai}\n"
                total += nilai
                count += 1

        if count > 0:
            rata = round(total/count,2)
            text += f"\n📈 Rata-rata Tahunan: *{rata}*"

        safe_edit(
            call.message.chat.id,
            call.message.message_id,
            text,
            home_button()
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
