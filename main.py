import os
import json
import time
import math
import html
import signal
import sys
import logging
import tempfile
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv()

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.apihelper import ApiTelegramException

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import gspread
from google.oauth2.service_account import Credentials

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch


# =========================================================
# CONFIG
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_CREDENTIALS_ENV = os.getenv("GOOGLE_CREDENTIALS")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1FiGTCl-Nny3Eqr657Q1luTQMDNwczxr-R9z1PgiorI0")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME")

TARGET_KEPATUHAN = 85.0
CACHE_TTL_SECONDS = 60
HOSPITALS_PER_PAGE = 8

COL_YEAR = "TAHUN"
COL_MONTH = "BULAN"
COL_HOSPITAL = "NamaPPK"
COL_SCORE = "Nilai Kepatuhan"

REQUIRED_COLUMNS = [COL_YEAR, COL_MONTH, COL_HOSPITAL, COL_SCORE]

MONTH_ORDER = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN belum diset.")

if not GOOGLE_CREDENTIALS_ENV:
    raise ValueError("GOOGLE_CREDENTIALS belum diset.")


# =========================================================
# BOT
# =========================================================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


# =========================================================
# STATE & CACHE
# =========================================================

user_sessions = {}
data_cache = {
    "rows": None,
    "ts": 0
}


# =========================================================
# GOOGLE SHEETS
# =========================================================

def load_google_credentials():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    raw = GOOGLE_CREDENTIALS_ENV.strip()

    if raw.startswith("{"):
        creds_dict = json.loads(raw)
        return Credentials.from_service_account_info(creds_dict, scopes=scopes)

    if os.path.exists(raw):
        return Credentials.from_service_account_file(raw, scopes=scopes)

    raise ValueError("GOOGLE_CREDENTIALS harus berupa JSON service account atau path file JSON.")


def get_sheet():
    creds = load_google_credentials()
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    if WORKSHEET_NAME:
        return spreadsheet.worksheet(WORKSHEET_NAME)

    return spreadsheet.sheet1


sheet = get_sheet()


def validate_sheet_columns(rows):
    if not rows:
        return

    first_row = rows[0]
    missing = [col for col in REQUIRED_COLUMNS if col not in first_row]
    if missing:
        raise ValueError(f"Kolom wajib tidak ditemukan di sheet: {', '.join(missing)}")


def fetch_records(force=False):
    now = time.time()

    if (
        not force
        and data_cache["rows"] is not None
        and now - data_cache["ts"] < CACHE_TTL_SECONDS
    ):
        return data_cache["rows"]

    rows = sheet.get_all_records()
    validate_sheet_columns(rows)

    data_cache["rows"] = rows
    data_cache["ts"] = now
    logging.info("Data sheet loaded: %s rows", len(rows))
    return rows


def clear_cache():
    data_cache["rows"] = None
    data_cache["ts"] = 0


# =========================================================
# HELPERS
# =========================================================

def handle_exit(signum, frame):
    logging.info("Bot stopped.")
    sys.exit(0)


signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)


def escape(value):
    return html.escape(str(value))


def safe_answer_callback(call, text=""):
    try:
        bot.answer_callback_query(call.id, text=text)
    except Exception:
        pass


def safe_edit_message(call, text, reply_markup=None):
    try:
        bot.edit_message_text(
            text=text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    except ApiTelegramException as e:
        if "message is not modified" in str(e).lower():
            return
        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )


def reset_user_session(user_id):
    user_sessions[user_id] = {
        "mode": None,
        "year": None,
        "month": None,
        "hospital_list": []
    }


def ensure_user_session(user_id):
    if user_id not in user_sessions:
        reset_user_session(user_id)
    return user_sessions[user_id]


def normalize_month(value):
    return str(value).strip().capitalize()


def normalize_hospital_name(value):
    if value is None:
        return "-"
    return str(value).split("(")[0].strip()


def parse_score(value):
    try:
        if value is None:
            return 0.0

        s = str(value).strip().replace("%", "").replace(" ", "")
        if not s:
            return 0.0

        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        else:
            s = s.replace(",", ".")

        return float(s)
    except Exception:
        return 0.0


