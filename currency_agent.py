"""
Chatbot Update Harga Aset - Contoh Agentic AI
====================================================
Stack: LangChain + Google Gemini (via Google AI Studio)

Sumber data:
- Frankfurter API v2 (gratis, tanpa API key): kurs mata uang & logam mulia
  (XAU/XAG diperlakukan sebagai 'mata uang'). Docs: https://frankfurter.dev/
  CATATAN: data Frankfurter granularitasnya HARIAN, bukan real-time per
  menit — makanya "update terakhir" untuk aset ini ditampilkan sebagai
  tanggal rate + jam kita mengecek, bukan jam pasar sesungguhnya.
- yfinance (gratis, tanpa API key): indeks saham IHSG (ticker ^JKSE),
  diambil intraday per menit sehingga jamnya adalah jam pasar sungguhan.
- DuckDuckGo (ddgs, gratis): fallback pencarian untuk aset di luar
  cakupan dua sumber di atas (mis. kripto)

CATATAN: "XAUG" bukan kode standar. Kode ISO resmi untuk emas adalah XAU.

Log: setiap request baru menimpa (bukan menambah) file agent_log.txt di
folder yang sama, jadi isinya selalu jejak dari request TERAKHIR saja.

Berhenti: tekan ESC kapan pun saat menunggu input untuk keluar.

Cara jalankan:
    (siapkan file .env berisi GOOGLE_API_KEY, lihat .env.example)
    python currency_agent.py
"""

import os
import sys
import datetime
from collections import defaultdict

import requests
import yfinance as yf
from ddgs import DDGS
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain.agents import create_agent

load_dotenv()  # baca GOOGLE_API_KEY dari file .env di folder yang sama

try:
    import msvcrt  # built-in di Windows, dipakai untuk deteksi tombol ESC
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False  # bukan Windows: fallback ke input() biasa + Ctrl+C

API_BASE = "https://api.frankfurter.dev/v2"
GRAMS_PER_TROY_OZ = 31.1034768
LOG_FILE = "agent_log.txt"

ASSET_LABELS = {
    "USD": "USD",
    "SGD": "SGD",
    "TWD": "TWD",
    "XAU": "Emas (XAU)",
    "XAG": "Perak (XAG, per troy oz)",
    "IHSG": "IHSG",
}


# ---------------------------------------------------------
# Logging ke file — di-timpa SEKALI setiap sesi program dimulai
# (_start_session_log), lalu MENUMPUK untuk tiap request selama sesi
# itu masih berjalan (_log_new_request + _log). Ini supaya histori
# konteks percakapan tetap kebaca di log, bukan hilang tiap giliran.
# ---------------------------------------------------------
def _start_session_log():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== SESI BARU DIMULAI: "
                f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")


