import os
import telebot
import json
import gspread
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google.oauth2.service_account import Credentials

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# ================= GOOGLE SHEET CONNECTION =================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

SPREADSHEET_ID = "1FiGTCl-Nny3Eqr657Q1luTQMDNwczxr-R9z1PgiorI0"
sheet = client.open_by_key(SPREADSHEET_ID).worksheet("INDIKATOR_FKRTL")


# ================= MENU BULAN =================
def bulan_menu():
    markup = InlineKeyboardMarkup(row_width=3)
    bulan_list = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
                  "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

    buttons = [InlineKeyboardButton(b, callback_data=f"bulan_{b}") for b in bulan_list]
    markup.add(*buttons)
    return markup


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "📊 *Monitoring Indikator Kepatuhan*\n\n"
        "Silakan pilih bulan:",
        reply_markup=bulan_menu(),
        parse_mode="Markdown"
    )


# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):

    if call.data.startswith("bulan_"):
        bulan_dipilih = call.data.split("_")[1]

        data = sheet.get_all_records()

        hasil = []
        for row in data:
            if row["BULAN"] == bulan_dipilih:
                nama = row["Nama PPK"]
                nilai = float(row["Nilai Kepatuhan"])
                hasil.append((nama, nilai))

        if not hasil:
            bot.send_message(call.message.chat.id, "Data tidak ditemukan.")
            return

        # Ranking
        hasil.sort(key=lambda x: x[1], reverse=True)

        ranking_text = f"📊 *Ranking Indikator - {bulan_dipilih}*\n\n"
        total = 0

        for i, (nama, nilai) in enumerate(hasil, start=1):
            medal = ["🥇", "🥈", "🥉"]
            icon = medal[i-1] if i <= 3 else f"{i}️⃣"
            ranking_text += f"{icon} {nama} - {nilai}\n"
            total += nilai

        rata2 = round(total / len(hasil), 2)

        ranking_text += f"\n📊 Rata-rata Cabang: *{rata2}*\n"

        # Area of Improvement
        improvement = [f"{n} - {v}" for n, v in hasil if v < 85]

        if improvement:
            ranking_text += "\n⚠️ *Area of Improvement (<85)*\n"
            ranking_text += "\n".join(improvement)

        bot.send_message(
            call.message.chat.id,
            ranking_text,
            parse_mode="Markdown"
        )

    bot.answer_callback_query(call.id)


bot.infinity_polling()