def get_years(rows):
    years = {
        str(row.get(COL_YEAR, "")).strip()
        for row in rows
        if str(row.get(COL_YEAR, "")).strip()
    }

    def sort_key(x):
        return (0, int(x)) if x.isdigit() else (1, x)

    return sorted(years, key=sort_key)


def get_months_for_year(rows, year):
    month_set = {
        normalize_month(row.get(COL_MONTH, ""))
        for row in rows
        if str(row.get(COL_YEAR, "")).strip() == str(year).strip()
    }
    return [m for m in MONTH_ORDER if m in month_set]


def get_rows_for_period(rows, year, month):
    result = []

    for row in rows:
        row_year = str(row.get(COL_YEAR, "")).strip()
        row_month = normalize_month(row.get(COL_MONTH, ""))

        if row_year == str(year).strip() and row_month == normalize_month(month):
            result.append({
                "nama": normalize_hospital_name(row.get(COL_HOSPITAL, "-")),
                "nilai": parse_score(row.get(COL_SCORE, 0)),
                "raw": row
            })

    return result


def aggregate_hospitals(period_rows):
    grouped = defaultdict(list)

    for item in period_rows:
        grouped[item["nama"]].append(item["nilai"])

    result = []
    for nama, values in grouped.items():
        avg_score = sum(values) / len(values)
        result.append((nama, avg_score))

    result.sort(key=lambda x: x[1], reverse=True)
    return result


def build_all_summary(rows, month, year):
    if not rows:
        return None

    total = sum(v for _, v in rows)
    avg = total / len(rows)
    highest_name, highest_score = rows[0]
    lowest_name, lowest_score = rows[-1]
    below_target = [(n, v) for n, v in rows if v < TARGET_KEPATUHAN]

    insight_lines = [
        f"Rata-rata kepatuhan pada periode {month} {year} adalah {avg:.2f}%.",
        f"RS terbaik adalah {highest_name} dengan nilai {highest_score:.2f}%.",
        f"RS dengan nilai terendah adalah {lowest_name} dengan nilai {lowest_score:.2f}%."
    ]

    if below_target:
        insight_lines.append(
            f"Terdapat {len(below_target)} RS yang masih berada di bawah target {TARGET_KEPATUHAN:.0f}%."
        )
    else:
        insight_lines.append(f"Seluruh RS telah memenuhi target ≥ {TARGET_KEPATUHAN:.0f}%.")

    return {
        "mode": "all",
        "month": month,
        "year": year,
        "rows": rows,
        "avg": avg,
        "highest_name": highest_name,
        "highest_score": highest_score,
        "lowest_name": lowest_name,
        "lowest_score": lowest_score,
        "below_target": below_target,
        "insight": "\n".join(insight_lines)
    }


def build_single_summary(all_rows, hospital_name, month, year):
    selected = None
    for nama, nilai in all_rows:
        if nama == hospital_name:
            selected = (nama, nilai)
            break

    if not selected:
        return None

    rank = next((i for i, (nama, _) in enumerate(all_rows, 1) if nama == hospital_name), None)
    total = sum(v for _, v in all_rows)
    avg = total / len(all_rows)

    hospital, score = selected
    status = "Memenuhi Target" if score >= TARGET_KEPATUHAN else "Di Bawah Target"
    gap = score - TARGET_KEPATUHAN

    insight_lines = [
        f"{hospital} memiliki nilai kepatuhan {score:.2f}% pada periode {month} {year}.",
        f"Peringkat {hospital} adalah #{rank} dari total {len(all_rows)} RS.",
        f"Rata-rata seluruh RS pada periode ini adalah {avg:.2f}%."
    ]

    if score >= TARGET_KEPATUHAN:
        insight_lines.append(f"Nilai sudah melampaui target {TARGET_KEPATUHAN:.0f}% sebesar {gap:.2f} poin.")
    else:
        insight_lines.append(f"Nilai masih di bawah target {TARGET_KEPATUHAN:.0f}% sebesar {abs(gap):.2f} poin.")

    return {
        "mode": "single",
        "month": month,
        "year": year,
        "hospital": hospital,
        "score": score,
        "rank": rank,
        "total_rs": len(all_rows),
        "avg_all": avg,
        "status": status,
        "gap": gap,
        "insight": "\n".join(insight_lines)
    }


