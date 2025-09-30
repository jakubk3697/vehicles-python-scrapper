#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplikacja webowa do monitorowania nowych aukcji aut ze Szwajcarii
"""

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

DB_PATH = Path("autazeszwajcarii.db")

def get_db_connection():
    """Połączenie z bazą danych"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Utwórz tabele jeśli nie istnieją
    cur = conn.cursor()
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
    cur.execute("""
    CREATE TABLE IF NOT EXISTS watched_searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        search_term TEXT UNIQUE,
        created_ts INTEGER,
        last_check_ts INTEGER
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_ts INTEGER
    )
    """)
    conn.commit()
    
    return conn

def human_time(ts):
    """Konwersja timestamp na czytelny format"""
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "?"

def get_time_until_end(end_ts):
    """Oblicz czas do końca aukcji"""
    now = int(time.time())
    if end_ts <= now:
        return "ZAKOŃCZONO"
    
    diff = end_ts - now
    days = diff // 86400
    hours = (diff % 86400) // 3600
    minutes = (diff % 3600) // 60
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

@app.route('/')
def index():
    """Strona główna"""
    return render_template('index.html')

@app.route('/api/new_auctions')
def api_new_auctions():
    """API - nowe aukcje od ostatniej wizyty"""
    conn = get_db_connection()
    
    # Pobierz timestamp ostatniej wizyty z parametru lub użyj domyślnego (ostatnie 24h)
    last_visit = request.args.get('since', int(time.time()) - 86400)
    try:
        last_visit = int(last_visit)
    except ValueError:
        last_visit = int(time.time()) - 86400
    
    query = """
    SELECT id, title, href, end_ts, first_seen_ts
    FROM auctions 
    WHERE first_seen_ts > ?
    ORDER BY first_seen_ts DESC
    LIMIT 100
    """
    
    auctions = conn.execute(query, (last_visit,)).fetchall()
    conn.close()
    
    result = []
    for auction in auctions:
        result.append({
            'id': auction['id'],
            'title': auction['title'],
            'href': auction['href'],
            'end_time': human_time(auction['end_ts']),
            'time_until_end': get_time_until_end(auction['end_ts']),
            'first_seen': human_time(auction['first_seen_ts']),
            'is_ended': auction['end_ts'] <= int(time.time())
        })
    
    return jsonify(result)

@app.route('/api/watched_searches')
def api_watched_searches():
    """API - obserwowane wyszukiwania"""
    conn = get_db_connection()
    
    # Pobierz wszystkie obserwowane frazy
    searches = conn.execute("""
        SELECT id, search_term, created_ts, last_check_ts
        FROM watched_searches
        ORDER BY created_ts DESC
    """).fetchall()
    
    result = []
    for search in searches:
        # Znajdź nowe aukcje dla tej frazy od ostatniego sprawdzenia
        last_check = search['last_check_ts'] or search['created_ts']
        
        new_auctions = conn.execute("""
            SELECT id, title, href, end_ts, first_seen_ts
            FROM auctions 
            WHERE first_seen_ts > ? 
            AND LOWER(title) LIKE LOWER(?)
            ORDER BY first_seen_ts DESC
            LIMIT 10
        """, (last_check, f"%{search['search_term']}%")).fetchall()
        
        result.append({
            'id': search['id'],
            'search_term': search['search_term'],
            'created': human_time(search['created_ts']),
            'last_check': human_time(search['last_check_ts']) if search['last_check_ts'] else 'Nigdy',
            'new_auctions': [
                {
                    'id': auction['id'],
                    'title': auction['title'],
                    'href': auction['href'],
                    'end_time': human_time(auction['end_ts']),
                    'time_until_end': get_time_until_end(auction['end_ts']),
                    'first_seen': human_time(auction['first_seen_ts']),
                    'is_ended': auction['end_ts'] <= int(time.time())
                }
                for auction in new_auctions
            ]
        })
    
    conn.close()
    return jsonify(result)

@app.route('/api/stats')
def api_stats():
    """API - statystyki"""
    conn = get_db_connection()
    
    # Całkowita liczba aukcji
    total = conn.execute("SELECT COUNT(*) as count FROM auctions").fetchone()['count']
    
    # Liczba obserwowanych wyszukiwań
    watched_searches_count = conn.execute("SELECT COUNT(*) as count FROM watched_searches").fetchone()['count']
    
    conn.close()
    
    return jsonify({
        'total_auctions': total,
        'watched_searches': watched_searches_count
    })

@app.route('/api/mark_visited')
def api_mark_visited():
    """API - oznacz aktualny czas jako ostatnią wizytę"""
    current_time = int(time.time())
    return jsonify({
        'success': True,
        'timestamp': current_time,
        'human_time': human_time(current_time)
    })

@app.route('/api/get_setting/<key>')
def api_get_setting(key):
    """API - pobierz ustawienie z bazy"""
    conn = get_db_connection()
    try:
        result = conn.execute("SELECT value FROM user_settings WHERE key = ?", (key,)).fetchone()
        if result:
            return jsonify({'success': True, 'value': result['value']})
        else:
            return jsonify({'success': False, 'value': None})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/set_setting/<key>', methods=['POST'])
def api_set_setting(key):
    """API - zapisz ustawienie do bazy"""
    data = request.get_json()
    value = data.get('value')
    
    conn = get_db_connection()
    try:
        current_time = int(time.time())
        conn.execute("""
            INSERT OR REPLACE INTO user_settings (key, value, updated_ts)
            VALUES (?, ?, ?)
        """, (key, value, current_time))
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/add_watched_search', methods=['POST'])
def api_add_watched_search():
    """API - dodaj nowe obserwowane wyszukiwanie"""
    data = request.get_json()
    search_term = data.get('search_term', '').strip()
    
    if not search_term:
        return jsonify({'success': False, 'error': 'Fraza wyszukiwania nie może być pusta'})
    
    conn = get_db_connection()
    try:
        current_time = int(time.time())
        conn.execute("""
            INSERT OR REPLACE INTO watched_searches (search_term, created_ts, last_check_ts)
            VALUES (?, ?, ?)
        """, (search_term, current_time, current_time))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Dodano obserwowanie frazy: {search_term}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/remove_watched_search/<int:search_id>', methods=['DELETE'])
def api_remove_watched_search(search_id):
    """API - usuń obserwowane wyszukiwanie"""
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM watched_searches WHERE id = ?", (search_id,))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Usunięto obserwowane wyszukiwanie'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/mark_search_checked/<int:search_id>', methods=['POST'])
def api_mark_search_checked(search_id):
    """API - oznacz wyszukiwanie jako sprawdzone"""
    conn = get_db_connection()
    try:
        current_time = int(time.time())
        conn.execute("""
            UPDATE watched_searches 
            SET last_check_ts = ? 
            WHERE id = ?
        """, (current_time, search_id))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Oznaczono jako sprawdzone'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/refresh')
def refresh():
    """Odśwież dane - uruchom skrypt scrapera"""
    import subprocess
    try:
        result = subprocess.run(['python3', 'scrape_autazeszwajcarii.py'], 
                              capture_output=True, text=True, timeout=300)
        return jsonify({
            'success': True,
            'output': result.stdout,
            'error': result.stderr
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Timeout - skrypt działał zbyt długo'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug, host='0.0.0.0', port=port)
