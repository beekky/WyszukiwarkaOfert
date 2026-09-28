import subprocess
import sys

# Automatyczna instalacja przeglądarki Playwright w chmurze
try:
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
except Exception:
    pass

import streamlit as st
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import urllib.parse
import re
import time
import json
import os
from datetime import datetime

st.set_page_config(page_title="OLX Analytics & Price Tracker", page_icon="⚡", layout="wide")

# --- CUSTOM CSS: MOTYW SAAS DASHBOARD ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    :root {
        --dash-bg: #0b0f19;
        --sidebar-bg: #111827;
        --card-bg: #1e293b;
        --border-color: #334155;
        --accent-cyan: #00f2fe;
        --accent-green: #10b981;
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
    }

    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], .main {
        background-color: var(--dash-bg) !important;
        color: var(--text-main) !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }

    section[data-testid="stSidebar"] {
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--border-color) !important;
    }

    label, p, span, h1, h2, h3, h4, h5, h6, .stMarkdown {
        color: var(--text-main) !important;
    }

    input, textarea, div[data-baseweb="select"], div[data-baseweb="base-input"] {
        background-color: #0f172a !important;
        color: #ffffff !important;
        border-color: var(--border-color) !important;
        border-radius: 8px !important;
    }

    .metric-card {
        background-color: #1e293b;
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: var(--accent-cyan);
    }
    .metric-label {
        font-size: 0.85rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .pill-tag {
        display: inline-block;
        font-size: 0.8rem;
        padding: 4px 10px;
        border-radius: 6px;
        background: #0f172a;
        color: #cbd5e1 !important;
        margin-right: 6px;
        margin-top: 6px;
        border: 1px solid var(--border-color);
    }
    .pill-delivery {
        background: rgba(0, 242, 254, 0.1);
        color: var(--accent-cyan) !important;
        border-color: rgba(0, 242, 254, 0.3);
    }

    div.stButton > button {
        border-radius: 8px !important;
        font-weight: 700 !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button[kind="primary"], div.stButton > button:first-child {
        background: linear-gradient(135deg, #00f2fe 0%, #3b82f6 100%) !important;
        color: #0f172a !important;
        border: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- TRWAŁY ZAPIS ZGŁOSZEŃ JSON ---
PLIK_BUFORA = "zgloszenia_bufor.json"

def wczytaj_bufor_z_pliku():
    if os.path.exists(PLIK_BUFORA):
        try:
            with open(PLIK_BUFORA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def zapisz_bufor_do_pliku():
    try:
        with open(PLIK_BUFORA, "w", encoding="utf-8") as f:
            json.dump(st.session_state["bufor_zgloszen"], f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Błąd zapisu bufora: {e}")

if "bufor_zgloszen" not in st.session_state:
    st.session_state["bufor_zgloszen"] = wczytaj_bufor_z_pliku()

if "zalogowany_admin" not in st.session_state:
    st.session_state["zalogowany_admin"] = False

if "stop_requested" not in st.session_state:
    st.session_state["stop_requested"] = False

# --- PATCH NOTES ---
HISTORIA_ZMIAN = [
    {
        "wersja": "v2.1.0",
        "data": "28 Września 2026",
        "wazna": True,
        "opis": "Poprawka braku wyników wyszukiwania i obsługa zmian struktury OLX.",
        "zmiany": [
            "Zaktualizowano selektory kart ogłoszeń na OLX (obsługa data-cy, data-testid oraz ad-card).",
            "Naprawiono filtr wycinający polskie znaki diakrytyczne (ą, ć, ę, ł, ń, ó, ś, ź, ż) z zapytania.",
            "Wprowadzono automatyczne wykrywanie blokad antybotowych (Cloudflare / CAPTCHA) z czytelną informacją dla użytkownika.",
            "Złagodzono algorytm weryfikacji trafności w czy_trafna_oferta."
        ]
    },
    {
        "wersja": "v2.0.0",
        "data": "28 Września 2026",
        "wazna": True,
        "opis": "Zabezpieczenie przed błędem TargetClosedError i dodanie opcji ręcznego przerwania skanowania.",
        "zmiany": ["Dodano przycisk 🛑 Stop oraz zabezpieczenie pętli Playwright."]
    }
]

SLOWA_USZKODZONE = [
    'uszkodzon', 'zepsut', 'nie działy', 'nie działa', 'niedziała', 'na części', 
    'defekt', 'pęknięt', 'spalon', 'nietestowan', 'brak możliwości sprawdzenia', 
    'wada', 'wady', 'zbit', 'po zalaniu', 'nietestowane', 'stan nieznany', 'usterka'
]

SMIECI_BRANŻOWE = {
    'bluza', 'bluzka', 'koszulka', 'buty', 'spodnie', 'dres', 'kurtka', 
    'gra', 'gry', 'ps3', 'ps4', 'ps5', 'xbox', 'dvd', 'cd', 'spódnica', 'pudełko'
}

GENERYCZNE_SLOWA = {
    'champion', 'champions', 'sport', 'sports', 'game', 'games', 'pro', 'max', 
    'plus', 'super', 'mini', 'lite', 'v1', 'v2', 'v3', 'ps3', 'ps4', 'ps5', 'xbox'
}

DOMENY_REKLAMOWE = [
    'google-analytics', 'googletagmanager', 'doubleclick', 'googleadservices',
    'facebook.net', 'facebook.com/tr', 'criteo', 'hotjar', 'onesignal', 
    'scorecardresearch', 'analytics', 'adsystem', 'adservice', 'pixel', 
    'tracker', 'rubiconproject', 'pubmatic', 'openx', 'adnxs', 'smartadserver'
]

KATEGORIE_OLX = {
    "Wszystkie kategorie": "oferty",
    "Motoryzacja": "motoryzacja",
    "Elektronika": "elektronika",
    "Dom i Ogród": "dom-ogrod",
    "Moda": "moda",
    "Nieruchomości": "nieruchomosci",
    "Sport i Hobby": "sport-hobbys",
    "Dla Dzieci": "dla-dzieci",
    "Rolnictwo": "rolnictwo",
    "Zwierzęta": "zwierzeta",
    "Usługi i Firmy": "uslugi-firmy",
    "Antyki i Kolekcje": "antyki-sztuka-kolekcje"
}

def czy_podobne_zgloszenie(tekst1, tekst2, kategoria1, kategoria2):
    if kategoria1 != kategoria2:
        return False
    s1 = set(re.findall(r'\w+', tekst1.lower()))
    s2 = set(re.findall(r'\w+', tekst2.lower()))
    s1_f = {w for w in s1 if len(w) > 2}
    s2_f = {w for w in s2 if len(w) > 2}
    if not s1_f or not s2_f:
        return False
    return len(s1_f.intersection(s2_f)) / len(s1_f.union(s2_f)) > 0.3

def wyciagnij_nazwe_z_linku(url_lub_tekst):
    if url_lub_tekst.startswith("http://") or url_lub_tekst.startswith("https://"):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url_lub_tekst, headers=headers, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            h1 = soup.find('h1')
            title = h1.text.strip() if h1 else soup.title.text.strip()
            czysta_nazwa = re.split(r'[|\-–]', title)[0].strip()
            slowa = czysta_nazwa.split()
            return " ".join(slowa[:6]) if len(slowa) > 6 else czysta_nazwa
        except Exception:
            return url_lub_tekst
    return url_lub_tekst

def parse_price(price_str):
    if not price_str:
        return 999999.0
    cleaned = re.sub(r'[^\d,.]', '', price_str).replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return 999999.0

def analizuj_i_stworz_skrot_opisu(tekst_opisu):
    if not tekst_opisu:
        return False, "Brak opisu", "Brak treści opisu w ogłoszeniu.", []
    tekst_lower = tekst_opisu.lower()
    znalezione_wady = [s for s in SLOWA_USZKODZONE if s in tekst_lower]
    czy_uszkodzony = bool(znalezione_wady)
    ostrzezenie = f"⚠️ Wykryto w opisie słowa sugerujące wadę: {', '.join(set(znalezione_wady))}" if czy_uszkodzony else ""

    cechy = []
    if any(k in tekst_lower for k in ['gwarancj', 'rękojmi']):
        cechy.append("📜 Gwarancja / Rękojmia")
    if any(k in tekst_lower for k in ['faktura', 'paragon', 'dowód zakupu']):
        cechy.append("🧾 Paragon / Faktura")
    if any(k in tekst_lower for k in ['komplet', 'pełen zestaw', 'pudełko', 'oryginalne opakowanie']):
        cechy.append("📦 Pełen zestaw")

    czysty = tekst_opisu.strip()
    skrot = czysty[:800] + "\n\n[... ciąg dalszy w ogłoszeniu]" if len(czysty) > 800 else czysty
    return czy_uszkodzony, ostrzezenie, skrot, cechy

def wykryj_forme_dostawy(card, tresc_opisu):
    try:
        card_html = card.inner_html().lower() if card else ""
        ma_olx = "przesyłka olx" in card_html or "kup z przesyłką" in card_html or card.query_selector('[data-testid="delivery-icon"]') is not None
    except Exception:
        ma_olx = False
        
    tekst_lower = tresc_opisu.lower() if tresc_opisu else ""
    ma_odbior = any(kw in tekst_lower for kw in ['odbiór osobisty', 'odbior osobisty', 'tylko odbiór'])
    ma_wysylka = any(kw in tekst_lower for kw in ['wysyłka', 'wysylka', 'paczkomat', 'kurier', 'poczta'])

    formy = []
    if ma_olx: formy.append("📦 Przesyłka OLX")
    elif ma_wysylka: formy.append("✉️ Wysyłka prywatna")
    if ma_odbior: formy.append("🤝 Odbiór osobisty")
    return " | ".join(formy) if formy else "ℹ️ Brak szczegółów dostawy"

def czy_trafna_oferta(szukana_fraza, znaleziony_tytul, url="", tresc_opisu=""):
    url_slug = re.sub(r'[^a-zA-Z0-9]', ' ', url).lower()
    pelny_tekst = f"{znaleziony_tytul} {url_slug} {tresc_opisu}".lower()
    fraza_lower = szukana_fraza.lower()

    for smiec in SMIECI_BRANŻOWE:
        if smiec in pelny_tekst and smiec not in fraza_lower:
            return False

    slowa_zapytania = [s.lower() for s in re.findall(r'\w+', szukana_fraza) if len(s) >= 2 or s.isdigit()]
    if not slowa_zapytania:
        return True

    trafione = [s for s in slowa_zapytania if s in pelny_tekst]
    if len(slowa_zapytania) >= 2:
        return (len(trafione) / len(slowa_zapytania)) >= 0.4
    return len(trafione) >= 1

def zablokuj_zbedne_zasoby_i_reklamy(route):
    try:
        url = route.request.url.lower()
        res_type = route.request.resource_type
        if res_type in ["image", "media", "font"] or any(domena in url for domena in DOMENY_REKLAMOWE):
            route.abort()
        else:
            route.continue_()
    except Exception:
        pass

def formatuj_czas(sekundy):
    s = int(sekundy)
    m, s = divmod(s, 60)
    return f"{m}m {s}s" if m > 0 else f"{s}s"

# --- ZOPTAMALIZOWANA I ODPORNA PĘTLA SKANOWANIA ---
def pobierz_oferty_olx(fraza, kategorie_slugs, stany_olx, cena_min, cena_max, pasek_postepu, tekst_statusu, stop_container):
    oferty, odrzucone_list, unikalne_linki = [], [], set()
    MAX_OFERT, MAX_STRON_PER_KAT = 100, 30

    # Poprawne zachowanie polskich znaków w nazwie
    fraza_clean = re.sub(r'\s+', ' ', fraza.strip())
    olx_query_clean = re.sub(r'[^a-zA-Z0-9ąęłśćóżźĄĘŁŚĆÓŻŹ\s-]', '', fraza_clean).strip().replace(" ", "-")
    olx_query = urllib.parse.quote(olx_query_clean)

    olx_map = {"Nowe": "new", "Używane": "used", "Uszkodzone": "damaged"}
    olx_state_param = "".join([f"&search%5Bfilter_enum_state%5D%5B{i}%5D={olx_map[s]}" for i, s in enumerate(stany_olx) if s in olx_map])
    olx_price_param = ""
    if cena_min > 0: olx_price_param += f"&search%5Bfilter_float_price%3Afrom%5D={cena_min}"
    if cena_max > 0: olx_price_param += f"&search%5Bfilter_float_price%3Ato%5D={cena_max}"

    tekst_statusu.write("⚡ Uruchamiam silnik w tle z blokadą reklam...")
    pasek_postepu.progress(2)
    start_time = time.time()
    bot_blocked = False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, 
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                locale="pl-PL"
            )
            context.route("**/*", zablokuj_zbedne_zasoby_i_reklamy)
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            total_kategorii = len(kategorie_slugs)

            for kat_idx, kategoria_slug in enumerate(kategorie_slugs, start=1):
                if len(oferty) >= MAX_OFERT or st.session_state.get("stop_requested", False): 
                    break

                for strona in range(1, MAX_STRON_PER_KAT + 1):
                    if len(oferty) >= MAX_OFERT or st.session_state.get("stop_requested", False): 
                        break

                    elapsed_sec = time.time() - start_time
                    tekst_statusu.write(f"⚡ Kat. {kat_idx}/{total_kategorii} | Strona {strona} (znaleziono: {len(oferty)}) | ⏱️ {formatuj_czas(elapsed_sec)}")

                    olx_url = f"https://www.olx.pl/{kategoria_slug}/q-{olx_query}/?page={strona}&search%5Border%5D=filter_float_price%3Aasc{olx_state_param}{olx_price_param}"
                    
                    try:
                        page.goto(olx_url, wait_until="domcontentloaded", timeout=15000)
                    except Exception: 
                        pass
                    
                    # Weryfikacja czy OLX nie zablokował IP serwera (Cloudflare Bot Challenge)
                    page_title = page.title().lower()
                    if "cloudflare" in page_title or "security check" in page_title or "access denied" in page_title:
                        bot_blocked = True
                        break

                    try:
                        # Rozszerzony selektor odpowiadający starej i nowej strukturze OLX
                        cards = page.query_selector_all('div[data-cy="l-card"], div[data-testid="l-card"], [data-testid="ad-card"]')
                        if not cards and strona == 1:
                            # Próba alternatywnego oczekiwania
                            page.wait_for_selector('div[data-cy="l-card"], div[data-testid="l-card"]', timeout=4000)
                            cards = page.query_selector_all('div[data-cy="l-card"], div[data-testid="l-card"], [data-testid="ad-card"]')
                            
                        if not cards: 
                            break

                        for card in cards: 
                            if len(oferty) >= MAX_OFERT or st.session_state.get("stop_requested", False): 
                                break
                                
                            title_elem = card.query_selector('h6, h4, [data-testid="ad-title"], [data-cy="ad-card-title"]')
                            price_elem = card.query_selector('p[data-testid="ad-price"], [data-cy="ad-price"]')
                            link_elem = card.query_selector('a')
                            
                            if title_elem and price_elem and link_elem:
                                tytul = title_elem.inner_text().strip()
                                cena_str = price_elem.inner_text().strip()
                                cena_num = parse_price(cena_str)
                                link = link_elem.get_attribute('href') or ""
                                if link and not link.startswith('http'): link = "https://www.olx.pl" + link

                                if link in unikalne_linki or (cena_min > 0 and cena_num < cena_min) or (cena_max > 0 and cena_num > cena_max):
                                    continue

                                tresc_opisu = ""
                                try:
                                    detail_page = context.new_page()
                                    detail_page.goto(link, wait_until="domcontentloaded", timeout=8000)
                                    desc_elem = detail_page.query_selector('div[data-cy="ad_description"], div[class*="css-1o9z2s"], [data-testid="ad_description"]')
                                    if desc_elem: tresc_opisu = desc_elem.inner_text()
                                    detail_page.close()
                                except Exception: 
                                    pass

                                if not czy_trafna_oferta(fraza_clean, tytul, link, tresc_opisu):
                                    odrzucone_list.append(f"{tytul} ({cena_str})")
                                    continue

                                czy_uszkodzony, ostrzezenie_opis, skrot_opisu, cechy_z_opisu = analizuj_i_stworz_skrot_opisu(tresc_opisu)
                                dostawa_info = wykryj_forme_dostawy(card, tresc_opisu)

                                unikalne_linki.add(link)
                                oferty.append({
                                    "źródło": "OLX", "tytuł": tytul, "cena_str": cena_str, "cena_val": cena_num,
                                    "link": link, "ostrzezenie": ostrzezenie_opis, "czy_uszkodzony": czy_uszkodzony,
                                    "skrot_opisu": skrot_opisu, "cechy": cechy_z_opisu, "dostawa": dostawa_info
                                })

                        pasek_postepu.progress(min(98, int((kat_idx / total_kategorii) * 100)))
                    except Exception:
                        break

            try:
                browser.close()
            except Exception:
                pass
    except Exception:
        pass

    total_time_formatted = formatuj_czas(time.time() - start_time)
    oferty.sort(key=lambda x: x['cena_val'])
    pasek_postepu.progress(100)
    
    if bot_blocked:
        st.warning("⚠️ Serwer OLX tymczasowo ograniczył zapytania z tego IP (weryfikacja botowa). Odczekaj chwilę lub spróbuj zaświadczyć wyszukiwanie z bardziej precyzyjną nazwą.")
        
    return oferty, odrzucone_list, total_time_formatted

# --- DIALOG LOGOWANIA ADMINA ---
@st.dialog("🔐 Panel Logowania Administratora")
def dialog_logowania():
    st.write("Wprowadź dane dostępowe:")
    login = st.text_input("Login", key="dialog_login_input")
    haslo = st.text_input("Hasło", type="password", key="dialog_pass_input")
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        if st.button("Zaloguj się", use_container_width=True):
            if login == "admin" and haslo == "admin":
                st.session_state["zalogowany_admin"] = True
                st.success("Zalogowano!")
                st.rerun()
            else:
                st.error("Błędny login lub hasło!")
    with col_l2:
        if st.button("Anuluj", use_container_width=True):
            st.rerun()

# --- UKŁAD STRONY: PANEL BOCZNY ---

with st.sidebar:
    st.markdown("## ⚙️ Panel Sterowania")
    st.caption("Skonfiguruj zapytanie do skanera OLX")

    input_data = st.text_input("Szukany przedmiot / Link:", placeholder="np. Rower Kross Hexagon")

    wybrane_kategorie_nazwy = st.multiselect(
        "Kategorie OLX:", 
        list(KATEGORIE_OLX.keys()), 
        default=["Wszystkie kategorie"]
    )

    stany_olx = st.multiselect("Stan przedmiotu:", ["Nowe", "Używane", "Uszkodzone"], default=["Nowe", "Używane"])

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        cena_min = st.number_input("Cena min:", min_value=0, value=0, step=50)
    with col_s2:
        cena_max = st.number_input("Cena max:", min_value=0, value=0, step=50)

    col_btn1, col_btn2 = st.columns([2, 1])
    with col_btn1:
        przycisk_szukaj = st.button("⚡ Uruchom", use_container_width=True, type="primary")
    with col_btn2:
        if st.button("🛑 Stop", use_container_width=True, help="Przerwij skanowanie"):
            st.session_state["stop_requested"] = True
            st.toast("Wysłano sygnał zatrzymania...")

    st.divider()
    
    col_adm1, col_adm2 = st.columns([1, 3])
    with col_adm1:
        if st.button("🔑", help="Wloguj się do panelu zarządczego"):
            dialog_logowania()
    with col_adm2:
        st.caption("Tryb Admina" if not st.session_state["zalogowany_admin"] else "✅ Zalogowany Admin")

# --- GŁÓWNY WORKSPACE ---

tab_search, tab_patch_notes, tab_feedback = st.tabs([
    "🔍 Wyniki i Analityka", 
    "📋 Lista Zmian (Patch Notes)", 
    "💬 Zgłoś Błąd / Feedback"
])

# === ZAKŁADKA 1: WYNIKI I ANALITYKA ===
with tab_search:
    if przycisk_szukaj:
        st.session_state["stop_requested"] = False
        if not input_data.strip():
            st.warning("Proszę podać frazę wyszukiwania lub wkleić link w panelu bocznym.")
        elif not wybrane_kategorie_nazwy:
            st.warning("Proszę wybrać przynajmniej jedną kategorię w panelu bocznym.")
        else:
            szukana_fraza = wyciagnij_nazwe_z_linku(input_data)
            
            if "Wszystkie kategorie" in wybrane_kategorie_nazwy:
                kategorie_slugs = ["oferty"]
            else:
                kategorie_slugs = [KATEGORIE_OLX[k] for k in wybrane_kategorie_nazwy]
            
            pasek = st.progress(0)
            status = st.empty()
            stop_container = st.empty()
            
            wyniki, odrzucone, czas_pracy = pobierz_oferty_olx(
                szukana_fraza, kategorie_slugs, stany_olx, cena_min, cena_max, 
                pasek, status, stop_container
            )
            
            pasek.empty()
            status.empty()
            stop_container.empty()
            
            if not wyniki:
                st.error("Nie znaleziono pasujących ofert w podanym zakresie cenowym.")
            else:
                srednia_cena = sum(o['cena_val'] for o in wyniki) / len(wyniki)
                
                if st.session_state.get("stop_requested", False):
                    st.warning(f"🛑 Wyszukiwanie zostało przerwane na życzenie użytkownika. Wyświetlam {len(wyniki)} ofert pobranych do momentu zatrzymania:")
                else:
                    st.success(f"✨ Znaleziono {len(wyniki)} trafnych ofert na OLX w czasie {czas_pracy}! Posortowano od najniższej ceny:")

                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.markdown(f"<div class='metric-card'><div class='metric-value'>{len(wyniki)}</div><div class='metric-label'>Trafnych Ofert</div></div>", unsafe_allow_html=True)
                with m2:
                    st.markdown(f"<div class='metric-card'><div class='metric-value'>{wyniki[0]['cena_str']}</div><div class='metric-label'>Najniższa Cena</div></div>", unsafe_allow_html=True)
                with m3:
                    st.markdown(f"<div class='metric-card'><div class='metric-value'>{srednia_cena:.2f} zł</div><div class='metric-label'>Średnia Cena</div></div>", unsafe_allow_html=True)
                with m4:
                    st.markdown(f"<div class='metric-card'><div class='metric-value'>{czas_pracy}</div><div class='metric-label'>Czas Skanowania</div></div>", unsafe_allow_html=True)

                st.markdown("---")

                for idx, o in enumerate(wyniki, start=1):
                    col_rank, col_main, col_price, col_btn = st.columns([0.8, 5, 2.2, 2])
                    
                    with col_rank:
                        st.markdown(f"<div style='font-size:1.4rem; font-weight:800; color:#00f2fe;'>#{idx}</div>", unsafe_allow_html=True)
                        st.caption(f"**{o['źródło']}**")
                    
                    with col_main:
                        st.markdown(f"#### {o['tytuł']}")
                        
                        tags_html = f"<span class='pill-tag pill-delivery'>🚚 {o['dostawa']}</span>"
                        for c in o['cechy']:
                            tags_html += f"<span class='pill-tag'>{c}</span>"
                        st.markdown(tags_html, unsafe_allow_html=True)

                        with st.expander("📄 Szczegółowy podgląd opisu"):
                            st.text(o['skrot_opisu'])

                        if o['ostrzezenie']:
                            st.error(o['ostrzezenie'])

                    with col_price:
                        st.markdown(f"<div style='font-size:1.4rem; font-weight:800; color:#10b981; background:rgba(16,185,129,0.1); padding:6px 14px; border-radius:8px; display:inline-block;'>💰 {o['cena_str']}</div>", unsafe_allow_html=True)
                    
                    with col_btn:
                        st.link_button("Zobacz ofertę ↗", o['link'], use_container_width=True)
                    
                    st.divider()

                if odrzucone:
                    with st.expander(f"🗑️ Odrzucone oferty ({len(odrzucone)})"):
                        for item in odrzucone[:50]:
                            st.text(item)
    else:
        st.info("👈 Wypełnij dane w lewym panelu sterowania i kliknij **'⚡ Uruchamiam'**, aby pobrać oferty.")

# === ZAKŁADKA 2: PATCH NOTES ===
with tab_patch_notes:
    st.header("📋 Historia Zmian (Patch Notes)")
    tylko_wazne = st.checkbox("Pokaż tylko najważniejsze wersje (Major Releases)", value=False)

    for item in HISTORIA_ZMIAN:
        if tylko_wazne and not item["wazna"]: continue
        badge = "🚀 WAŻNA WERSJA" if item["wazna"] else "🛠️ POPRAWKA"
        st.subheader(f"{item['wersja']} — {badge}")
        st.caption(f"Data wydania: {item['data']} | *{item['opis']}*")
        for zmiana in item["zmiany"]:
            st.markdown(f"* {zmiana}")
        st.divider()

# === ZAKŁADKA 3: FEEDBACK / ZGŁOSZENIA ===
with tab_feedback:
    st.header("💬 Centrum Zgłoszeń i Uwag")
    st.write("Coś nie działa, a może masz pomysł na nową funkcję? Zgłoś to poniżej.")

    with st.form("formularz_zgloszenia", clear_on_submit=True):
        col_typ, col_autor = st.columns([2, 2])
        with col_typ:
            typ_zgloszenia = st.selectbox("Kategoria:", ["🔴 Błąd w działaniu", "⚠️ Błędne/nietrafne wyniki", "💡 Propozycja nowej funkcji", "ℹ️ Inne"])
        with col_autor:
            autor = st.text_input("Nick / Kontakt (opcjonalnie):", placeholder="np. Janek")

        opis_problem = st.text_area("Opis sytuacji:", placeholder="Co nie działa...")
        submit = st.form_submit_button("Wyślij zgłoszenie")

        if submit:
            if not opis_problem.strip():
                st.error("Proszę wpisać opis.")
            else:
                autor_clean = autor.strip() if autor.strip() else "Anonim"
                opis_clean = opis_problem.strip()
                
                znaleziony_duplikat = None
                for zgl in st.session_state["bufor_zgloszen"]:
                    if czy_podobne_zgloszenie(opis_clean, zgl["opis"], typ_zgloszenia, zgl["kategoria"]):
                        znaleziony_duplikat = zgl
                        break

                if znaleziony_duplikat:
                    znaleziony_duplikat["licznik"] += 1
                    znaleziony_duplikat["priorytet"] = "🔥 Wysoki Priorytet"
                    znaleziony_duplikat["czas_ostatniego"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if autor_clean not in znaleziony_duplikat["autorzy"]:
                        znaleziony_duplikat["autorzy"].append(autor_clean)
                    znaleziony_duplikat["historia_opisow"].append(opis_clean)
                    zapisz_bufor_do_pliku()
                    st.success(f"Połączono zgłoszenie z istniejącym (zgłoszono {znaleziony_duplikat['licznik']}x)!")
                else:
                    nowy_wpis = {
                        "id": len(st.session_state["bufor_zgloszen"]) + 1,
                        "czas_pierwszego": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "czas_ostatniego": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "kategoria": typ_zgloszenia,
                        "autorzy": [autor_clean],
                        "opis": opis_clean,
                        "status": "⏳ Oczekuje",
                        "priorytet": "Normalny",
                        "licznik": 1,
                        "historia_opisow": [opis_clean]
                    }
                    st.session_state["bufor_zgloszen"].insert(0, nowy_wpis)
                    zapisz_bufor_do_pliku()
                    st.success("Zgłoszenie dodane do bufora.")

    if st.session_state["zalogowany_admin"]:
        st.divider()
        col_adm_head, col_adm_btn = st.columns([4, 1])
        with col_adm_head:
            st.subheader(f"📥 Bufor Zgłoszeń ({len(st.session_state['bufor_zgloszen'])}) — Tryb Admina")
        with col_adm_btn:
            if st.button("🚪 Wyloguj Admina"):
                st.session_state["zalogowany_admin"] = False
                st.rerun()

        if not st.session_state["bufor_zgloszen"]:
            st.info("Brak zgłoszeń w buforze.")
        else:
            if st.button("🗑️ Wyczyść cały bufor"):
                st.session_state["bufor_zgloszen"] = []
                zapisz_bufor_do_pliku()
                st.rerun()

            opcje_statusu = ["⏳ Oczekuje", "⚙️ W trakcie naprawy", "✅ Rozwiązany", "❌ Odrzucony / Duplikat"]

            for zgl in st.session_state["bufor_zgloszen"]:
                prio_badge = "🔥 WYSOKI PRIORYTET" if zgl["priorytet"] == "🔥 Wysoki Priorytet" or zgl["licznik"] > 1 else "NORMALNY"
                
                with st.expander(f"#{zgl['id']} [{zgl['kategoria']}] — {prio_badge} (x{zgl['licznik']}) | {zgl['status']}"):
                    col_s1, col_s2 = st.columns([2.5, 1.5])
                    with col_s1:
                        st.caption(f"Autorzy: **{', '.join(zgl['autorzy'])}**")
                        st.write(f"**Główny opis:** {zgl['opis']}")
                    with col_s2:
                        nowy_status = st.selectbox("Zmień status:", opcje_statusu, index=opcje_statusu.index(zgl["status"]) if zgl["status"] in opcje_statusu else 0, key=f"status_select_{zgl['id']}")
                        if nowy_status != zgl["status"]:
                            zgl["status"] = nowy_status
                            zapisz_bufor_do_pliku()
                            st.toast(f"Zmieniono status #{zgl['id']}")
                            st.rerun()