def get_top_rows(rows, n=10):
    return rows[:n]


def get_bottom_rows(rows, n=10):
    return sorted(rows, key=lambda x: x[1])[:n]


# =========================================================
# MENUS
# =========================================================

def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Indikator Kepatuhan", callback_data="indikator"),
        InlineKeyboardButton("🏥 Antrian Online", callback_data="antrian"),
        InlineKeyboardButton("📱 Mobile JKN", callback_data="mobile"),
        InlineKeyboardButton("ℹ️ Informasi Lain", callback_data="info"),
    )
    markup.add(InlineKeyboardButton("🔄 Refresh Data", callback_data="refresh"))
    return markup


def home_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏠 Home", callback_data="home"))
    return markup


def indikator_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Seluruh Faskes", callback_data="all"),
        InlineKeyboardButton("🏥 Per Faskes", callback_data="rs"),
    )
    markup.add(
        InlineKeyboardButton("🔄 Refresh Data", callback_data="refresh"),
        InlineKeyboardButton("🏠 Home", callback_data="home"),
    )
    return markup


def build_year_menu(prefix, years, back_callback="indikator"):
    markup = InlineKeyboardMarkup(row_width=3)
    for year in years:
        markup.add(InlineKeyboardButton(str(year), callback_data=f"{prefix}|{year}"))
    markup.add(
        InlineKeyboardButton("🔙 Kembali", callback_data=back_callback),
        InlineKeyboardButton("🏠 Home", callback_data="home")
    )
    return markup


def build_month_menu(prefix, year, months, back_callback):
    markup = InlineKeyboardMarkup(row_width=3)
    for month in months:
        markup.add(InlineKeyboardButton(month, callback_data=f"{prefix}|{year}|{month}"))
    markup.add(
        InlineKeyboardButton("🔙 Kembali", callback_data=back_callback),
        InlineKeyboardButton("🏠 Home", callback_data="home")
    )
    return markup


def build_all_report_menu(year, month):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("📄 Dashboard Lengkap", callback_data=f"av|{year}|{month}|dash"))
    markup.add(InlineKeyboardButton("🏆 Top 10", callback_data=f"av|{year}|{month}|top"))
    markup.add(InlineKeyboardButton("🔻 Bottom 10", callback_data=f"av|{year}|{month}|bottom"))
    markup.add(
        InlineKeyboardButton("🔙 Kembali", callback_data=f"ay|{year}"),
        InlineKeyboardButton("🏠 Home", callback_data="home")
    )
    return markup


def build_hospital_menu(user_id, page=0):
    session = ensure_user_session(user_id)
    hospitals = session.get("hospital_list", [])

    total = len(hospitals)
    total_pages = max(1, math.ceil(total / HOSPITALS_PER_PAGE))
    page = max(0, min(page, total_pages - 1))

    start = page * HOSPITALS_PER_PAGE
    end = start + HOSPITALS_PER_PAGE
    current_items = hospitals[start:end]

    markup = InlineKeyboardMarkup(row_width=1)

    for idx, hospital_name in enumerate(current_items, start=start):
        label = hospital_name[:50]
        markup.add(InlineKeyboardButton(label, callback_data=f"pr|{idx}"))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"rp|{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"rp|{page + 1}"))
    if nav:
        markup.row(*nav)

    year = session.get("year")
    markup.add(
        InlineKeyboardButton("🔙 Kembali", callback_data=f"ry|{year}"),
        InlineKeyboardButton("🏠 Home", callback_data="home")
    )

    return markup, page, total_pages


# =========================================================
# CHARTS
# =========================================================

