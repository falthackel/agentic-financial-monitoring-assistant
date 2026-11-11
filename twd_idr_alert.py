#!/usr/bin/env python3
"""
TWD/IDR Price Alert Monitor
----------------------------
Memantau nilai tukar TWD/IDR menggunakan yfinance (ticker TWDIDR=X).

PENTING: Versi awal script ini pakai Frankfurter API dengan EUR pivot
triangulation, TAPI ternyata Frankfurter (sumber datanya ECB) TIDAK
menyediakan TWD sama sekali -- TWD tidak ada di daftar currency ECB.
Makanya diganti ke yfinance, yang punya pair langsung TWDIDR=X (dan sudah
ada di stack kamu untuk data IHSG).

Cara kerja:
1. Ambil harga TWDIDR=X terakhir dari Yahoo Finance via yfinance.
2. Estimasi rate jual money changer = mid-market * (1 + spread%), karena
   money changer selalu jual di atas mid-market.
3. Bandingkan estimasi tsb dengan target beli kamu.
4. Simpan histori ke CSV dan cetak alert jika target tercapai.

Konfigurasi via .env (lihat .env.example) atau override lewat argumen CLI.
Urutan prioritas: argumen CLI > nilai di .env > default bawaan.

Cara pakai:
    python3 twd_idr_alert.py                       # pakai config dari .env / default
    python3 twd_idr_alert.py --target 550 --spread 0.75
    python3 twd_idr_alert.py --loop --interval 3600

Integrasi ke chatbot LangChain kamu:
    Import fungsi `get_twd_idr_rate()` dan `check_alert()` langsung,
    atau bungkus sebagai LangChain Tool (lihat contoh di bagian bawah file).
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone

import yfinance as yf

try:
    from dotenv import load_dotenv
    load_dotenv()  # baca file .env di direktori kerja saat ini, kalau ada
except ImportError:
    # python-dotenv belum terpasang -> tetap jalan, cukup tanpa baca .env.
    # Install dengan: pip install python-dotenv --break-system-packages
    pass

YFINANCE_TICKER = "TWDIDR=X"
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "twd_idr_history.csv")

# Default diambil dari environment variable (.env) kalau ada, kalau tidak pakai fallback.
DEFAULT_TARGET = float(os.getenv("TWD_IDR_TARGET", 550.0))
DEFAULT_SPREAD_PCT = float(os.getenv("TWD_IDR_SPREAD_PCT", 0.75))
DEFAULT_DIRECTION = os.getenv("TWD_IDR_DIRECTION", "below")
DEFAULT_INTERVAL = int(os.getenv("TWD_IDR_INTERVAL", 3600))


def get_twd_idr_rate() -> dict:
    """Ambil TWD/IDR langsung dari Yahoo Finance (ticker TWDIDR=X) via yfinance.

    Returns dict berisi rate dan timestamp. Raises RuntimeError kalau data
    kosong/tidak bisa diambil (misal koneksi bermasalah atau ticker berubah).
    """
    ticker = yf.Ticker(YFINANCE_TICKER)

    # fast_info lebih ringan/cepat daripada .history(), cocok untuk polling berkala
    try:
        rate = ticker.fast_info["last_price"]
    except (KeyError, Exception):
        rate = None

    if not rate:
        # fallback: ambil dari history 1 hari terakhir kalau fast_info kosong
        hist = ticker.history(period="1d")
        if hist.empty:
            raise RuntimeError(f"Tidak ada data untuk ticker {YFINANCE_TICKER}")
        rate = hist["Close"].iloc[-1]

    return {
        "rate": round(float(rate), 4),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def estimate_money_changer_rate(mid_rate: float, spread_pct: float) -> float:
    """Estimasi rate JUAL money changer dari mid-market rate.

    Money changer selalu menjual valas di atas mid-market (itu keuntungan
    mereka). spread_pct dalam persen, misal 0.75 berarti +0.75% dari mid-market.

    Ini hanya ESTIMASI kasar berdasarkan spread historis yang kamu amati dari
    penawaran money changer langganan kamu -- bukan data real-time dari mereka.
    Sesuaikan --spread berdasarkan pengamatanmu sendiri (misal kalau mereka
    biasa jual di 554 saat mid-market 553.13, itu spread ~0.16%).
    """
    return mid_rate * (1 + spread_pct / 100)


def log_to_history(record: dict) -> None:
    """Append hasil fetch ke CSV history supaya bisa dianalisis trennya nanti."""
    file_exists = os.path.isfile(HISTORY_FILE)
    with open(HISTORY_FILE, "a", newline="") as f:
        fieldnames = ["fetched_at", "rate", "est_money_changer_rate"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)


def check_alert(rate: float, target: float, direction: str = "below") -> bool:
    """Cek apakah rate sudah memenuhi kondisi alert.

    direction="below" -> alert saat rate <= target (kasus kamu: mau beli TWD murah)
    direction="above" -> alert saat rate >= target (kalau suatu saat mau jual)
    """
    if direction == "below":
        return rate <= target
    return rate >= target


def run_once(target: float, direction: str, spread_pct: float) -> bool:
    try:
        result = get_twd_idr_rate()
    except Exception as e:
        print(f"[ERROR] Gagal fetch rate: {e}", file=sys.stderr)
        return False

    mid_rate = result["rate"]
    est_rate = round(estimate_money_changer_rate(mid_rate, spread_pct), 4)
    result["est_money_changer_rate"] = est_rate
    log_to_history(result)

    ts = result["fetched_at"]
    triggered = check_alert(est_rate, target, direction)
    status = "🎯 TARGET TERCAPAI!" if triggered else "belum mencapai target"

    print(
        f"[{ts}] Mid-market = {mid_rate}  |  Estimasi jual money changer (+{spread_pct}%) = {est_rate}  "
        f"(target {direction} {target}) -> {status}"
    )

    if triggered:
        print(
            f"\n🔔 ALERT: Estimasi rate jual money changer sudah di {est_rate}, sudah "
            f"{'<=' if direction=='below' else '>='} target kamu ({target}).\n"
            f"   Ini masih ESTIMASI — telepon/cek langsung ke money changer langganan kamu "
            f"untuk konfirmasi harga jual real mereka sebelum transaksi.\n"
        )

    return triggered


def main():
    parser = argparse.ArgumentParser(description="TWD/IDR price alert monitor")
    parser.add_argument("--target", type=float, default=DEFAULT_TARGET, help=f"Target rate (default dari .env atau {DEFAULT_TARGET})")
    parser.add_argument(
        "--spread",
        type=float,
        default=DEFAULT_SPREAD_PCT,
        help=f"Estimasi markup money changer dalam persen di atas mid-market (default dari .env atau {DEFAULT_SPREAD_PCT}%%)",
    )
    parser.add_argument(
        "--direction",
        choices=["below", "above"],
        default=DEFAULT_DIRECTION,
        help="'below' = alert saat estimasi rate turun ke/bawah target (default, cocok untuk niat BELI). 'above' = alert saat naik ke/atas target (cocok untuk niat JUAL).",
    )
    parser.add_argument("--loop", action="store_true", help="Jalankan terus-menerus, bukan sekali saja")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help=f"Interval detik antar cek jika --loop (default dari .env atau {DEFAULT_INTERVAL})")
    args = parser.parse_args()

    if args.loop:
        print(
            f"Memantau TWD/IDR setiap {args.interval} detik, spread estimasi {args.spread}%, "
            f"target {args.direction} {args.target}..."
        )
        print("Tekan Ctrl+C untuk berhenti.\n")
        try:
            while True:
                triggered = run_once(args.target, args.direction, args.spread)
                if triggered:
                    print("Target tercapai. Menghentikan loop otomatis.")
                    break
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nDihentikan oleh user.")
    else:
        run_once(args.target, args.direction, args.spread)


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Contoh pembungkusan sebagai LangChain Tool, untuk diintegrasikan ke
# chatbot agentic kamu yang sudah ada:
#
# from langchain.tools import tool
#
# @tool
# def twd_idr_alert_tool(target: float = 550.0) -> str:
#     """Cek rate TWD/IDR saat ini dan bandingkan dengan target beli user."""
#     result = get_twd_idr_rate()
#     triggered = check_alert(result["rate"], target)
#     if triggered:
#         return f"TWD/IDR sekarang {result['rate']}, sudah mencapai target {target}!"
#     return f"TWD/IDR sekarang {result['rate']}, masih di atas target {target}."
# ---------------------------------------------------------------------------