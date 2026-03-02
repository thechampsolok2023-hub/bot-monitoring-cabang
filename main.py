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


# ================= MENU TAHUN DINAMIS =================
def tahun_menu():
    data = sheet.get_all_records()
    tahun_set = set()

    for row in data:
        tahun = str(row.get("TAHUN", "")).strip()
        if tahun:
            tahun_set.add(tahun)

    tahun_sorted = sorted(tahun_set, reverse=True)

    markup = InlineKeyboardMarkup(row_width=3)
    buttons = [
        InlineKeyboardButton(t, callback_data=f"tahun_{t}")
        for t in tahun_sorted
    ]
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
        "Selamat datang di Sistem Monitoring Fasilitas Kesehatan Rujukan Tingkat Lanjutan (FKRTL).\n\n"
        "Sistem ini digunakan untuk memantau dan mengevaluasi indikator kepatuhan serta kinerja layanan rumah sakit berdasarkan data terintegrasi.\n\n"
        "Silakan memilih menu utama untuk mengakses informasi yang dibutuhkan.",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

def generate_pdf(hasil, bulan, tahun, rata, terbaik, terendah):

    doc = SimpleDocTemplate(
        "Laporan_Indikator_Kepatuhan.pdf"
    )

    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>SISTEM MONITORING FKRTL</b>", styles["Title"]))
    elements.append(Paragraph("BPJS Kesehatan - Kantor Cabang Solok", styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(f"<b>Laporan Indikator Kepatuhan</b>", styles["Heading2"]))
    elements.append(Paragraph(f"{bulan} {tahun}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    # Tabel
    data_table = [["No","Nama Faskes","Nilai (%)"]]

    for i,(nama,nilai) in enumerate(hasil,1):
        nilai_format = f"{nilai:.2f}".replace(".", ",")
        data_table.append([i,nama,nilai_format])

    table = Table(data_table, colWidths=[40,300,80])

    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#005BAC")),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('ALIGN',(2,1),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,-1),'Helvetica'),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    rata_format = f"{rata:.2f}".replace(".", ",")
    terbaik_format = f"{terbaik[1]:.2f}".replace(".", ",")
    terendah_format = f"{terendah[1]:.2f}".replace(".", ",")

    elements.append(Paragraph(f"<b>Rata-rata:</b> {rata_format}%", styles["Normal"]))
    elements.append(Paragraph(f"<b>Tertinggi:</b> {terbaik[0]} ({terbaik_format}%)", styles["Normal"]))
    elements.append(Paragraph(f"<b>Terendah:</b> {terendah[0]} ({terendah_format}%)", styles["Normal"]))

    doc.build(elements)
# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    data = sheet.get_all_records()

    # ===== HOME =====
    if call.data == "home":
        bot.edit_message_text(
            "🏠 *Menu Utama*\nSilakan pilih layanan:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )

    # ===== INDIKATOR → PILIH TAHUN =====
    elif call.data == "indikator":
        bot.edit_message_text(
            "📊 Pilih Tahun:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=tahun_menu()
        )

    # ===== PILIH TAHUN → PILIH BULAN =====
    elif call.data.startswith("tahun_"):

        tahun = call.data.split("_")[1]
        bulan_set = set()

        for row in data:
            if str(row.get("TAHUN", "")) == tahun:
                bulan = str(row.get("BULAN", "")).strip()
                if bulan:
                    bulan_set.add(bulan)

        urutan_bulan = [
            "Januari","Februari","Maret","April",
            "Mei","Juni","Juli","Agustus",
            "September","Oktober","November","Desember"
        ]

        bulan_sorted = [b for b in urutan_bulan if b in bulan_set]

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

            # ===== PILIH BULAN → TAMPILKAN RANKING =====
    elif call.data.startswith("bulan_"):

        _, tahun, bulan = call.data.split("_")

        hasil = []

        for row in data:
            if (str(row.get("TAHUN","")) == tahun and
                bulan.lower() in str(row.get("BULAN","")).lower()):

                nama_full = row.get("NamaPPK","-")

                # Hilangkan kode faskes
                if "(" in nama_full:
                    nama = nama_full.split("(")[0].strip()
                else:
                    nama = nama_full.strip()

                # Potong otomatis jika terlalu panjang
                if len(nama) > 28:
                    nama = nama[:25] + "..."

                nilai_raw = float(row.get("Nilai Kepatuhan") or 0)

                # Normalisasi
                if nilai_raw > 100:
                    nilai = nilai_raw / 100
                else:
                    nilai = nilai_raw

                hasil.append((nama,nilai))

        if not hasil:
            bot.answer_callback_query(call.id,"Data tidak ada")
            return

        hasil.sort(key=lambda x: x[1], reverse=True)

        terbaik = hasil[0]
        terendah = hasil[-1]

        text = f"📊 *RANKING INDIKATOR KEPATUHAN*\n"
        text += f"📅 {bulan} {tahun}\n\n"

        total = 0

        for i,(nama,nilai) in enumerate(hasil,1):

            if nilai >= 85:
                icon = "🟢"
            elif nilai >= 75:
                icon = "🟡"
            else:
                icon = "🔴"

            nilai_format = f"{nilai:.2f}".replace(".", ",")
            text += f"{i}. {nama} - {icon} {nilai_format}%\n"
            total += nilai

        rata = total / len(hasil)
        rata_format = f"{rata:.2f}".replace(".", ",")

        terbaik_format = f"{terbaik[1]:.2f}".replace(".", ",")
        terendah_format = f"{terendah[1]:.2f}".replace(".", ",")

        text += f"\n📈 *Rata-rata:* {rata_format}%"
        text += f"\n🏆 *Tertinggi:* {terbaik[0]} ({terbaik_format}%)"
        text += f"\n⚠️ *Terendah:* {terendah[0]} ({terendah_format}%)"

        # ====== GRAFIK HORIZONTAL PROFESIONAL ======
        names = [x[0] for x in hasil]
        values = [x[1] for x in hasil]

        plt.figure(figsize=(8,6))
        bars = plt.barh(names, values)
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