def create_all_chart(summary, output_path):
    rows = summary["rows"]
    lowest_name = summary["lowest_name"]
    month = summary["month"]
    year = summary["year"]

    names = [x[0] for x in rows]
    values = [x[1] for x in rows]

    colors_bar = []
    for nama, nilai in rows:
        if nama == lowest_name:
            colors_bar.append("orange")
        elif nilai >= TARGET_KEPATUHAN:
            colors_bar.append("green")
        else:
            colors_bar.append("red")

    fig_height = min(max(4, len(names) * 0.5 + 2), 20)
    plt.figure(figsize=(11, fig_height))

    bars = plt.barh(names, values, color=colors_bar)
    plt.axvline(TARGET_KEPATUHAN, linestyle="--")

    plt.xlabel("Nilai Kepatuhan (%)")
    plt.title(f"Dashboard Kepatuhan {month} {year}")
    plt.gca().invert_yaxis()

    max_x = max(100, max(values) + 10)
    plt.xlim(0, max_x)

    for bar in bars:
        width = bar.get_width()
        plt.text(width + 1, bar.get_y() + bar.get_height() / 2, f"{width:.2f}%", va="center")

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()


def create_single_chart(summary, output_path):
    hospital = summary["hospital"]
    score = summary["score"]
    month = summary["month"]
    year = summary["year"]

    plt.figure(figsize=(8, 3.8))
    bars = plt.barh([hospital], [score])

    plt.axvline(TARGET_KEPATUHAN, linestyle="--")
    plt.xlim(0, max(100, score + 15))
    plt.xlabel("Nilai Kepatuhan (%)")
    plt.title(f"Kepatuhan {hospital} - {month} {year}")

    for bar in bars:
        width = bar.get_width()
        plt.text(width + 1, bar.get_y() + bar.get_height() / 2, f"{width:.2f}%", va="center")

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()


def create_subset_chart(title, rows, output_path):
    names = [x[0] for x in rows]
    values = [x[1] for x in rows]

    colors_bar = ["green" if v >= TARGET_KEPATUHAN else "red" for _, v in rows]

    fig_height = min(max(4, len(names) * 0.6 + 2), 12)
    plt.figure(figsize=(10, fig_height))

    bars = plt.barh(names, values, color=colors_bar)
    plt.axvline(TARGET_KEPATUHAN, linestyle="--")
    plt.xlabel("Nilai Kepatuhan (%)")
    plt.title(title)
    plt.gca().invert_yaxis()

    max_x = max(100, max(values) + 10)
    plt.xlim(0, max_x)

    for bar in bars:
        width = bar.get_width()
        plt.text(width + 1, bar.get_y() + bar.get_height() / 2, f"{width:.2f}%", va="center")

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()


# =========================================================
# PDF BUILDERS
# =========================================================

