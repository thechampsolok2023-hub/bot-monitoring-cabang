import os
import telebot
import json
import gspread
import matplotlib.pyplot as plt
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google.oauth2.service_account import Credentials
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Table
from reportlab.lib.styles import getSampleStyleSheet

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# ================= GOOGLE CONNECTION =================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

SPREADSHEET_ID = "PASTE_SPREADSHEET_ID_KAMU"
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# ================= MENU BULAN =================
def bulan_menu():
    markup = InlineKeyboardMarkup(row_width=3)
    bulan_list = ["Jan","Feb","Mar","Apr","Mei","Jun",
                  "Jul","Agu","Sep","Okt","Nov","Des"]
    buttons = [InlineKeyboardButton(b, callback_data=f"bulan_{b}") for b in bulan_list]
    markup.add(*buttons)
    return markup

# ================= START =================
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 *Selamat Datang di Sistem Monitoring FKRTL*\n\nSilakan pilih bulan:",
        reply_markup=bulan_menu(),
        parse_mode="Markdown"
    )

# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    data = sheet.get_all_records()

    # ================= PILIH BULAN =================
    if call.data.startswith("bulan_"):
        bulan = call.data.split("_")[1]

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📊 Seluruh RS", callback_data=f"all_{bulan}"),
            InlineKeyboardButton("🏥 Per RS", callback_data=f"per_{bulan}")
        )
        markup.add(
            InlineKeyboardButton("⬅️ Kembali", callback_data="back")
        )

        bot.edit_message_text(
            f"📅 Bulan *{bulan}* dipilih\nSilakan pilih tampilan:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    # ================= BACK =================
    elif call.data == "back":
        bot.edit_message_text(
            "📅 Silakan pilih bulan:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=bulan_menu()
        )

    # ================= SELURUH RS =================
    elif call.data.startswith("all_"):
        bulan = call.data.split("_")[1]
        hasil = []

        for row in data:
            if str(row.get("BULAN","")).strip().lower() == bulan.lower():
                nama = row.get("NamaPPK","-")
                nilai = float(row.get("Nilai Kepatuhan",0))
                hasil.append((nama,nilai))

        if not hasil:
            bot.answer_callback_query(call.id,"Data tidak ada")
            return

        hasil.sort(key=lambda x: x[1], reverse=True)

        text = f"📊 *RANKING BULAN {bulan}*\n\n"
        total = 0

        for i,(nama,nilai) in enumerate(hasil,1):
            icon = "🟢" if nilai >= 85 else "🔴"
            text += f"{i}. {nama} - {icon} {nilai}\n"
            total += nilai

        rata = round(total/len(hasil),2)
        text += f"\n📈 Rata-rata: *{rata}*"

        # ==== GRAFIK ====
        names = [x[0] for x in hasil]
        values = [x[1] for x in hasil]

        plt.figure()
        plt.bar(names, values)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig("ranking.png")
        plt.close()

        bot.send_photo(call.message.chat.id, open("ranking.png","rb"))
        bot.send_message(call.message.chat.id,text,parse_mode="Markdown")

        # tombol export
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📄 Export PDF", callback_data=f"pdf_{bulan}")
        )
        markup.add(
            InlineKeyboardButton("⬅️ Kembali", callback_data="back")
        )

        bot.send_message(call.message.chat.id,"Menu tambahan:",reply_markup=markup)

    # ================= PER RS =================
    elif call.data.startswith("per_"):
        bulan = call.data.split("_")[1]

        markup = InlineKeyboardMarkup(row_width=2)

        for row in data:
            if str(row.get("BULAN","")).strip().lower() == bulan.lower():
                rs = row.get("NamaPPK","-")
                markup.add(
                    InlineKeyboardButton(rs, callback_data=f"detail_{bulan}_{rs}")
                )

        markup.add(InlineKeyboardButton("⬅️ Kembali", callback_data="back"))

        bot.send_message(call.message.chat.id,"🏥 Pilih RS:",reply_markup=markup)

    # ================= DETAIL RS =================
    elif call.data.startswith("detail_"):
        _, bulan, rs = call.data.split("_",2)

        for row in data:
            if (str(row.get("BULAN","")).strip().lower() == bulan.lower()
                and row.get("NamaPPK","") == rs):

                nilai = float(row.get("Nilai Kepatuhan",0))
                icon = "🟢" if nilai >= 85 else "🔴"

                text = f"🏥 *{rs}*\n\n"
                text += f"Nilai Kepatuhan: {icon} {nilai}\n"
                text += f"Nilai TT: {row.get('Nilai (Tempat Tidur)',0)}\n"
                text += f"Nilai TMO: {row.get('Nilai (TMO)',0)}\n"
                text += f"Mobile JKN: {row.get('Mobile JKN',0)}\n"
                text += f"Waktu Tunggu: {row.get('Waktu Tunggu Layanan',0)}\n"

                bot.send_message(call.message.chat.id,text,parse_mode="Markdown")
                break

    # ================= EXPORT PDF =================
    elif call.data.startswith("pdf_"):
        bulan = call.data.split("_")[1]

        hasil = []
        for row in data:
            if str(row.get("BULAN","")).strip().lower() == bulan.lower():
                hasil.append([row.get("NamaPPK","-"), row.get("Nilai Kepatuhan",0)])

        file_name = f"laporan_{bulan}.pdf"
        doc = SimpleDocTemplate(file_name)
        elements = []

        style = getSampleStyleSheet()
        elements.append(Paragraph(f"Laporan Bulan {bulan}", style["Title"]))
        elements.append(Spacer(1,0.5*inch))

        table = Table([["Nama RS","Nilai Kepatuhan"]] + hasil)
        elements.append(table)

        doc.build(elements)

        bot.send_document(call.message.chat.id, open(file_name,"rb"))

    bot.answer_callback_query(call.id)

bot.infinity_polling()
