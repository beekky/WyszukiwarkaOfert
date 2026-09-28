import streamlit as st
import requests
from bs4 import BeautifulSoup
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

# --- OBSŁUGA TRWAŁEGO ZAPISU BUFORA ZGŁOSZEŃ ---
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

# --- OBSŁUGA TRWAŁEGO ZAPISU PATCH NOTES (JSON) ---
PLIK_PATCH_NOTES = "patch_notes.json"

DOMYSLNA_HISTORIA_ZMIAN = [
    {
        "wersja": "v3.1.0",
        "data": "28 Września 2026",
        "wazna": True,
        "opis": "Naprawa pobierania opisów oraz gruntowne czyszczenie kodu.",
        "zmiany": [
            "Wdrożono natychmiastowe pobieranie opisów przez per-offer API oraz parser __NEXT_DATA__, eliminując błędy braku opisu.",
            "Usunięto zbędne, powielone funkcje i nakładające się pętle skanujące (duża poprawa wydajności).",
            "Zoptymalizowano zużycie pamięci na serwerze chmurowym."
        ]
    },
    {
        "wersja": "v3.0.0",
        "data": "28 Września 2026",
        "wazna": True,
        "opis": "Playwright Native Single-Pass Engine z Auto-Query Fallback.",
        "zmiany": ["Zaimplementowano automatyczny fallback dla złożonych nazw przedmiotów."]
    },
    {
        "wersja": "v1.0.0",
        "data": "28 Września 2026",
        "wazna": True,
        "opis": "Pierwsza wersja silnika wyszukiwarki OLX.",
        "zmiany": ["Inicjalizacja aplikacji."]
    }
]

