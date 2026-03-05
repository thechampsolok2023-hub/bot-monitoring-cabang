import os
import telebot
import json
import gspread
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google.oauth2.service_account import Credentials

# ================= ENV =================
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN tidak ditemukan")

creds_env = os.getenv("GOOGLE_CREDENTIALS")
if not creds_env:
    raise ValueError("GOOGLE_CREDENTIALS tidak ditemukan")

bot = telebot.TeleBot(TOKEN)

# ================= STATE =================
user_state = {}

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
    tahun_set = {str(row.get("TAHUN", "")).strip() for row in data if row.get("TAHUN")}
    tahun_sorted = sorted(tahun_set, reverse=True)

    markup = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton(t, callback_data=f"tahun_{t}") for t in tahun_sorted]
    markup.add(*buttons)
    markup.add(InlineKeyboardButton("🏠 Home", callback_data="home"))
    return markup

# ================= AI INSIGHT =================
def generate_insight(hasil, rata, bulan, tahun):

    tertinggi_nama, tertinggi_nilai = hasil[0]
    terendah_nama, terendah_nilai = hasil[-1]

    rs_dibawah = [x for x in hasil if x[1] < 85]

    insight = f"""
INSIGHT ANALISIS

Rata-rata kepatuhan cabang pada periode {bulan} {tahun} adalah {rata:.2f}%.

RS dengan performa terbaik adalah {tertinggi_nama} dengan nilai {tertinggi_nilai:.2f}%.

RS dengan nilai terendah adalah {terendah_nama} dengan nilai {terendah_nilai:.2f}%.
"""

    if rs_dibawah:
        insight += f"\nTerdapat {len(rs_dibawah)} RS yang masih berada di bawah target kepatuhan 85%."
    else:
        insight += "\nSeluruh RS telah memenuhi target kepatuhan ≥ 85%."

    return insight
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

    # ================= HOME =================
    if call.data == "home":

        bot.edit_message_text(
            "🏠 *Menu Utama*\nSilakan pilih layanan:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )

    # ================= MENU INDIKATOR =================
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

    # ================= PILIH MODE =================
    elif call.data == "indikator_all":

        user_state[call.from_user.id] = "ALL"

        bot.edit_message_text(
            "📊 Pilih Tahun:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=tahun_menu()
        )

    elif call.data == "indikator_rs":

        user_state[call.from_user.id] = "RS"

        bot.edit_message_text(
            "🏥 Pilih Tahun:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=tahun_menu()
        )

    # ================= PILIH TAHUN =================
    elif call.data.startswith("tahun_"):

        tahun = call.data.split("_")[1]

        bulan_set = {
            str(row.get("BULAN", "")).strip()
            for row in data
            if str(row.get("TAHUN", "")) == tahun
        }

        urutan = [
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]

        bulan_sorted = [b for b in urutan if b in bulan_set]

        markup = InlineKeyboardMarkup(row_width=3)

        for b in bulan_sorted:
            markup.add(InlineKeyboardButton(b, callback_data=f"bulan_{tahun}_{b}"))

        markup.add(InlineKeyboardButton("🏠 Home", callback_data="home"))

        bot.edit_message_text(
            f"📅 Tahun {tahun}\nPilih Bulan:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )

    # ================= PILIH BULAN =================
    elif call.data.startswith("bulan_"):

        _, tahun, bulan = call.data.split("_")
        mode = user_state.get(call.from_user.id)

        filtered = [
            row for row in data
            if str(row.get("TAHUN", "")) == tahun
            and bulan.lower() in str(row.get("BULAN", "")).lower()
        ]

        if not filtered:
            bot.answer_callback_query(call.id, "Data tidak ada")
            return

        # ================= MODE ALL =================
        if mode == "ALL":

            hasil = []
            total = 0

            for row in filtered:
                nama = row.get("NamaPPK","-").split("(")[0].strip()
                nilai = float(row.get("Nilai Kepatuhan") or 0)

            hasil.append((nama, nilai))
            total += nilai

        hasil.sort(key=lambda x: x[1], reverse=True)

        top5 = hasil[:5]
        ranking_text = ""

        for i,(nama,nilai) in enumerate(top5,1):
            ranking_text += f"{i}. {nama} ({nilai:.2f}%)\n"

        rata = total / len(hasil)

        tertinggi_nama, tertinggi_nilai = hasil[0]
        terendah_nama, terendah_nilai = hasil[-1]

        rs_dibawah_85 = [(n, v) for n, v in hasil if v < 85]

        if rs_dibawah_85:
            daftar = "\n".join(
                [f"- {n} ({v:.2f}%)" for n, v in rs_dibawah_85]
            )
        else:
            daftar = "Tidak ada 🎉"

        insight = generate_insight(hasil, rata, bulan, tahun)

        text = (
            f"📊 *DASHBOARD EKSEKUTIF*\n"
            f"📅 {bulan} {tahun}\n\n"
            f"Jumlah RS : {len(hasil)}\n"
            f"Rata-rata Cabang : {rata:.2f}%\n\n"
            f"🏆 *Top 5 Kepatuhan*\n"
            f"{ranking_text}\n"
            f"🥇 Tertinggi : {tertinggi_nama} ({tertinggi_nilai:.2f}%)\n"
            f"🔻 Terendah : {terendah_nama} ({terendah_nilai:.2f}%)\n\n"
            f"🔴 RS < 85%:\n{daftar}\n\n"
            f"{insight}"
        )

        bot.send_message(
            call.message.chat.id,
            text,
            parse_mode="Markdown",
            reply_markup=home_button()
        )
        # ================= MODE RS =================
        elif mode == "RS":

            rs_list = sorted({
                row.get("NamaPPK", "-").split("(")[0].strip()
                for row in filtered
            })

            markup = InlineKeyboardMarkup(row_width=1)

            for rs in rs_list:
                markup.add(
                    InlineKeyboardButton(
                        rs,
                        callback_data=f"detail_{tahun}_{bulan}_{rs}"
                    )
                )

            markup.add(InlineKeyboardButton("🏠 Home", callback_data="home"))

            bot.edit_message_text(
                f"🏥 Pilih Faskes\n📅 {bulan} {tahun}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )

    # ================= DETAIL RS =================
    elif call.data.startswith("detail_"):

        _, tahun, bulan, rs_nama = call.data.split("_", 3)

        filtered = [
            row for row in data
            if str(row.get("TAHUN", "")) == tahun
            and bulan.lower() in str(row.get("BULAN", "")).lower()
            and rs_nama in row.get("NamaPPK", "")
        ]

        if not filtered:
            bot.answer_callback_query(call.id, "Data tidak ada")
            return

        nilai = float(filtered[0].get("Nilai Kepatuhan") or 0)

        text = (
            f"🏥 *{rs_nama}*\n"
            f"📅 {bulan} {tahun}\n\n"
            f"Nilai Kepatuhan : {nilai:.2f}%"
        )

        bot.send_message(
            call.message.chat.id,
            text,
            parse_mode="Markdown",
            reply_markup=home_button()
        )

    bot.answer_callback_query(call.id)


print("Bot started ✅")
bot.infinity_polling(none_stop=True, skip_pending=True)
