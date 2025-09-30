# scrape_autazeszwajcarii.py
import re
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://autazeszwajcarii.pl"
# Startowy adres z listą – zostaw "/" (strona główna) albo podmień np. na
# "/aukcje/licytacje" jeśli wolisz wyraźny listing:
START_PATH = "/"

DB_PATH = Path("autazeszwajcarii.db")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/127.0 Safari/537.36"
}

def ensure_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS auctions (
        id TEXT PRIMARY KEY,
        title TEXT,
        href TEXT,
        end_ts INTEGER,
        first_seen_ts INTEGER,
        last_seen_ts INTEGER
    )
    """)
    con.commit()
    return con

def fetch_page(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

def parse_max_pages(soup):
    # Na liście jest kontener z data-max-page (widziałeś to w DevTools)
    cont = soup.select_one(".container.business.auctions-container")
    if cont and cont.has_attr("data-max-page"):
        try:
            return int(cont["data-max-page"])
        except ValueError:
            pass
    # fallback – jeśli nie ma atrybutu, lecimy tylko pierwszą stronę
    return 1

def parse_auctions(soup):
    out = []
    for div in soup.select("div.auction-entry"):
        # Wyciągnij datę końca aukcji z tekstu
        end_ts = 0
        end_info = div.select_one(".auction-end-info")
        if end_info:
            end_text = end_info.get_text()
            # Szukaj daty w formacie DD-MM-YYYY HH:MM:SS
            date_match = re.search(r'(\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2})', end_text)
            if date_match:
                date_str = date_match.group(1)
                try:
                    dt = datetime.strptime(date_str, '%d-%m-%Y %H:%M:%S')
                    end_ts = int(dt.timestamp())
                except ValueError:
                    end_ts = 0

        # Tytuł + href
        a = div.select_one("h4 a[href]")
        title = a.get_text(strip=True) if a else None
        href = urljoin(BASE, a["href"]) if a else None

        # Wyciągnij ID z href: /aukcje/licytacja/506922/...
        auction_id = None
        if a and a.has_attr("href"):
            m = re.search(r"/licytacja/(\d+)", a["href"])
            if m:
                auction_id = m.group(1)

        if auction_id and title and href:
            out.append({
                "id": auction_id,
                "title": title,
                "href": href,
                "end_ts": end_ts
            })
    return out

def crawl_all():
    url = urljoin(BASE, START_PATH)
    html = fetch_page(url)
    soup = BeautifulSoup(html, "html.parser")

    max_pages = parse_max_pages(soup)
    auctions = parse_auctions(soup)

    # Strony 2..N (jeśli na stronie mają paginację przez ?page=)
    for p in range(2, max_pages + 1):
        page_url = urljoin(BASE, f"{START_PATH}?page={p}")
        html = fetch_page(page_url)
        soup = BeautifulSoup(html, "html.parser")
        auctions.extend(parse_auctions(soup))

    return auctions

def upsert_and_report_new(con, auctions):
    cur = con.cursor()
    now = int(time.time())
    new_rows = []

    for a in auctions:
        cur.execute("SELECT id FROM auctions WHERE id = ?", (a["id"],))
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "INSERT INTO auctions (id, title, href, end_ts, first_seen_ts, last_seen_ts) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (a["id"], a["title"], a["href"], a["end_ts"], now, now)
            )
            new_rows.append(a)
        else:
            cur.execute(
                "UPDATE auctions SET title=?, href=?, end_ts=?, last_seen_ts=? WHERE id=?",
                (a["title"], a["href"], a["end_ts"], now, a["id"])
            )
    con.commit()
    return new_rows

def human_time(ts):
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "?"

def main():
    con = ensure_db()
    auctions = crawl_all()
    new_rows = upsert_and_report_new(con, auctions)

    if not auctions:
        print("Brak danych – sprawdź START_PATH lub strukturę strony.")
        return

    if new_rows:
        print(f"Nowe aukcje ({len(new_rows)}):")
        for a in new_rows:
            print(f"- [{a['id']}] {a['title']} | koniec: {human_time(a['end_ts'])} | {a['href']}")
    else:
        print("Dziś brak nowych aukcji.")

    # Dla ciekawych: pokaż 5 najbliższych zakończeń (z całej bazy)
    cur = con.cursor()
    cur.execute("""
        SELECT id, title, href, end_ts
        FROM auctions
        WHERE end_ts > strftime('%s','now')  -- jeszcze trwają
        ORDER BY end_ts ASC
        LIMIT 5
    """)
    rows = cur.fetchall()
    if rows:
        print("\nNajbliższe zakończenia:")
        for (aid, title, href, end_ts) in rows:
            print(f"- [{aid}] {title} | {human_time(end_ts)} | {href}")

if __name__ == "__main__":
    main()
