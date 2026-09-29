import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import urllib.parse
import re
import time
import json

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="Inteligentny Agregator Ofert OLX",
    page_icon="⚡",
    layout="wide"
)

# --- STYLE CSS (PRO STYLIZACJA KART I ODZNAK) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"], .main {
        background-color: #0b0f19 !important;
        color: #f8fafc !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }

    section[data-testid="stSidebar"] {
        background-color: #111827 !important;
        border-right: 1px solid #334155 !important;
    }

    /* Karta Oferty */
    .offer-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 20px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 100%;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .offer-card:hover {
        transform: translateY(-3px);
        border-color: #00f2fe;
    }
    .offer-img {
        width: 100%;
        height: 190px;
        object-fit: cover;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    .offer-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 8px;
        line-height: 1.3;
        height: 2.6em;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
    }
    .offer-price {
        font-size: 1.35rem;
        font-weight: 800;
        color: #10b981;
        margin-bottom: 10px;
    }

    /* Badges / Odznaki */
    .badge {
        display: inline-block;
        font-size: 0.78rem;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 6px;
        margin-right: 6px;
        margin-bottom: 8px;
    }
    .deal-super { background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }
    .deal-average { background: rgba(59, 130, 246, 0.2); color: #3b82f6; border: 1px solid #3b82f6; }
    .deal-high { background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid #ef4444; }
    .deal-neutral { background: rgba(148, 163, 184, 0.2); color: #94a3b8; border: 1px solid #94a3b8; }

    .scam-safe { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .scam-warn { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.4); }

    /* Nagłówek i formularz */
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .hero-sub {
        color: #94a3b8;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- LISTA PODEJRZANYCH SŁÓW (SCAM CHECKER) ---
SUSPICIOUS_WORDS = [
    'kurier podejmie', 'przez whatsapp', 'whatsapp', 'płatność z góry',
    'wyjechałem za granicę', 'wyjechałam za granicę', 'przesyłka kurierska inpost',
    'odbierze kurier', 'płatność zaliczkowa', 'kod blik', 'link do płatności',
    'rezerwacja po wpłacie', 'płatność na konto', 'zaliczka'
]

# --- SLUGIFIKACJA MIAST DLA OLX ---
CITY_MAPPING = {
    'krakowie': 'krakow', 'kraków': 'krakow', 'krakow': 'krakow',
    'warszawie': 'warszawa', 'warszawa': 'warszawa',
    'wrocławiu': 'wroclaw', 'wrocław': 'wroclaw', 'wroclaw': 'wroclaw',
    'poznaniu': 'poznan', 'poznań': 'poznan', 'poznan': 'poznan',
    'gdańsku': 'gdansk', 'gdańsk': 'gdansk', 'gdansk': 'gdansk',
    'katowicach': 'katowice', 'katowice': 'katowice',
    'łodzi': 'lodz', 'łódź': 'lodz', 'lodz': 'lodz',
    'szczecinie': 'szczecin', 'szczecin': 'szczecin',
    'lublinie': 'lublin', 'lublin': 'lublin',
    'gdyni': 'gdynia', 'gdynia': 'gdynia',
    'bydgoszczy': 'bydgoszcz', 'bydgoszcz': 'bydgoszcz',
    'tychach': 'tychy', 'tychy': 'tychy'
}

def normalize_city(city_text):
    if not city_text:
        return None
    c = city_text.lower().strip()
    for key, val in CITY_MAPPING.items():
        if key in c:
            return val
    c = re.sub(r'[ąá]', 'a', c)
    c = re.sub(r'[ćc]', 'c', c)
    c = re.sub(r'[ęe]', 'e', c)
    c = re.sub(r'[łl]', 'l', c)
    c = re.sub(r'[ńn]', 'n', c)
    c = re.sub(r'[óo]', 'o', c)
    c = re.sub(r'[śs]', 's', c)
    c = re.sub(r'[źżz]', 'z', c)
    return re.sub(r'(ie|iu|ach|e)$', '', c)

# --- 1. WYSZUKIWARKA NATURALNA (PSEUDO-AI PARSER) ---
def parse_natural_query(text):
    text_clean = text.lower().strip()
    
    # Wyciąganie maksymalnej ceny
    max_price = None
    max_match = re.search(r'(?:do|max|maksymalnie|poniżej|do kwoty|za)\s*(\d[\d\s]*)\s*(?:zł|pln)?', text_clean)
    if max_match:
        try:
            max_price = float(re.sub(r'[^\d]', '', max_match.group(1)))
        except ValueError:
            pass

    # Wyciąganie minimalnej ceny
    min_price = None
    min_match = re.search(r'(?:od|min|minimalnie|powyżej)\s*(\d[\d\s]*)\s*(?:zł|pln)?', text_clean)
    if min_match:
        try:
            min_price = float(re.sub(r'[^\d]', '', min_match.group(1)))
        except ValueError:
            pass

    # Wyciąganie lokalizacji
    location = None
    loc_match = re.search(r'\b(?:w|z|okolice)\s+([a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ\-]+)', text_clean)
    if loc_match:
        location = loc_match.group(1)

    # Czyszczenie tekstu z wykrytych fraz
    words_to_remove = []
    if max_match:
        words_to_remove.append(max_match.group(0))
    if min_match:
        words_to_remove.append(min_match.group(0))
    if loc_match:
        words_to_remove.append(loc_match.group(0))

    stopwords = ['szukam', 'kupię', 'potrzebuję', 'okazja', 'tanio', 'pilnie', 'chcę', 'kupic', 'poszukuję']
    
    cleaned_phrase = text_clean
    for w in words_to_remove:
        cleaned_phrase = cleaned_phrase.replace(w, ' ')
    for sw in stopwords:
        cleaned_phrase = re.sub(r'\b' + sw + r'\b', ' ', cleaned_phrase)
        
    cleaned_phrase = re.sub(r'\s+', ' ', cleaned_phrase).strip()

    return {
        'phrase': cleaned_phrase if cleaned_phrase else text_clean,
        'max_price': max_price,
        'min_price': min_price,
        'location': location
    }

# --- PARSER CENY ---
def parse_price_val(price_str):
    if not price_str:
        return 0.0
    cleaned = re.sub(r'[^\d,.]', '', str(price_str)).replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

# --- 2. SCRAPER BEZPOŚREDNI OLX (CLOUDSCRAPER + BEAUTIFULSOUP) ---
def fetch_olx_deals(parsed_data):
    phrase = parsed_data['phrase']
    location = parsed_data['location']
    max_price = parsed_data['max_price']
    min_price = parsed_data['min_price']

    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )

    phrase_slug = urllib.parse.quote(re.sub(r'\s+', '-', phrase.strip()))
    city_slug = normalize_city(location) if location else None

    if city_slug:
        base_url = f"https://www.olx.pl/{city_slug}/q-{phrase_slug}/"
    else:
        base_url = f"https://www.olx.pl/oferty/q-{phrase_slug}/"

    params = ["search%5Border%5D=filter_float_price%3Aasc"]
    if max_price:
        params.append(f"search%5Bfilter_float_price%3Ato%5D={int(max_price)}")
    if min_price:
        params.append(f"search%5Bfilter_float_price%3Afrom%5D={int(min_price)}")

    url = f"{base_url}?{'&'.join(params)}"

    try:
        response = scraper.get(url, timeout=12)
        if response.status_code == 403 or "cloudflare" in response.text.lower():
            return None, "OLX tymczasowo zablokował automatyczny scraping. Odczekaj chwilę i spróbuj ponownie."
        if response.status_code != 200:
            return None, f"Nie udało się pobrać danych (HTTP {response.status_code})."
    except Exception as e:
        return None, f"Błąd połączenia z serwerem OLX: {str(e)}"

    soup = BeautifulSoup(response.text, 'html.parser')
    offers = []

    # 1. Odczyt z natywnego obiektu JSON __NEXT_DATA__
    next_data = soup.find('script', id='__NEXT_DATA__')
    if next_data and next_data.string:
        try:
            data = json.loads(next_data.string)
            page_props = data.get('props', {}).get('pageProps', {})
            ads_list = (
                page_props.get('data', {}).get('ads', []) or
                page_props.get('ads', []) or
                page_props.get('listing', {}).get('ads', [])
            )

            for ad in ads_list:
                if not isinstance(ad, dict):
                    continue
                title = ad.get('title', '')
                url_ad = ad.get('url', '')
                if not title or not url_ad:
                    continue

                if not url_ad.startswith('http'):
                    url_ad = "https://www.olx.pl" + url_ad

                price_obj = ad.get('price', {})
                price_val = 0.0
                price_str = "Zapytaj o cenę"
                if isinstance(price_obj, dict):
                    price_val = float(price_obj.get('value', 0.0) or 0.0)
                    price_str = price_obj.get('displayValue', f"{price_val:.0f} zł")

                photos = ad.get('photos', [])
                img_url = "https://via.placeholder.com/300x200?text=Brak+Zdj%C4%99cia"
                if photos and isinstance(photos, list):
                    first_photo = photos[0]
                    if isinstance(first_photo, dict):
                        img_url = first_photo.get('link', '').replace('{width}', '400').replace('{height}', '300')

                desc_raw = ad.get('description', '') or ''
                desc_text = BeautifulSoup(desc_raw, 'html.parser').get_text(separator=' ') if desc_raw else title

                loc_name = ad.get('location', {}).get('city', {}).get('name', location if location else 'Polska')

                offers.append({
                    'title': title,
                    'price': price_val,
                    'price_str': price_str,
                    'url': url_ad,
                    'img_url': img_url,
                    'description': desc_text,
                    'location': loc_name
                })
        except Exception:
            pass

    # 2. Rezerwowy parser kart HTML
    if not offers:
        cards = soup.select('div[data-cy="l-card"], div[data-testid="l-card"], [data-testid="ad-card"]')
        for card in cards:
            t_elem = card.find(['h6', 'h4', 'h3']) or card.find(attrs={'data-testid': 'ad-title'})
            p_elem = card.find('p', {'data-testid': 'ad-price'}) or card.find(attrs={'data-cy': 'ad-price'})
            l_elem = card.find('a', href=True)
            img_elem = card.find('img')

            if t_elem and l_elem:
                title = t_elem.get_text().strip()
                url_ad = l_elem['href']
                if not url_ad.startswith('http'):
                    url_ad = "https://www.olx.pl" + url_ad

                price_str = p_elem.get_text().strip() if p_elem else "0 zł"
                price_val = parse_price_val(price_str)

                img_url = "https://via.placeholder.com/300x200?text=Brak+Zdj%C4%99cia"
                if img_elem:
                    img_url = img_elem.get('src') or img_elem.get('data-src') or img_url

                offers.append({
                    'title': title,
                    'price': price_val,
                    'price_str': price_str,
                    'url': url_ad,
                    'img_url': img_url,
                    'description': title,
                    'location': location if location else 'Polska'
                })

    return offers, None

# --- 3. DARMOWY WERYFIKATOR OSZUSTW I OCENA OPŁACALNOŚCI (DEAL SCORING) ---
def check_scam(title, description):
    text = f"{title} {description}".lower()
    triggered = [w for w in SUSPICIOUS_WORDS if w in text]
    if triggered:
        return False, f"🔴 Uwaga! Podejrzane słowa: {', '.join(triggered)}"
    return True, "🟢 Bezpieczne"

def process_and_score_deals(offers_list):
    if not offers_list:
        return pd.DataFrame()

    df = pd.DataFrame(offers_list)

    # Obliczanie mediany cenowej z odrzuceniem cen <= 0
    valid_prices = df[df['price'] > 0]['price']
    
    if len(valid_prices) > 0:
        median_price = valid_prices.median()
    else:
        median_price = 0.0

    deal_scores = []
    deal_classes = []
    scam_statuses = []
    scam_msgs = []

    for _, row in df.iterrows():
        p = row['price']
        if p <= 0 or median_price <= 0:
            deal_scores.append('ℹ️ Nieokreślona')
            deal_classes.append('deal-neutral')
        elif p <= median_price * 0.85:
            deal_scores.append('🔥 Super okazja')
            deal_classes.append('deal-super')
        elif p >= median_price * 1.15:
            deal_scores.append('🚩 Zawyżona')
            deal_classes.append('deal-high')
        else:
            deal_scores.append('⚖️ Przeciętna')
            deal_classes.append('deal-average')

        is_safe, msg = check_scam(row['title'], row['description'])
        scam_statuses.append(is_safe)
        scam_msgs.append(msg)

    df['deal_score'] = deal_scores
    df['deal_class'] = deal_classes
    df['scam_safe'] = scam_statuses
    df['scam_msg'] = scam_msgs
    df['median_ref'] = median_price

    return df

# --- INTERFEJS APLIKACJI STREAMLIT ---

st.markdown('<div class="hero-title">⚡ Inteligentny Agregator Ofert OLX</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Darmowa analityka cenowa w czasie rzeczywistym z detekcją okazji i weryfikacją oszustw.</div>', unsafe_allow_html=True)

# GŁÓWNE WEJŚCIE NATURALNE
query_input = st.text_input(
    "💬 Wpisz zapytanie w języku naturalnym:",
    placeholder="np. Szukam roweru szosowego do 3000 zł w Krakowie",
    key="natural_query_input"
)

if query_input.strip():
    parsed = parse_natural_query(query_input)

    max_p_str = f"{int(parsed['max_price'])} zł" if parsed['max_price'] else "Brak limitu"
    min_p_str = f"{int(parsed['min_price'])} zł" if parsed['min_price'] else "Brak"
    city_str = parsed['location'].capitalize() if parsed['location'] else "Cała Polska"

    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1:
        st.info(f"🔎 **Fraza:** {parsed['phrase']}")
    with col_p2:
        st.info(f"💰 **Cena max:** {max_p_str}")
    with col_p3:
        st.info(f"🏷️ **Cena min:** {min_p_str}")
    with col_p4:
        st.info(f"📍 **Miasto:** {city_str}")

    if st.button("🚀 Szukaj Najlepszych Okazji", type="primary", use_container_width=True):
        with st.spinner("⚡ Skanuję oferty i obliczam medianę cenową..."):
            raw_offers, error_msg = fetch_olx_deals(parsed)

            if error_msg:
                st.error(f"⚠️ {error_msg}")
            elif not raw_offers:
                st.warning("Nie znaleziono ofert spełniających podane kryteria.")
            else:
                df = process_and_score_deals(raw_offers)

                st.success(f"Przeanalizowano {len(df)} ofert. Mediana cenowa wynosi: **{df['median_ref'].iloc[0]:.2f} zł**")

                top_deal_count = len(df[df['deal_class'] == 'deal-super'])
                scam_warn_count = len(df[df['scam_safe'] == False])

                m1, m2, m3 = st.columns(3)
                m1.metric("Znaleziono super okazji", f"🔥 {top_deal_count}")
                m2.metric("Mediana cenowa rynku", f"{df['median_ref'].iloc[0]:.0f} zł")
                m3.metric("Podejrzane ogłoszenia", f"⚠️ {scam_warn_count}")

                st.markdown("---")

                COLS_PER_ROW = 3
                cols = st.columns(COLS_PER_ROW)

                for idx, row in df.iterrows():
                    col = cols[idx % COLS_PER_ROW]
                    scam_class = "scam-safe" if row['scam_safe'] else "scam-warn"

                    card_html = f"""
                    <div class="offer-card">
                        <div>
                            <img src="{row['img_url']}" class="offer-img" alt="Miniaturka"/>
                            <div class="offer-title">{row['title']}</div>
                            <div class="offer-price">{row['price_str']}</div>
                            <div>
                                <span class="badge {row['deal_class']}">{row['deal_score']}</span>
                                <span class="badge {scam_class}">{row['scam_msg']}</span>
                            </div>
                        </div>
                    </div>
                    """
                    with col:
                        st.markdown(card_html, unsafe_allow_html=True)
                        st.link_button("Zobacz ofertę ↗", row['url'], use_container_width=True)
                        st.markdown("<br>", unsafe_allow_html=True)

else:
    st.info("👈 Wpisz powyżej dowolne zapytanie, np. *'Kupię iPhone 13 do 2500 zł w Warszawie'*, aby rozpoczęć darmową analitykę.")