def build_all_pdf(summary, chart_path, pdf_path):
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
    )

    elements = []

    elements.append(Paragraph("DASHBOARD EKSEKUTIF - SELURUH FASKES", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Periode: {escape(summary['month'])} {escape(summary['year'])}", styles["Normal"]))
    elements.append(Paragraph(f"Jumlah RS: {len(summary['rows'])}", styles["Normal"]))
    elements.append(Paragraph(f"Rata-rata: {summary['avg']:.2f}%", styles["Normal"]))
    elements.append(Spacer(1, 14))

    elements.append(Image(chart_path, width=6.7 * inch, height=4.5 * inch))
    elements.append(Spacer(1, 14))

    insight_html = escape(summary["insight"]).replace("\n", "<br/>")
    elements.append(Paragraph(f"<b>Insight</b><br/>{insight_html}", styles["Normal"]))
    elements.append(Spacer(1, 14))

    table_data = [["Rank", "Nama RS", "Nilai"]]
    for idx, (nama, nilai) in enumerate(summary["rows"], 1):
        table_data.append([str(idx), nama, f"{nilai:.2f}%"])

    table = Table(table_data, repeatRows=1, colWidths=[45, 320, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
    ]))

    elements.append(Paragraph("<b>Ranking RS</b>", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    elements.append(table)

    doc.build(elements)


def build_single_pdf(summary, chart_path, pdf_path):
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
    )

    elements = []

    elements.append(Paragraph("DASHBOARD PER FASKES", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Periode: {escape(summary['month'])} {escape(summary['year'])}", styles["Normal"]))
    elements.append(Paragraph(f"Nama RS: {escape(summary['hospital'])}", styles["Normal"]))
    elements.append(Paragraph(f"Nilai Kepatuhan: {summary['score']:.2f}%", styles["Normal"]))
    elements.append(Paragraph(f"Rank: #{summary['rank']} dari {summary['total_rs']} RS", styles["Normal"]))
    elements.append(Paragraph(f"Rata-rata semua RS: {summary['avg_all']:.2f}%", styles["Normal"]))
    elements.append(Paragraph(f"Status: {escape(summary['status'])}", styles["Normal"]))
    elements.append(Spacer(1, 14))

    elements.append(Image(chart_path, width=6.4 * inch, height=3.2 * inch))
    elements.append(Spacer(1, 14))

    insight_html = escape(summary["insight"]).replace("\n", "<br/>")
    elements.append(Paragraph(f"<b>Insight</b><br/>{insight_html}", styles["Normal"]))

    doc.build(elements)


def build_ranking_pdf(title, month, year, rows, chart_path, pdf_path):
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
    )

    elements = []

    elements.append(Paragraph(title, styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Periode: {escape(month)} {escape(year)}", styles["Normal"]))
    elements.append(Paragraph(f"Jumlah RS: {len(rows)}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Image(chart_path, width=6.5 * inch, height=4.0 * inch))
    elements.append(Spacer(1, 12))

    table_data = [["Rank", "Nama RS", "Nilai"]]
    for idx, (nama, nilai) in enumerate(rows, 1):
        table_data.append([str(idx), nama, f"{nilai:.2f}%"])

    table = Table(table_data, repeatRows=1, colWidths=[45, 320, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
    ]))

    elements.append(table)
    doc.build(elements)


# =========================================================
# TEXT BUILDERS
# =========================================================

def build_all_text(summary):
    rows = summary["rows"]
    below_target = summary["below_target"]

    ranking_lines = [
        f"{idx}. {escape(nama)} ({nilai:.2f}%)"
        for idx, (nama, nilai) in enumerate(rows[:10], 1)
    ]

    below_lines = [
        f"• {escape(nama)} ({nilai:.2f}%)"
        for nama, nilai in below_target[:10]
    ]

    text_lines = [
        "<b>📊 DASHBOARD EKSEKUTIF</b>",
        f"📅 {escape(summary['month'])} {escape(summary['year'])}",
        "",
        f"Jumlah RS: <b>{len(rows)}</b>",
        f"Rata-rata: <b>{summary['avg']:.2f}%</b>",
        "",
        "<b>🏆 Top 10 Ranking</b>",
        *ranking_lines,
        "",
        f"🥇 Tertinggi: <b>{escape(summary['highest_name'])}</b> ({summary['highest_score']:.2f}%)",
        f"🔻 Terendah: <b>{escape(summary['lowest_name'])}</b> ({summary['lowest_score']:.2f}%)",
        "",
        f"🔴 RS di bawah {TARGET_KEPATUHAN:.0f}%: <b>{len(below_target)}</b>",
    ]

    if below_lines:
        text_lines.extend(below_lines)
        if len(below_target) > 10:
            text_lines.append(f"... dan {len(below_target) - 10} RS lainnya. Detail lengkap ada di PDF.")
    else:
        text_lines.append("Tidak ada 🎉")

    text_lines.extend([
        "",
        "<b>Insight</b>",
        escape(summary["insight"]).replace("\n", "<br/>")
    ])

    return "\n".join(text_lines)


def build_single_text(summary):
    return "\n".join([
        "<b>🏥 DASHBOARD PER FASKES</b>",
        f"📅 {escape(summary['month'])} {escape(summary['year'])}",
        "",
        f"Nama RS: <b>{escape(summary['hospital'])}</b>",
        f"Nilai Kepatuhan: <b>{summary['score']:.2f}%</b>",
        f"Rank: <b>#{summary['rank']}</b> dari {summary['total_rs']} RS",
        f"Rata-rata Semua RS: <b>{summary['avg_all']:.2f}%</b>",
        f"Status: <b>{escape(summary['status'])}</b>",
        "",
        "<b>Insight</b>",
        escape(summary["insight"]).replace("\n", "<br/>")
    ])


def build_subset_text(title, month, year, rows):
    lines = [
        f"<b>{escape(title)}</b>",
        f"📅 {escape(month)} {escape(year)}",
        "",
    ]

    for idx, (nama, nilai) in enumerate(rows, 1):
        lines.append(f"{idx}. {escape(nama)} ({nilai:.2f}%)")

    return "\n".join(lines)


# =========================================================
# REPORT SENDERS
# =========================================================

def send_all_dashboard(chat_id, summary, user_id):
    text_message = build_all_text(summary)

    with tempfile.TemporaryDirectory() as tmpdir:
        chart_path = os.path.join(tmpdir, f"chart_all_{user_id}.png")
        pdf_path = os.path.join(tmpdir, f"Dashboard_Seluruh_Faskes_{summary['month']}_{summary['year']}.pdf")

        create_all_chart(summary, chart_path)
        build_all_pdf(summary, chart_path, pdf_path)

        with open(pdf_path, "rb") as f:
            bot.send_document(chat_id, f)

    bot.send_message(chat_id, text_message, reply_markup=home_button())


def send_single_dashboard(chat_id, summary, user_id):
    text_message = build_single_text(summary)

    with tempfile.TemporaryDirectory() as tmpdir:
        chart_path = os.path.join(tmpdir, f"chart_single_{user_id}.png")
        safe_name = "".join(ch for ch in summary["hospital"] if ch.isalnum() or ch in (" ", "_", "-")).strip()
        safe_name = safe_name[:40] if safe_name else "RS"
        pdf_path = os.path.join(tmpdir, f"Dashboard_{safe_name}_{summary['month']}_{summary['year']}.pdf")

        create_single_chart(summary, chart_path)
        build_single_pdf(summary, chart_path, pdf_path)

        with open(pdf_path, "rb") as f:
            bot.send_document(chat_id, f)

    bot.send_message(chat_id, text_message, reply_markup=home_button())


def send_subset_report(chat_id, title, month, year, rows, user_id):
    text_message = build_subset_text(title, month, year, rows)

    with tempfile.TemporaryDirectory() as tmpdir:
        chart_path = os.path.join(tmpdir, f"chart_subset_{user_id}.png")
        safe_title = title.replace(" ", "_")
        pdf_path = os.path.join(tmpdir, f"{safe_title}_{month}_{year}.pdf")

        create_subset_chart(title, rows, chart_path)
        build_ranking_pdf(title, month, year, rows, chart_path, pdf_path)

        with open(pdf_path, "rb") as f:
            bot.send_document(chat_id, f)

    bot.send_message(chat_id, text_message, reply_markup=home_button())


# =========================================================
# COMMANDS
# =========================================================

@bot.message_handler(commands=["start", "menu"])
def start(message):
    reset_user_session(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "🏥 <b>SISTEM MONITORING FKRTL</b>\n\nSilakan pilih menu:",
        reply_markup=main_menu()
    )


@bot.message_handler(commands=["refresh"])
def refresh_command(message):
    clear_cache()
    rows = fetch_records(force=True)
    bot.send_message(
        message.chat.id,
        f"✅ Data berhasil direfresh.\nTotal baris terbaca: <b>{len(rows)}</b>",
        reply_markup=main_menu()
    )


@bot.message_handler(commands=["ping"])
def ping_command(message):
    bot.send_message(message.chat.id, "🏓 Bot aktif.", reply_markup=main_menu())


@bot.message_handler(commands=["help"])
def help_command(message):
    text = "\n".join([
        "<b>Perintah tersedia:</b>",
        "/start - buka menu utama",
        "/menu - buka menu utama",
        "/refresh - refresh data dari Google Sheet",
        "/ping - cek bot aktif",
        "/help - bantuan"
    ])
    bot.send_message(message.chat.id, text, reply_markup=main_menu())


@bot.message_handler(func=lambda m: True)
def fallback_message(message):
    bot.send_message(
        message.chat.id,
        "Silakan gunakan /start untuk membuka menu utama.",
        reply_markup=main_menu()
    )


# =========================================================
# CALLBACK HANDLER
# =========================================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    session = ensure_user_session(user_id)

    try:
        safe_answer_callback(call)
        data = call.data

        if data == "home":
            reset_user_session(user_id)
            safe_edit_message(
                call,
                "🏠 <b>Menu Utama</b>\n\nSilakan pilih menu:",
                reply_markup=main_menu()
            )
            return

        if data == "refresh":
            clear_cache()
            rows = fetch_records(force=True)
            safe_edit_message(
                call,
                f"✅ Data berhasil direfresh.\nTotal baris terbaca: <b>{len(rows)}</b>",
                reply_markup=indikator_menu()
            )
            return

        if data == "indikator":
            safe_edit_message(
                call,
                "<b>Pilih jenis laporan:</b>",
                reply_markup=indikator_menu()
            )
            return

        if data == "antrian":
            safe_edit_message(
                call,
                "<b>🏥 Antrian Online</b>\n\nMenu ini sudah disiapkan. Tinggal ditambahkan logikanya.",
                reply_markup=home_button()
            )
            return

        if data == "mobile":
            safe_edit_message(
                call,
                "<b>📱 Mobile JKN</b>\n\nMenu ini sudah disiapkan. Tinggal ditambahkan logikanya.",
                reply_markup=home_button()
            )
            return

        if data == "info":
            safe_edit_message(
                call,
                "<b>ℹ️ Informasi Lain</b>\n\nMenu ini sudah disiapkan. Tinggal ditambahkan logikanya.",
                reply_markup=home_button()
            )
            return

        if data == "all":
            rows = fetch_records()
            years = get_years(rows)

            if not years:
                safe_edit_message(call, "Data tahun belum tersedia.", reply_markup=home_button())
                return

            session["mode"] = "all"
            safe_edit_message(
                call,
                "<b>Pilih Tahun (Seluruh Faskes):</b>",
                reply_markup=build_year_menu("ay", years)
            )
            return

        if data.startswith("ay|"):
            _, year = data.split("|", 1)
            rows = fetch_records()
            months = get_months_for_year(rows, year)

            if not months:
                safe_edit_message(
                    call,
                    f"Data bulan untuk tahun {escape(year)} belum tersedia.",
                    reply_markup=home_button()
                )
                return

            session["mode"] = "all"
            session["year"] = year

            safe_edit_message(
                call,
                f"<b>Seluruh Faskes</b>\nTahun: <b>{escape(year)}</b>\n\nPilih Bulan:",
                reply_markup=build_month_menu("am", year, months, "all")
            )
            return

        if data.startswith("am|"):
            _, year, month = data.split("|", 2)
            rows = fetch_records()
            period_rows = get_rows_for_period(rows, year, month)
            aggregated = aggregate_hospitals(period_rows)

            if not aggregated:
                safe_edit_message(
                    call,
                    "Data untuk periode tersebut tidak ditemukan.",
                    reply_markup=home_button()
                )
                return

            safe_edit_message(
                call,
                f"<b>Periode Dipilih</b>\n📅 {escape(month)} {escape(year)}\n\nPilih jenis laporan:",
                reply_markup=build_all_report_menu(year, month)
            )
            return

        if data.startswith("av|"):
            _, year, month, report_type = data.split("|", 3)

            rows = fetch_records()
            period_rows = get_rows_for_period(rows, year, month)
            aggregated = aggregate_hospitals(period_rows)
            summary = build_all_summary(aggregated, month, year)

            if not summary:
                bot.send_message(
                    call.message.chat.id,
                    "Data untuk periode tersebut tidak ditemukan.",
                    reply_markup=home_button()
                )
                return

            if report_type == "dash":
                send_all_dashboard(call.message.chat.id, summary, user_id)
                return

            if report_type == "top":
                top_rows = get_top_rows(summary["rows"], 10)
                send_subset_report(
                    call.message.chat.id,
                    "TOP 10 KEPATUHAN RS",
                    month,
                    year,
                    top_rows,
                    user_id
                )
                return

            if report_type == "bottom":
                bottom_rows = get_bottom_rows(summary["rows"], 10)
                send_subset_report(
                    call.message.chat.id,
                    "BOTTOM 10 KEPATUHAN RS",
                    month,
                    year,
                    bottom_rows,
                    user_id
                )
                return

        if data == "rs":
            rows = fetch_records()
            years = get_years(rows)

            if not years:
                safe_edit_message(call, "Data tahun belum tersedia.", reply_markup=home_button())
                return

            session["mode"] = "single"
            safe_edit_message(
                call,
                "<b>Pilih Tahun (Per Faskes):</b>",
                reply_markup=build_year_menu("ry", years)
            )
            return

        if data.startswith("ry|"):
            _, year = data.split("|", 1)
            rows = fetch_records()
            months = get_months_for_year(rows, year)

            if not months:
                safe_edit_message(
                    call,
                    f"Data bulan untuk tahun {escape(year)} belum tersedia.",
                    reply_markup=home_button()
                )
                return

            session["mode"] = "single"
            session["year"] = year

            safe_edit_message(
                call,
                f"<b>Per Faskes</b>\nTahun: <b>{escape(year)}</b>\n\nPilih Bulan:",
                reply_markup=build_month_menu("rm", year, months, "rs")
            )
            return

        if data.startswith("rm|"):
            _, year, month = data.split("|", 2)
            rows = fetch_records()
            period_rows = get_rows_for_period(rows, year, month)
            aggregated = aggregate_hospitals(period_rows)

            if not aggregated:
                safe_edit_message(
                    call,
                    "Data untuk periode tersebut tidak ditemukan.",
                    reply_markup=home_button()
                )
                return

            hospital_names = [nama for nama, _ in aggregated]

            session["mode"] = "single"
            session["year"] = year
            session["month"] = month
            session["hospital_list"] = hospital_names

            markup, page, total_pages = build_hospital_menu(user_id, page=0)

            safe_edit_message(
                call,
                f"<b>Pilih RS</b>\nPeriode: <b>{escape(month)} {escape(year)}</b>\n"
                f"Jumlah RS: <b>{len(hospital_names)}</b>\n"
                f"Halaman <b>{page + 1}/{total_pages}</b>",
                reply_markup=markup
            )
            return

        if data.startswith("rp|"):
            _, page_str = data.split("|", 1)
            page = int(page_str)

            if not session.get("hospital_list"):
                safe_edit_message(
                    call,
                    "Sesi daftar RS sudah habis. Silakan ulang dari menu Per Faskes.",
                    reply_markup=home_button()
                )
                return

            markup, current_page, total_pages = build_hospital_menu(user_id, page=page)

            safe_edit_message(
                call,
                f"<b>Pilih RS</b>\nPeriode: <b>{escape(session['month'])} {escape(session['year'])}</b>\n"
                f"Jumlah RS: <b>{len(session['hospital_list'])}</b>\n"
                f"Halaman <b>{current_page + 1}/{total_pages}</b>",
                reply_markup=markup
            )
            return

        if data.startswith("pr|"):
            _, idx_str = data.split("|", 1)
            idx = int(idx_str)

            hospital_list = session.get("hospital_list", [])
            if idx < 0 or idx >= len(hospital_list):
                safe_edit_message(call, "Pilihan RS tidak valid.", reply_markup=home_button())
                return

            hospital_name = hospital_list[idx]
            year = session.get("year")
            month = session.get("month")

            rows = fetch_records()
            period_rows = get_rows_for_period(rows, year, month)
            aggregated = aggregate_hospitals(period_rows)
            summary = build_single_summary(aggregated, hospital_name, month, year)

            if not summary:
                bot.send_message(
                    call.message.chat.id,
                    "Data RS tidak ditemukan untuk periode tersebut.",
                    reply_markup=home_button()
                )
                return

            send_single_dashboard(call.message.chat.id, summary, user_id)
            return

        safe_edit_message(
            call,
            "Menu tidak dikenali. Silakan kembali ke Home.",
            reply_markup=home_button()
        )

    except Exception as e:
        logging.exception("Error callback: %s", e)
        bot.send_message(
            call.message.chat.id,
            f"Terjadi kesalahan saat memproses permintaan.\n\nDetail: <code>{escape(e)}</code>",
            reply_markup=home_button()
        )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    logging.info("Bot started ✅")
    fetch_records(force=True)
    bot.infinity_polling(none_stop=True, timeout=20, long_polling_timeout=20)