def _log_new_request(question: str):
    _log(f"\n{'=' * 60}")
    _log(f"REQUEST: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _log(f"Pertanyaan: {question}")
    _log("-" * 60)


def _log(message: str):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")



# ---------------------------------------------------------
# Helper waktu
# ---------------------------------------------------------
def _now_hm() -> str:
    return datetime.datetime.now().strftime("%H:%M")


def _format_daily_update(date_str: str) -> str:
    """Untuk sumber data harian (Frankfurter): tanggal rate + jam kita cek."""
    return f"{date_str} • dicek {_now_hm()}"


# ---------------------------------------------------------
# Helper: ambil rate lintas mata uang lewat EUR sebagai pivot
# ---------------------------------------------------------
def _fetch_eur_cross_series(from_currency: str, to_currency: str,
                             date_or_range: dict = None) -> dict:
    """
    Mengembalikan dict {tanggal: rate} untuk from_currency -> to_currency,
    dihitung lewat pivot EUR.
    """
    from_c, to_c = from_currency.upper(), to_currency.upper()
    quotes = ",".join(sorted(set([from_c, to_c]) - {"EUR"}))

    params = {"base": "EUR"}
    if quotes:
        params["quotes"] = quotes
    if date_or_range:
        params.update(date_or_range)

    resp = requests.get(f"{API_BASE}/rates", params=params, timeout=15)
    resp.raise_for_status()
    rows = resp.json()

    by_date = defaultdict(dict)
    for row in rows:
        by_date[row["date"]][row["quote"]] = row["rate"]

    cross = {}
    for date, rates in by_date.items():
        rate_from = 1.0 if from_c == "EUR" else rates.get(from_c)
        rate_to = 1.0 if to_c == "EUR" else rates.get(to_c)
        if rate_from and rate_to:
            cross[date] = rate_to / rate_from

    return cross


def _get_price_and_change(asset: str, base_currency: str = "IDR"):
    """Harga terkini + persen perubahan dari hari sebelumnya. -> (harga, pct, tanggal)"""
    week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    cross = _fetch_eur_cross_series(asset, base_currency, {"from": week_ago})

    if len(cross) < 1:
        raise ValueError(f"Tidak ada data untuk {asset}")

    dates_sorted = sorted(cross.keys())
    latest_date = dates_sorted[-1]
    latest_rate = cross[latest_date]

    if len(dates_sorted) >= 2:
        prev_rate = cross[dates_sorted[-2]]
        pct_change = (latest_rate - prev_rate) / prev_rate * 100
    else:
        pct_change = None

    return latest_rate, pct_change, latest_date


def _get_gold_data():
    """
    Data emas khusus: harga acuan USD/troy oz (buat pantau volatilitas
    seperti biasa dipantau), plus konversi ke Rp/gram dan Rp/0.01gram.
    """
    week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    cross_usd = _fetch_eur_cross_series("XAU", "USD", {"from": week_ago})
    cross_idr = _fetch_eur_cross_series("XAU", "IDR", {"from": week_ago})

    if not cross_usd or not cross_idr:
        raise ValueError("Tidak ada data XAU")

    dates_usd = sorted(cross_usd.keys())
    latest_date = dates_usd[-1]
    usd_per_oz = cross_usd[latest_date]
    idr_per_oz = cross_idr.get(latest_date) or cross_idr[sorted(cross_idr.keys())[-1]]

    idr_per_gram = idr_per_oz / GRAMS_PER_TROY_OZ
    idr_per_0_01_gram = idr_per_gram * 0.01

    if len(dates_usd) >= 2:
        prev_usd = cross_usd[dates_usd[-2]]
        pct_change = (usd_per_oz - prev_usd) / prev_usd * 100
    else:
        pct_change = None

    return {
        "usd_per_oz": usd_per_oz,
        "idr_per_gram": idr_per_gram,
        "idr_per_0_01_gram": idr_per_0_01_gram,
        "pct_change": pct_change,
        "date": latest_date,
    }


def _get_ihsg_data():
    """
    Harga IHSG intraday (jam sungguhan dari pasar, bukan estimasi) +
    persen perubahan vs penutupan hari sebelumnya.
    """
    ticker = yf.Ticker("^JKSE")
    daily = ticker.history(period="5d")
    if daily.empty:
        raise ValueError("Tidak ada data IHSG")

    prev_close = float(daily.iloc[-2]["Close"]) if len(daily) >= 2 else None

    intraday = ticker.history(period="1d", interval="1m")
    if not intraday.empty:
        price = float(intraday.iloc[-1]["Close"])
        last_update = intraday.index[-1].strftime("%Y-%m-%d %H:%M")
    else:
        # di luar jam bursa, data 1-menit bisa kosong -> pakai data harian
        price = float(daily.iloc[-1]["Close"])
        last_update = daily.index[-1].strftime("%Y-%m-%d %H:%M")

    pct_change = ((price - prev_close) / prev_close * 100) if prev_close else None
    return price, pct_change, last_update


# ---------------------------------------------------------
# 1. TOOL: kurs terkini satu pasangan
# ---------------------------------------------------------
@tool
def get_exchange_rate(from_currency: str, to_currency: str) -> str:
    """
    Mengambil kurs tukar TERKINI antara dua mata uang FIAT resmi (ISO 4217),
    contoh: USD, IDR, SGD, TWD, EUR. Juga mendukung XAU (emas), XAG (perak)
    per troy ounce. TIDAK mendukung kripto atau indeks saham (pakai
    get_price_table untuk IHSG) — untuk itu gunakan web_search.

    Gunakan tool ini HANYA untuk 1 pasangan spesifik. Untuk "update harga"
    beberapa aset sekaligus, gunakan get_price_table.

    Args:
        from_currency: kode mata uang asal, contoh 'USD'
        to_currency: kode mata uang tujuan, contoh 'IDR'
    """
    _log(f"🔧 [TOOL DIPANGGIL] get_exchange_rate({from_currency!r}, {to_currency!r})")
    try:
        cross = _fetch_eur_cross_series(from_currency, to_currency)
        if not cross:
            _log(f"❌ [TOOL GAGAL] {from_currency}/{to_currency} tidak ditemukan di Frankfurter")
            return (f"Tidak menemukan kurs untuk {from_currency} ke {to_currency}. "
                     "Mungkin bukan mata uang/logam mulia standar — coba web_search.")
        latest_date = max(cross.keys())
        rate = cross[latest_date]
        _log(f"✅ [TOOL SUKSES] {from_currency} -> {to_currency} = {rate:.6g} (per {latest_date})")
        return f"1 {from_currency.upper()} = {rate:.6g} {to_currency.upper()} (per {latest_date})"
    except Exception as e:
        _log(f"❌ [TOOL ERROR] {str(e)}")
        return f"Gagal mengambil data kurs: {str(e)}"


# ---------------------------------------------------------
# 2. TOOL: rata-rata kurs pada rentang tanggal
# ---------------------------------------------------------
@tool
def get_average_exchange_rate(from_currency: str, to_currency: str,
                               start_date: str, end_date: str) -> str:
    """
    Menghitung rata-rata kurs harian antara dua mata uang pada rentang
    tanggal tertentu. Berguna untuk membandingkan periode (mis. Q1 vs Q2).

    Args:
        from_currency: kode mata uang asal, contoh 'USD'
        to_currency: kode mata uang tujuan, contoh 'IDR'
        start_date: tanggal mulai format YYYY-MM-DD
        end_date: tanggal akhir format YYYY-MM-DD
    """
    _log(f"🔧 [TOOL DIPANGGIL] get_average_exchange_rate({from_currency!r}, "
         f"{to_currency!r}, {start_date!r}, {end_date!r})")
    try:
        cross = _fetch_eur_cross_series(
            from_currency, to_currency,
            date_or_range={"from": start_date, "to": end_date},
        )
        if not cross:
            _log("❌ [TOOL GAGAL] Tidak ada data historis untuk periode ini")
            return f"Tidak ada data kurs {from_currency} ke {to_currency} antara {start_date} dan {end_date}."

        values = list(cross.values())
        avg = sum(values) / len(values)
        _log(f"✅ [TOOL SUKSES] Rata-rata = {avg:.6g} dari {len(values)} hari data")
        return (f"Rata-rata 1 {from_currency.upper()} = {avg:.6g} {to_currency.upper()} "
                f"selama {start_date} s/d {end_date} ({len(values)} hari data, "
                f"min {min(values):.6g}, max {max(values):.6g})")
    except Exception as e:
        _log(f"❌ [TOOL ERROR] {str(e)}")
        return f"Gagal mengambil data kurs historis: {str(e)}"


# ---------------------------------------------------------
# 3. TOOL: tabel harga banyak aset sekaligus (basis IDR)
# ---------------------------------------------------------
@tool
def get_price_table(assets: str = "USD,SGD,TWD,XAU,IHSG") -> str:
    """
    Membuat TABEL harga beberapa aset sekaligus, lengkap dengan persentase
    perubahan dan waktu update terakhir. Tool UTAMA untuk "update harga
    hari ini", "ringkasan pasar", dll. Emas (XAU) ditampilkan dalam acuan
    USD/troy oz PLUS Rp/gram dan Rp/0.01gram.

    JANGAN panggil get_exchange_rate berkali-kali untuk kasus ini — tool
    ini sudah menghitung dan memformat semuanya dalam satu panggilan.

    Args:
        assets: daftar kode aset dipisah koma. Kode ISO 4217 (USD, SGD,
            TWD, dst), XAU/XAG untuk logam mulia, atau IHSG. Default:
            "USD,SGD,TWD,XAU,IHSG".
    """
    asset_list = [a.strip().upper() for a in assets.split(",") if a.strip()]
    _log(f"🔧 [TOOL DIPANGGIL] get_price_table({asset_list})")

    rows = []
    for asset in asset_list:
        label = ASSET_LABELS.get(asset, asset)
        try:
            if asset == "XAU":
                data = _get_gold_data()
                harga_str = (f"${data['usd_per_oz']:,.2f}/oz | "
                             f"Rp{data['idr_per_gram']:,.0f}/gr "
                             f"(Rp{data['idr_per_0_01_gram']:,.0f}/0.01gr)")
                pct = data["pct_change"]
                last_update = _format_daily_update(data["date"])
                _log(f"✅ [{asset}] {harga_str} (per {last_update})")
            elif asset == "IHSG":
                price, pct, last_update = _get_ihsg_data()
                harga_str = f"Rp{price:,.2f}"
                _log(f"✅ [{asset}] {harga_str} (per {last_update})")
            else:
                price, pct, date_str = _get_price_and_change(asset, "IDR")
                harga_str = f"Rp{price:,.2f}"
                last_update = _format_daily_update(date_str)
                _log(f"✅ [{asset}] {harga_str} (per {last_update})")
            rows.append((label, harga_str, pct, last_update))
        except Exception as e:
            _log(f"❌ [{asset}] gagal: {e}")
            rows.append((label, None, None, f"GAGAL: {e}"))

    lines = [
        "| Aset | Harga | Perubahan (vs hari sebelumnya) | Update Terakhir |",
        "|---|---|---|---|",
    ]
    for label, harga_str, pct, last_update in rows:
        if harga_str is None:
            lines.append(f"| {label} | - | - | {last_update} |")
            continue
        if pct is None:
            pct_str = "n/a"
        else:
            arrow = "🔺" if pct >= 0 else "🔻"
            pct_str = f"{arrow} {pct:+.2f}%"
        lines.append(f"| {label} | {harga_str} | {pct_str} | {last_update} |")

    _log(f"✅ [TOOL SUKSES] Tabel {len(rows)} aset selesai dibentuk")
    return "\n".join(lines)


# ---------------------------------------------------------
# 4. TOOL: web search (fallback)
# ---------------------------------------------------------
@tool
def web_search(query: str) -> str:
    """
    Mencari informasi terkini di internet lewat DuckDuckGo. Gunakan
    SEBAGAI FALLBACK ketika tool data terstruktur lain gagal (mis. aset
    kripto atau kode yang tidak dikenali).

    Args:
        query: kata kunci pencarian, contoh 'harga bitcoin ke IDR hari ini'
    """
    _log(f"🔧 [TOOL DIPANGGIL] web_search({query!r})")
    _log("↳ [KENAPA] tool data terstruktur sebelumnya tidak bisa menjawab, "
         "agent memutuskan mencoba mencari di internet")
    try:
        results = DDGS().text(query, max_results=4)
        if not results:
            _log("❌ [TOOL GAGAL] Tidak ada hasil pencarian ditemukan")
            return "Tidak ada hasil pencarian yang ditemukan."

        formatted = "\n".join(f"- {r['title']}: {r['body']}" for r in results)
        _log(f"✅ [TOOL SUKSES] Ditemukan {len(results)} hasil pencarian")
        return formatted
    except Exception as e:
        _log(f"❌ [TOOL ERROR] {str(e)}")
        return f"Gagal melakukan pencarian: {str(e)}"


# ---------------------------------------------------------
# Inisialisasi model Gemini + agent
# ---------------------------------------------------------
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0,
    api_key=os.environ.get("GOOGLE_API_KEY"),
)

