import os
import telebot
import json
import gspread
import matplotlib.pyplot as plt
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google.oauth2.service_account import Credentials
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# ================= ENV =================

TOKEN = os.getenv("BOT_TOKEN")
creds_env = os.getenv("GOOGLE_CREDENTIALS")

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
        InlineKeyboardButton("ℹ️ Informasi Lain", callback_data="info")
    )

    return markup


def home_button():

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏠 Home", callback_data="home"))
    return markup


# ================= AI INSIGHT =================

def generate_insight(hasil, rata, bulan, tahun):

    tertinggi_nama, tertinggi_nilai = hasil[0]
    terendah_nama, terendah_nilai = hasil[-1]

    rs_dibawah = [x for x in hasil if x[1] < 85]

    text = f"""
INSIGHT ANALISIS

Rata-rata kepatuhan cabang pada periode {bulan} {tahun} adalah {rata:.2f}%.

RS dengan performa terbaik adalah {tertinggi_nama} dengan nilai {tertinggi_nilai:.2f}%.

RS dengan nilai terendah adalah {terendah_nama} dengan nilai {terendah_nilai:.2f}%.
"""

    if rs_dibawah:
        text += f"\nTerdapat {len(rs_dibawah)} RS yang masih berada di bawah target 85%."
    else:
        text += "\nSeluruh RS telah memenuhi target ≥85%."

    return text


# ================= START =================

