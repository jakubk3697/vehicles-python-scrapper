# Monitor Aukcji Aut ze Szwajcarii

Aplikacja webowa do monitorowania nowych aukcji aut ze strony autazeszwajcarii.pl.

## Funkcje

- 🔍 **Obserwowane wyszukiwania** - dodaj frazy (np. "audi", "bmw x3") i otrzymuj powiadomienia o nowych aukcjach
- 🆕 **Nowe aukcje** - pokazuje aukcje dodane od ostatniej wizyty
- 📊 **Statystyki** - liczba aukcji, aktywnych, nowych
- 🔄 **Automatyczne odświeżanie** - pobiera najnowsze dane ze strony

## Instalacja lokalna

```bash
# Sklonuj repozytorium
git clone <repo-url>
cd auta

# Zainstaluj zależności
pip install -r requirements.txt

# Uruchom aplikację
python app.py
```

Aplikacja będzie dostępna pod adresem: http://localhost:8080

## Użycie

1. **Dodaj obserwowane wyszukiwania** - wpisz frazę (np. "audi") i kliknij "Dodaj"
2. **Odśwież dane** - kliknij "🔄 Odśwież dane" aby pobrać najnowsze aukcje
3. **Oznacz jako odwiedzone** - kliknij "✅ Oznacz jako odwiedzone" aby wyczyścić listę nowych aukcji

## Technologie

- **Backend**: Python Flask
- **Frontend**: HTML, CSS, JavaScript
- **Baza danych**: SQLite
- **Web scraping**: BeautifulSoup, Requests

## Pliki

- `app.py` - główna aplikacja Flask
- `scrape_autazeszwajcarii.py` - skrypt do pobierania aukcji
- `templates/index.html` - interfejs webowy
- `requirements.txt` - zależności Python
