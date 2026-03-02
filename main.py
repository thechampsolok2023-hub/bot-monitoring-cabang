import os
import telebot
import json
import gspread
import matplotlib.pyplot as plt
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google.oauth2.service_account import Credentials
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

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

# ================= MENU =================
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

def tahun_menu():
    data = sheet.get_all_records()
    tahun_set = {str(row.get("TAHUN","")).strip() for row in data if row.get("TAHUN")}
    tahun_sorted = sorted(tahun_set, reverse=True)

    markup = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton(t, callback_data=f"tahun_{t}") for t in tahun_sorted]
    markup.add(*buttons)
    markup.add(InlineKeyboardButton("🏠 Home", callback_data="home"))
    return markup

# ================= START =================
@bot.message_handler(commands=['start'])
def start(message):
    nama_user = message.from_user.full_name
    bot.send_message(
        message.chat.id,
        f"🏥 *SISTEM MONITORING FKRTL*\n"
        f"BPJS Kesehatan\n"
        f"Kantor Cabang Solok\n\n"
        f"Yth. *{nama_user}*,\n\n"
        "Selamat datang di Sistem Monitoring FKRTL.\n\n"
        "Silakan memilih menu utama.",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    data = sheet.get_all_records()

    if call.data == "home":
        bot.edit_message_text(
            "🏠 *Menu Utama*\nSilakan pilih layanan:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )

    elif call.data == "indikator":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📊 Seluruh Faskes", callback_data="indikator_all"),
            InlineKeyboardButton("🏥 Per Faskes", callback_data="indikator_rs"),
        )
        markup.add(InlineKeyboardButton("🏠 Home", callback_data="home"))

        bot.edit_message_text(
            "Silakan pilih jenis laporan:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )

    elif call.data == "indikator_all":
        bot.edit_message_text(
            "📊 Pilih Tahun:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=tahun_menu()
        )

    elif call.data == "indikator_rs":
        bot.edit_message_text(
            "🏥 Pilih Tahun untuk melihat detail per Faskes:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=tahun_menu()
        )

    elif call.data.startswith("tahun_"):
        tahun = call.data.split("_")[1]
        bulan_set = {
            str(row.get("BULAN","")).strip()
            for row in data
            if str(row.get("TAHUN","")) == tahun
        }

        urutan = ["Januari","Februari","Maret","April","Mei","Juni",
                  "Juli","Agustus","September","Oktober","November","Desember"]

        bulan_sorted = [b for b in urutan if b in bulan_set]

        markup = InlineKeyboardMarkup(row_width=3)
        buttons = [
            InlineKeyboardButton(b, callback_data=f"bulan_{tahun}_{b}")
            for b in bulan_sorted
        ]
        markup.add(*buttons)
        markup.add(InlineKeyboardButton("🏠 Home", callback_data="home"))

        bot.edit_message_text(
            f"📅 Tahun {tahun}\nPilih Bulan:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )

    elif call.data.startswith("bulan_"):

        _, tahun, bulan = call.data.split("_")
        hasil = []

        for row in data:
            if (str(row.get("TAHUN","")) == tahun and
                bulan.lower() in str(row.get("BULAN","")).lower()):

                nama = row.get("NamaPPK","-").split("(")[0].strip()
                nilai = float(row.get("Nilai Kepatuhan") or 0)

                if nilai > 100:
                    nilai = nilai / 100

                hasil.append((nama,nilai))

        if not hasil:
            bot.answer_callback_query(call.id,"Data tidak ada")
            return

        hasil.sort(key=lambda x: x[1], reverse=True)

        text = f"📊 *RANKING INDIKATOR KEPATUHAN*\n📅 {bulan} {tahun}\n\n"

        total = 0
        for i,(nama,nilai) in enumerate(hasil,1):
            icon = "🟢" if nilai >= 85 else "🟡" if nilai >= 75 else "🔴"
            nilai_format = f"{nilai:.2f}".replace(".", ",")
            text += f"{i}. {nama} - {icon} {nilai_format}%\n"
            total += nilai

        rata = total / len(hasil)
        text += f"\n📈 *Rata-rata:* {rata:.2f}%"

        # Grafik
        names = [x[0] for x in hasil]
        values = [x[1] for x in hasil]

        plt.figure(figsize=(8,6))
        plt.barh(names, values)
        plt.xlim(0,100)
        plt.xlabel("Nilai Kepatuhan (%)")
        plt.title(f"Ranking Kepatuhan - {bulan} {tahun}")
        plt.gca().invert_yaxis()
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

    bot.answer_callback_query(call.id)

print("Bot started ✅")
bot.infinity_polling()