@bot.message_handler(commands=['start'])
def start(message):

    bot.send_message(
        message.chat.id,
        "🏥 *SISTEM MONITORING FKRTL*\n\nSilakan pilih menu:",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


# ================= CALLBACK =================

@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    data = sheet.get_all_records()

    # ================= HOME =================

    if call.data == "home":

        bot.edit_message_text(
            "🏠 Menu Utama",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu()
        )


    # ================= MENU INDIKATOR =================

    elif call.data == "indikator":

        markup = InlineKeyboardMarkup()

        markup.add(
            InlineKeyboardButton("📊 Seluruh Faskes", callback_data="all"),
            InlineKeyboardButton("🏥 Per Faskes", callback_data="rs")
        )

        markup.add(InlineKeyboardButton("🏠 Home", callback_data="home"))

        bot.edit_message_text(
            "Pilih jenis laporan:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )


    # ================= MODE =================

    elif call.data == "all":

        user_state[call.from_user.id] = "ALL"

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("2025", callback_data="tahun_2025"))

        bot.edit_message_text(
            "Pilih Tahun:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )


    # ================= PILIH TAHUN =================

    elif call.data.startswith("tahun_"):

        tahun = call.data.split("_")[1]

        markup = InlineKeyboardMarkup(row_width=3)

        # ambil bulan yang ada datanya di sheet
        bulan_set = {
            str(row.get("BULAN","")).strip()
            for row in data
            if str(row.get("TAHUN","")).strip() == tahun
        }

        # urutan bulan normal
        urutan_bulan = [
        "Januari","Februari","Maret","April","Mei","Juni",
        "Juli","Agustus","September","Oktober","November","Desember"
        ]

        # hanya tampilkan bulan yang ada datanya
        bulan_sorted = [b for b in urutan_bulan if b in bulan_set]

        for b in bulan_sorted:
            markup.add(
                InlineKeyboardButton(b, callback_data=f"bulan_{tahun}_{b}")
            )

        markup.add(InlineKeyboardButton("🏠 Home", callback_data="home"))

        bot.edit_message_text(
            f"Tahun {tahun}\nPilih Bulan:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )


    # ================= PILIH BULAN =================

    elif call.data.startswith("bulan_"):

        _, tahun, bulan = call.data.split("_")

        filtered = []

        for row in data:

            tahun_row = str(row.get("TAHUN", "")).strip()
            bulan_row = str(row.get("BULAN", "")).strip().lower()

            if tahun_row == tahun and bulan.lower() in bulan_row:
                filtered.append(row)

        if not filtered:

            bot.answer_callback_query(call.id, "Data tidak ada")
            return

        # ================= HITUNG DATA =================

        hasil = []
        total = 0

        for row in filtered:

            nama = row.get("NamaPPK","-").split("(")[0].strip()

            nilai_str = str(row.get("Nilai Kepatuhan","0")).replace(",",".")
            nilai = float(nilai_str)

            hasil.append((nama,nilai))
            total += nilai

        hasil.sort(key=lambda x: x[1], reverse=True)
        top5 = hasil[:5]

        ranking_text = ""
        for i, (nama, nilai) in enumerate(top5, 1):
            ranking_text += f"{i}. {nama} ({nilai:.2f}%)\n"

        rata = total/len(hasil)

        tertinggi_nama, tertinggi_nilai = hasil[0]
        terendah_nama, terendah_nilai = hasil[-1]

        rs_bawah = [(n,v) for n,v in hasil if v < 85]

        if rs_bawah:

            daftar = "\n".join(
            [f"- {n} ({v:.2f}%)" for n,v in rs_bawah]
            )

        else:

            daftar = "Tidak ada 🎉"


        # ================= TOP 5 =================

        ranking_text = ""

        for i, (nama, nilai) in enumerate(hasil, 1):
            ranking_text += f"{i}. {nama} ({nilai:.2f}%)\n"


        # ================= GRAFIK =================

        names = [x[0] for x in hasil]
        values = [x[1] for x in hasil]

        colors_bar = []

        for n,v in hasil:

            if n == terendah_nama:
                colors_bar.append("orange")

            elif v >= 85:
                colors_bar.append("green")

            else:
                colors_bar.append("red")

        plt.figure(figsize=(10,6))

        bars = plt.barh(names, values, color=colors_bar)

        plt.axvline(85, linestyle="--")

        plt.xlabel("Nilai Kepatuhan (%)")
        plt.title(f"Dashboard Kepatuhan {bulan} {tahun}")

        plt.gca().invert_yaxis()

        for bar in bars:

            width = bar.get_width()

            plt.text(width+1,
                     bar.get_y()+bar.get_height()/2,
                     f"{width:.2f}%",
                     va="center")

        plt.tight_layout()

        plt.savefig("grafik.png")
        plt.close()


        # ================= PDF =================

        pdf = f"Dashboard_{bulan}_{tahun}.pdf"

        styles = getSampleStyleSheet()

        elements = []

        elements.append(Paragraph("DASHBOARD EKSEKUTIF", styles['Title']))
        elements.append(Spacer(1,20))

        elements.append(Paragraph(f"Periode : {bulan} {tahun}", styles['Normal']))
        elements.append(Paragraph(f"Jumlah RS : {len(hasil)}", styles['Normal']))
        elements.append(Paragraph(f"Rata-rata : {rata:.2f}%", styles['Normal']))

        elements.append(Spacer(1,20))

        elements.append(Image("grafik.png", width=6*inch, height=4*inch))

        elements.append(Spacer(1,20))

        insight = generate_insight(hasil,rata,bulan,tahun)

        elements.append(Paragraph(insight.replace("\n","<br/>"), styles['Normal']))

        doc = SimpleDocTemplate(pdf)

        doc.build(elements)

        with open(pdf, "rb") as file:
            bot.send_document(call.message.chat.id, file)


        # ================= TEXT =================

text = (
    f"📊 *DASHBOARD EKSEKUTIF*\n"
    f"📅 {bulan} {tahun}\n\n"
    f"Jumlah RS : {len(hasil)}\n"
    f"Rata-rata Cabang : {rata:.2f}%\n\n"
    f"🏆 Ranking Kepatuhan RS\n"
    f"{ranking_text}\n"
    f"🥇 Tertinggi : {tertinggi_nama} ({tertinggi_nilai:.2f}%)\n"
    f"🔻 Terendah : {terendah_nama} ({terendah_nilai:.2f}%)\n\n"
    f"🔴 RS < 85%:\n{daftar}\n\n"
    f"{generate_insight(hasil, rata, bulan, tahun)}"
)
        bot.send_message(
            call.message.chat.id,
            text,
            parse_mode="Markdown",
            reply_markup=home_button()
        )

    bot.answer_callback_query(call.id)

print("Bot started ✅")
bot.infinity_polling(none_stop=True)