def wczytaj_patch_notes_z_pliku():
    if os.path.exists(PLIK_PATCH_NOTES):
        try:
            with open(PLIK_PATCH_NOTES, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DOMYSLNA_HISTORIA_ZMIAN
    else:
        try:
            with open(PLIK_PATCH_NOTES, "w", encoding="utf-8") as f:
                json.dump(DOMYSLNA_HISTORIA_ZMIAN, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return DOMYSLNA_HISTORIA_ZMIAN

def zapisz_patch_notes_do_pliku():
    try:
        with open(PLIK_PATCH_NOTES, "w", encoding="utf-8") as f:
            json.dump(st.session_state["historia_zmian"], f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Błąd zapisu Patch Notes: {e}")

# --- INICJALIZACJA SESSION STATE ---
if "bufor_zgloszen" not in st.session_state:
    st.session_state["bufor_zgloszen"] = wczytaj_bufor_z_pliku()

if "historia_zmian" not in st.session_state:
    st.session_state["historia_zmian"] = wczytaj_patch_notes_z_pliku()

if "zalogowany_admin" not in st.session_state:
    st.session_state["zalogowany_admin"] = False

if "stop_requested" not in st.session_state:
    st.session_state["stop_requested"] = False

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

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"
}

def czy_podobne_zgloszenie(tekst1, tekst2, kategoria1, kategoria2):
    if kategoria1 != kategoria2:
        return False
    s1 = set(re.findall(r'\w+', tekst1.lower()))
    s2 = set(re.findall(r'\w+', tekst2.lower()))
    s1_f = {w for w in s1 if len(w) > 1}
    s2_f = {w for w in s2 if len(w) > 1}
    if not s1_f or not s2_f:
        return False
    return len(s1_f.intersection(s2_f)) / len(s1_f.union(s2_f)) > 0.3

def wyciagnij_nazwe_z_linku(url_lub_tekst):
    if url_lub_tekst.startswith("http://") or url_lub_tekst.startswith("https://"):
        try:
            response = requests.get(url_lub_tekst, headers=HTTP_HEADERS, timeout=5)
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
        return 0.0
    cleaned = re.sub(r'[^\d,.]', '', str(price_str)).replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

# --- PRECYZYJNA ANALIZA OPISU I WAD ---
def analizuj_i_stworz_skrot_opisu(tekst_opisu):
    if not tekst_opisu or tekst_opisu.strip() in ["Brak treści opisu w ogłoszeniu.", "Brak podglądu opisu."]:
        return False, "", "Brak treści opisu w ogłoszeniu.", []
    
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
    skrot = czysty[:800] + "\n\n[... ciąg dalszy w ogłoszeniu na OLX]" if len(czysty) > 800 else czysty
    return czy_uszkodzony, ostrzezenie, skrot, cechy

def czy_trafna_oferta(szukana_fraza, znaleziony_tytul, url="", tresc_opisu="", parametry_str=""):
    url_slug = re.sub(r'[^a-zA-Z0-9ąęłśćóżźĄĘŁŚĆÓŻŹ]', ' ', url).lower()
    pelny_tekst = f"{znaleziony_tytul} {url_slug} {tresc_opisu} {parametry_str}".lower()
    fraza_lower = szukana_fraza.lower()

    for smiec in SMIECI_BRANŻOWE:
        if smiec in pelny_tekst and smiec not in fraza_lower:
            return False

    slowa_zapytania = [s.lower() for s in re.findall(r'[a-zA-Z0-9ąęłśćóżźĄĘŁŚĆÓŻŹ]+', szukana_fraza)]
    if not slowa_zapytania:
        return True

    istotne_slowa = [s for s in slowa_zapytania if s not in GENERYCZNE_SLOWA]

    if istotne_slowa:
        slowa_glowne = [s for s in istotne_slowa if len(s) > 1]
        if slowa_glowne:
            trafione_glowne = [s for s in slowa_glowne if s in pelny_tekst]
            if not trafione_glowne:
                return False

    trafione_wszystkie = [s for s in slowa_zapytania if s in pelny_tekst]
    return (len(trafione_wszystkie) / len(slowa_zapytania)) >= 0.33

# --- NIEZAWODNE, DWUSTOPNIOWE POBIERANIE PEŁNEGO OPISU OGŁOSZENIA ---
def pobierz_opis_ogloszenia(ad_id, url):
    # Krok 1: Bezpośrednie odpytanie OLX API per-offer (błyskawiczny JSON)
    if ad_id:
        try:
            api_url = f"https://www.olx.pl/api/v1/offers/{ad_id}"
            res = requests.get(api_url, headers=HTTP_HEADERS, timeout=4)
            if res.status_code == 200:
                raw_desc = res.json().get('data', {}).get('description', '')
                if raw_desc:
                    clean = BeautifulSoup(raw_desc, 'html.parser').get_text(separator="\n").strip()
                    if clean:
                        return clean
        except Exception:
            pass

    # Krok 2: Odczyt z HTML / Otomoto / __NEXT_DATA__
    try:
        res = requests.get(url, headers=HTTP_HEADERS, timeout=4)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Script __NEXT_DATA__
            next_data = soup.find('script', id='__NEXT_DATA__')
            if next_data and next_data.string:
                try:
                    data_json = json.loads(next_data.string)
                    ad_data = data_json.get('props', {}).get('pageProps', {}).get('ad', {}) or data_json.get('props', {}).get('pageProps', {}).get('data', {}).get('ad', {})
                    raw_desc = ad_data.get('description', '')
                    if raw_desc:
                        clean = BeautifulSoup(raw_desc, 'html.parser').get_text(separator="\n").strip()
                        if clean:
                            return clean
                except Exception:
                    pass

            # Otomoto / HTML Selectors
            desc_div = (soup.find('div', {'data-cy': 'ad_description'}) or 
                        soup.find('div', {'data-testid': 'ad_description'}) or
                        soup.find('div', {'data-testid': 'advert-description'}) or
                        soup.find('div', class_=re.compile(r'description-content|css-1o9z2s')))
            if desc_div:
                return desc_div.get_text(separator="\n").strip()
    except Exception:
        pass

    return "Brak treści opisu w ogłoszeniu."

def formatuj_czas(sekundy):
    s = int(sekundy)
    m, s = divmod(s, 60)
    return f"{m}m {s}s" if m > 0 else f"{s}s"

# --- ZOPTYMALIZOWANE SKANOWANIE API Z POBIERANIEM OPISÓW ---
def skanuj_olx_api_clean(fraza_do_wyslania, fraza_oryginalna, cena_min, cena_max, status_elem, max_oferty=100):
    oferty, odrzucone = [], []
    unikalne = set()
    query_encoded = urllib.parse.quote(fraza_do_wyslania)

    for offset in range(0, 160, 40):
        if len(oferty) >= max_oferty or st.session_state.get("stop_requested", False):
            break

        api_url = f"https://www.olx.pl/api/v1/offers/?query={query_encoded}&offset={offset}&limit=40"
        if cena_min > 0:
            api_url += f"&filter_float_price:from={cena_min}"
        if cena_max > 0:
            api_url += f"&filter_float_price:to={cena_max}"

        try:
            resp = requests.get(api_url, headers=HTTP_HEADERS, timeout=7)
            if resp.status_code != 200:
                break

            items = resp.json().get('data', [])
            if not items:
                break

            for item in items:
                if len(oferty) >= max_oferty or st.session_state.get("stop_requested", False):
                    break

                tytul = item.get('title', '')
                url_ad = item.get('url', '')
                ad_id = item.get('id')
                if not tytul or not url_ad:
                    continue

                link = url_ad if url_ad.startswith('http') else "https://www.olx.pl" + url_ad
                if link in unikalne:
                    continue

                price_obj = item.get('price', {})
                price_val = float(price_obj.get('value', 0.0) or 0.0) if isinstance(price_obj, dict) else 0.0
                price_str = price_obj.get('displayValue', f"{price_val:.0f} zł") if isinstance(price_obj, dict) else f"{price_val:.0f} zł"

                if cena_min > 0 and price_val < cena_min and price_val > 0:
                    continue
                if cena_max > 0 and price_val > cena_max:
                    continue

                status_elem.write(f"⚡ Pobieranie opisu dla: **{tytul[:45]}...**")

                # Odczyt opisu
                desc_raw = item.get('description', '')
                if desc_raw:
                    tresc_opisu = BeautifulSoup(desc_raw, 'html.parser').get_text(separator="\n").strip()
                else:
                    tresc_opisu = pobierz_opis_ogloszenia(ad_id, link)

                params = item.get('params', [])
                param_texts = []
                if isinstance(params, list):
                    for p in params:
                        if isinstance(p, dict):
                            v_label = p.get('value', {})
                            if isinstance(v_label, dict):
                                v_label = v_label.get('label', '')
                            param_texts.append(str(v_label))

                parametry_str = " ".join(param_texts)

                if not czy_trafna_oferta(fraza_oryginalna, tytul, link, tresc_opisu, parametry_str):
                    odrzucone.append(f"{tytul} ({price_str})")
                    continue

                czy_u, ostrz, skrot, cechy = analizuj_i_stworz_skrot_opisu(tresc_opisu)
                deliv_obj = item.get('delivery', {})
                is_deliv = deliv_obj.get('is_delivery', False) if isinstance(deliv_obj, dict) else False
                dostawa_info = "📦 Przesyłka OLX" if is_deliv else "✉️ Dostawa prywatna / Odbiór"

                unikalne.add(link)
                oferty.append({
                    "źródło": "Otomoto" if "otomoto.pl" in link else "OLX", 
                    "tytuł": tytul, 
                    "cena_str": price_str, 
                    "cena_val": price_val,
                    "link": link, 
                    "ostrzezenie": ostrz, 
                    "czy_uszkodzony": czy_u,
                    "skrot_opisu": skrot if skrot else "Opis w ogłoszeniu na OLX.", 
                    "cechy": cechy, 
                    "dostawa": dostawa_info
                })

        except Exception:
            break

    return oferty, odrzucone

# --- GŁÓWNA FUNKCJA SKANERA ---
def pobierz_oferty_olx(fraza, kategorie_slugs, stany_olx, cena_min, cena_max, pasek_postepu, tekst_statusu, stop_container):
    start_time = time.time()
    fraza_clean = re.sub(r'\s+', ' ', fraza.strip())

    tekst_statusu.write("⚡ Uruchamiam skaner OLX...")
    pasek_postepu.progress(15)

    # Próba 1: Pobieranie bezpośrednie
    oferty, odrzucone = skanuj_olx_api_clean(fraza_clean, fraza_clean, cena_min, cena_max, tekst_statusu)
    pasek_postepu.progress(70)

    # Próba 2: Auto-Query Fallback dla haseł złożonych (np. opel astra k -> opel astra)
    if not oferty and len(fraza_clean.split()) > 1:
        fraza_uproszczona = " ".join([w for w in fraza_clean.split() if len(w) > 1 or not w.isalnum()])
        if fraza_uproszczona and fraza_uproszczona != fraza_clean:
            tekst_statusu.write(f"⚡ Automatyczny fallback dla frazy ogólnej: '{fraza_uproszczona}'...")
            oferty, odrzucone = skanuj_olx_api_clean(fraza_uproszczona, fraza_clean, cena_min, cena_max, tekst_statusu)

    total_time_formatted = formatuj_czas(time.time() - start_time)
    oferty.sort(key=lambda x: x['cena_val'])
    pasek_postepu.progress(100)

    return oferty, odrzucone, total_time_formatted

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

    input_data = st.text_input("Szukany przedmiot / Link:", placeholder="np. opel astra k lub Rower Kross")

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
                st.error("Nie znaleziono pasujących ofert na OLX. Upewnij się, że nazwa przedmiotu nie posiada błędów pisowni lub sprawdź inne kategorie.")
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
                        
                        tags_html = f"<span class='pill-tag pill-delivery'>{o['dostawa']}</span>"
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

    if st.session_state["zalogowany_admin"]:
        with st.expander("➕ Dodaj nową wersję Patch Notes (Tryb Admina)"):
            with st.form("formularz_patch_note", clear_on_submit=True):
                wersja_in = st.text_input("Numer wersji:", placeholder="np. v3.2.0")
                opis_in = st.text_input("Krótki opis wydania:", placeholder="np. Poprawa wydajności")
                zmiany_raw = st.text_area("Lista zmian (każda w nowej linii):", placeholder="Wprowadzono zmianę X")
                wazna_in = st.checkbox("Ważna wersja (Major Release)", value=True)
                
                if st.form_submit_button("Opublikuj Patch Note"):
                    if wersja_in and opis_in and zmiany_raw:
                        lista_z = [z.strip() for z in zmiany_raw.split("\n") if z.strip()]
                        nowy_entry = {
                            "wersja": wersja_in.strip(),
                            "data": datetime.now().strftime("%d %B %Y"),
                            "wazna": wazna_in,
                            "opis": opis_in.strip(),
                            "zmiany": lista_z
                        }
                        st.session_state["historia_zmian"].insert(0, nowy_entry)
                        zapisz_patch_notes_do_pliku()
                        st.success(f"Dodano wpis dla {wersja_in}!")
                        st.rerun()
                    else:
                        st.error("Proszę wypełnić wszystkie pola.")

    tylko_wazne = st.checkbox("Pokaż tylko najważniejsze wersje (Major Releases)", value=False)

    for item in st.session_state["historia_zmian"]:
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
