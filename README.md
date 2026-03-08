# FKRTL Telegram Bot

Bot Telegram untuk monitoring indikator kepatuhan FKRTL berbasis Google Sheet.

## Fitur
- Dashboard Seluruh Faskes
- Dashboard Per Faskes
- Top 10 dan Bottom 10
- Export PDF
- Refresh data dari Google Sheet
- Cache data untuk mengurangi request berulang

## Kebutuhan
- Python 3.11+
- Bot Telegram Token
- Google Service Account JSON
- Spreadsheet Google Sheet yang bisa diakses service account

## Format Google Sheet
Kolom yang wajib ada:
- TAHUN
- BULAN
- NamaPPK
- Nilai Kepatuhan

## Install Lokal

### 1. Buat virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