TODAY = datetime.date.today().isoformat()

agent = create_agent(
    llm,
    tools=[get_exchange_rate, get_average_exchange_rate, get_price_table, web_search],
    system_prompt=(
        f"Hari ini adalah {TODAY}. Kamu adalah asisten yang membantu "
        "menjawab pertanyaan soal kurs mata uang dan harga aset. SELALU "
        "gunakan tool yang tersedia untuk mendapatkan angka — jangan pernah "
        "menebak atau memakai data dari ingatanmu.\n\n"
        "Gunakan get_price_table saat user minta 'update harga', 'ringkasan "
        "pasar', atau daftar beberapa aset sekaligus. Gunakan "
        "get_exchange_rate hanya untuk satu pasangan mata uang spesifik. "
        "Gunakan get_average_exchange_rate untuk rata-rata/perbandingan "
        "periode.\n\n"
        "PENTING: jika tool data terstruktur gagal, JANGAN langsung "
        "menyerah — coba tool web_search sebagai alternatif.\n\n"
        "Jika pertanyaan tidak berkaitan dengan kurs/harga aset sama "
        "sekali, jawab seperti biasa tanpa memanggil tool."
    ),
)


# ---------------------------------------------------------
# Utilitas tampilan
# ---------------------------------------------------------
def _extract_text(message) -> str:
    """Ambil hanya bagian teks dari content Gemini 3.x (list of blocks)."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts).strip()
    return str(content)


_conversation_history = []  # riwayat pesan lintas giliran dalam 1 sesi chat


def _reset_conversation():
    """Kosongkan riwayat percakapan dan mulai sesi log baru dari nol."""
    global _conversation_history
    _conversation_history = []
    _start_session_log()


def _run_request(question: str) -> str:
    """
    Satu giliran tanya-jawab. Riwayat percakapan sebelumnya (kalau ada)
    ikut dikirim ke agent supaya dia punya KONTEKS dari pertanyaan/
    jawaban sebelumnya dalam sesi yang sama — misal supaya "kenapa itu
    naik?" tahu bahwa "itu" merujuk ke aset yang dibahas di giliran
    sebelumnya, bukan menebak/mereview rentang waktu sembarangan.
    """
    global _conversation_history
    _log_new_request(question)

    _conversation_history.append(("human", question))
    result = agent.invoke({"messages": _conversation_history})
    _conversation_history = result["messages"]  # simpan histori penuh (termasuk tool calls) untuk giliran berikutnya

    answer = _extract_text(_conversation_history[-1])
    _log("\n=== JAWABAN FINAL ===")
    _log(answer)
    return answer


def ask(question: str) -> str:
    """Kirim satu pertanyaan (dipakai untuk testing manual di luar mode chat)."""
    if not _conversation_history:
        _start_session_log()
    print(f"\n>> Anda: {question}")
    answer = _run_request(question)
    print(f"\n>> Agent:\n{answer}")
    return answer


# ---------------------------------------------------------
# Input dengan dukungan ESC untuk berhenti (Windows via msvcrt)
# ---------------------------------------------------------
def _read_line_with_esc(prompt: str = ""):
    """
    Baca satu baris input. Return None kalau user menekan ESC (berarti
    ingin berhenti). Di luar Windows (tanpa msvcrt), fallback ke input()
    biasa — gunakan Ctrl+C untuk berhenti.
    """
    if not HAS_MSVCRT:
        try:
            return input(prompt)
        except (EOFError, KeyboardInterrupt):
            return None

    print(prompt, end="", flush=True)
    buffer = []
    while True:
        ch = msvcrt.getwch()
        if ch == "\x1b":  # ESC
            print()
            return None
        elif ch in ("\r", "\n"):
            print()
            return "".join(buffer)
        elif ch == "\x08":  # backspace
            if buffer:
                buffer.pop()
                print("\b \b", end="", flush=True)
        else:
            buffer.append(ch)
            print(ch, end="", flush=True)


# ---------------------------------------------------------
# Mode chatbot interaktif
# ---------------------------------------------------------
def chat():
    _start_session_log()

    print("=" * 60)
    print("Chatbot Update Harga Aset")
    print("Contoh: 'update harga hari ini', 'berapa kurs SGD ke TWD?'")
    print("Tekan ESC kapan pun untuk berhenti (atau ketik 'exit')")
    print("Ketik 'reset' untuk mulai konteks percakapan baru")
    print(f"Log sesi ini (menumpuk, konteks tidak hilang) tersimpan di: {LOG_FILE}")
    print("=" * 60)

    while True:
        question = _read_line_with_esc("\nAnda: ")

        if question is None:
            print("\n[ESC ditekan] Menghentikan program. Sampai jumpa!")
            break

        question = question.strip()
        if not question:
            continue
        if question.lower() in ("exit", "quit", "keluar", "bye", "esc"):
            print("Sampai jumpa!")
            break
        if question.lower() in ("reset", "clear", "mulai baru"):
            _reset_conversation()
            print("[Riwayat percakapan direset — konteks sebelumnya dilupakan]")
            continue

        answer = _run_request(question)
        print(f"\nAgent:\n{answer}")


if __name__ == "__main__":
    chat()