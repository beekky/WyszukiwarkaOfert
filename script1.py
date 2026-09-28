import subprocess
import sys

# Automatyczna instalacja przeglądarki Playwright na serwerze chmurowym
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

st.set_page_config(page_title="Wyszukiwarka Ofert OLX", layout="wide")

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
    'tracker', 'rubiconproject', 'pubmatic', 'openx', 'adnxs', 'smartadserver',
    'casalemedia', 'yieldmo', 'taboola', 'outbrain', 'gemius', 'adform', 'quantserve'
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


def wyciagnij_nazwe_z_linku(url_lub_tekst):
    """Pobiera tytuł ze strony sklepu, jeśli podano link."""
    if url_lub_tekst.startswith("http://") or url_lub_tekst.startswith("https://"):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url_lub_tekst, headers=headers, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')

            h1 = soup.find('h1')
            title = h1.text.strip() if h1 else soup.title.text.strip()

            czysta_nazwa = re.split(r'[|\-–]', title)[0].strip()
            slowa = czysta_nazwa.split()
            if len(slowa) > 6:
                czysta_nazwa = " ".join(slowa[:6])
            return czysta_nazwa
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
    if any(k in tekst_lower for k in ['faktura', 'paragon', 'dowód zakupu', 'dowod zakupu']):
        cechy.append("🧾 Paragon / Faktura")
    if any(k in tekst_lower for k in ['komplet', 'pełen zestaw', 'pudełko', 'oryginalne opakowanie', 'zestaw']):
        cechy.append("📦 Pełen zestaw / Pudełko")

    czysty_tekst = tekst_opisu.strip()
    if len(czysty_tekst) > 800:
        skrot_opisu = czysty_tekst[:800] + "\n\n[... ciąg dalszy w ogłoszeniu na OLX]"
    else:
        skrot_opisu = czysty_tekst

    return czy_uszkodzony, ostrzezenie, skrot_opisu, cechy


def wykryj_forme_dostawy(card, tresc_opisu):
    card_html = card.inner_html().lower() if card else ""

    ma_przesylke_olx = "przesyłka olx" in card_html or "kup z przesyłką" in card_html or card.query_selector(
        '[data-testid="delivery-icon"]') is not None

    tekst_lower = tresc_opisu.lower() if tresc_opisu else ""

    ma_odbior_osobisty = any(kw in tekst_lower for kw in
                             ['odbiór osobisty', 'odbior osobisty', 'tylko odbiór', 'tylko odbior', 'odbiór na miejscu',
                              'odbior na miejscu'])
    ma_inna_wysylke = any(
        kw in tekst_lower for kw in ['wysyłka', 'wysylka', 'paczkomat', 'kurier', 'poczta', 'wysyłam', 'wysylam'])

    formy = []
    if ma_przesylke_olx:
        formy.append("📦 Przesyłka OLX")
    elif ma_inna_wysylke:
        formy.append("✉️ Wysyłka prywatna (bez OLX)")

    if ma_odbior_osobisty:
        formy.append("🤝 Odbiór osobisty")

    if not formy:
        formy.append("ℹ️ Brak szczegółów dostawy")

    return " | ".join(formy)


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

    glowne_klucze = [s for s in slowa_zapytania if len(s) > 3 and not s.isdigit() and s not in GENERYCZNE_SLOWA]
    if glowne_klucze:
        if not any(k in pelny_tekst for k in glowne_klucze):
            return False

    trafione = [s for s in slowa_zapytania if s in pelny_tekst]

    if len(slowa_zapytania) >= 2:
        return (len(trafione) / len(slowa_zapytania)) >= 0.5
    return len(trafione) >= 1


def zablokuj_zbedne_zasoby_i_reklamy(route):
    url = route.request.url.lower()
    res_type = route.request.resource_type

    if res_type in ["image", "media", "font"]:
        route.abort()
        return

    if any(domena in url for domena in DOMENY_REKLAMOWE):
        route.abort()
        return

    route.continue_()


def formatuj_czas(sekundy):
    s = int(sekundy)
    m, s = divmod(s, 60)
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def pobierz_oferty_olx(fraza, kategorie_slugs, stany_olx, cena_min, cena_max, pasek_postepu, tekst_statusu):
    oferty = []
    odrzucone_list = []
    unikalne_linki = set()

    MAX_OFERT = 100
    MAX_STRON_PER_KAT = 30

    fraza_clean = re.sub(r'\s+', ' ', fraza.strip())
    olx_query = re.sub(r'[^a-zA-Z0-9\s-]', '', fraza_clean).strip().replace(" ", "-")

    olx_map = {"Nowe": "new", "Używane": "used", "Uszkodzone": "damaged"}
    olx_state_param = "".join(
        [f"&search%5Bfilter_enum_state%5D%5B{i}%5D={olx_map[s]}" for i, s in enumerate(stany_olx) if s in olx_map])
    olx_price_param = ""
    if cena_min > 0:
        olx_price_param += f"&search%5Bfilter_float_price%3Afrom%5D={cena_min}"
    if cena_max > 0:
        olx_price_param += f"&search%5Bfilter_float_price%3Ato%5D={cena_max}"

    tekst_statusu.write("⚡ Uruchamiam silnik w tle z blokadą reklam...")
    pasek_postepu.progress(2)
    start_time = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
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
            if len(oferty) >= MAX_OFERT:
                break

            for strona in range(1, MAX_STRON_PER_KAT + 1):
                if len(oferty) >= MAX_OFERT:
                    break

                elapsed_sec = time.time() - start_time
                tekst_statusu.write(
                    f"⚡ Kategoria {kat_idx}/{total_kategorii} | Skanowanie strony {strona} (znaleziono trafnych: {len(oferty)}) | "
                    f"⏱️ Czas pracy: {formatuj_czas(elapsed_sec)}"
                )

                olx_url = f"https://www.olx.pl/{kategoria_slug}/q-{olx_query}/?page={strona}&search%5Border%5D=filter_float_price%3Aasc{olx_state_param}{olx_price_param}"

                try:
                    page.goto(olx_url, wait_until="commit", timeout=12000)
                    page.wait_for_selector('div[data-cy="l-card"]', timeout=6000)
                except Exception:
                    pass

                if strona > 1 and f"page={strona}" not in page.url and f"page/{strona}" not in page.url:
                    break

                try:
                    page.click('button[id="onetrust-accept-btn-handler"]', timeout=800)
                except Exception:
                    pass

                cards = page.query_selector_all('div[data-cy="l-card"]')
                if not cards:
                    break

                for card in cards:
                    if len(oferty) >= MAX_OFERT:
                        break

                    title_elem = card.query_selector('h6, h4, [data-testid="ad-title"]')
                    price_elem = card.query_selector('p[data-testid="ad-price"]')
                    link_elem = card.query_selector('a')

                    if title_elem and price_elem and link_elem:
                        tytul = title_elem.inner_text().strip()
                        cena_str = price_elem.inner_text().strip()
                        cena_num = parse_price(cena_str)
                        link = link_elem.get_attribute('href') or ""
                        if link and not link.startswith('http'):
                            link = "https://www.olx.pl" + link

                        if link in unikalne_linki:
                            continue

                        if cena_min > 0 and cena_num < cena_min:
                            continue
                        if cena_max > 0 and cena_num > cena_max:
                            continue

                        tytul_lower = tytul.lower()
                        if any(smiec in tytul_lower and smiec not in fraza_clean.lower() for smiec in SMIECI_BRANŻOWE):
                            odrzucone_list.append(f"{tytul} ({cena_str})")
                            continue

                        tresc_opisu = ""
                        try:
                            detail_page = context.new_page()
                            try:
                                detail_page.goto(link, wait_until="commit", timeout=8000)
                                detail_page.wait_for_selector('div[data-cy="ad_description"], div[class*="css-1o9z2s"]',
                                                              timeout=4000)
                            except Exception:
                                pass

                            desc_elem = detail_page.query_selector(
                                'div[data-cy="ad_description"], div[class*="css-1o9z2s"]')
                            if desc_elem:
                                tresc_opisu = desc_elem.inner_text()
                            detail_page.close()
                        except Exception:
                            pass

                        if not czy_trafna_oferta(fraza_clean, tytul, link, tresc_opisu):
                            odrzucone_list.append(f"{tytul} ({cena_str})")
                            continue

                        czy_uszkodzony, ostrzezenie_opis, skrot_opisu, cechy_z_opisu = analizuj_i_stworz_skrot_opisu(
                            tresc_opisu)
                        dostawa_info = wykryj_forme_dostawy(card, tresc_opisu)

                        unikalne_linki.add(link)
                        oferty.append({
                            "źródło": "OLX",
                            "tytuł": tytul,
                            "cena_str": cena_str,
                            "cena_val": cena_num,
                            "link": link,
                            "ostrzezenie": ostrzezenie_opis,
                            "czy_uszkodzony": czy_uszkodzony,
                            "skrot_opisu": skrot_opisu,
                            "cechy": cechy_z_opisu,
                            "dostawa": dostawa_info
                        })

                pasek_postepu.progress(min(98, int((kat_idx / total_kategorii) * 100)))

        browser.close()

    total_time_formatted = formatuj_czas(time.time() - start_time)
    oferty.sort(key=lambda x: x['cena_val'])
    pasek_postepu.progress(100)
    return oferty, odrzucone_list, total_time_formatted


# --- INTERFEJS UŻYTKOWNIKA ---

st.title("🔍 Porównywarka Ofert OLX")
st.write("Wklej link ze sklepu lub wpisz nazwę przedmiotu ręcznie.")

input_data = st.text_input("Link lub nazwa przedmiotu:", placeholder="np. https://... lub Rower Kross Hexagon 3.0")

col_cat, col_f1, col_c1, col_c2 = st.columns([2.5, 2, 1, 1])

with col_cat:
    wybrane_kategorie_nazwy = st.multiselect(
        "Kategorie OLX:",
        list(KATEGORIE_OLX.keys()),
        default=["Wszystkie kategorie"]
    )
with col_f1:
    stany_olx = st.multiselect("Stan przedmiotu:", ["Nowe", "Używane", "Uszkodzone"], default=["Nowe", "Używane"])
with col_c1:
    cena_min = st.number_input("Cena minimalna (PLN):", min_value=0, value=0, step=50,
                               help="Odrzuca drobne akcesoria i części")
with col_c2:
    cena_max = st.number_input("Cena maksymalna (PLN, 0 = brak):", min_value=0, value=0, step=50)

if st.button("Szukaj najtańszych ofert na OLX"):
    if not input_data.strip():
        st.warning("Proszę wpisać frazę lub wkleić link.")
    elif not wybrane_kategorie_nazwy:
        st.warning("Proszę wybrać przynajmniej jedną kategorię.")
    else:
        szukana_fraza = wyciagnij_nazwe_z_linku(input_data)

        if "Wszystkie kategorie" in wybrane_kategorie_nazwy:
            kategorie_slugs = ["oferty"]
            opis_kat = "Wszystkie kategorie"
        else:
            kategorie_slugs = [KATEGORIE_OLX[k] for k in wybrane_kategorie_nazwy]
            opis_kat = ", ".join(wybrane_kategorie_nazwy)

        st.info(
            f"Przeszukuję kategorie (**{opis_kat}**) na OLX dla frazy: **{szukana_fraza}** (Zakres cen: {cena_min} zł - {cena_max if cena_max > 0 else 'brak limitu'} zł)")

        pasek = st.progress(0)
        status = st.empty()

        wyniki, odrzucone, czas_pracy = pobierz_oferty_olx(
            szukana_fraza, kategorie_slugs, stany_olx, cena_min, cena_max,
            pasek, status
        )

        pasek.empty()
        status.empty()

        if not wyniki:
            st.error("Nie znaleziono pasujących ofert w podanym zakresie cenowym.")
        else:
            st.success(
                f"Znaleziono {len(wyniki)} trafnych ofert na OLX w czasie {czas_pracy}! Posortowano od najniższej ceny:")

            for idx, o in enumerate(wyniki, start=1):
                col1, col2, col3, col4 = st.columns([1, 4.5, 2, 2])
                with col1:
                    st.markdown(f"### #{idx}")
                    st.caption(f"**{o['źródło']}**")
                with col2:
                    st.write(f"**{o['tytuł']}**")

                    st.caption(f"🚚 **Dostawa:** {o['dostawa']}")

                    if o['cechy']:
                        st.markdown(" ".join([f"`{c}`" for c in o['cechy']]))

                    with st.expander("📄 Szczegółowy podgląd opisu"):
                        st.text(o['skrot_opisu'])

                    if o['ostrzezenie']:
                        st.error(o['ostrzezenie'])

                with col3:
                    st.markdown(f"💰 **{o['cena_str']}**")
                with col4:
                    st.link_button("Zobacz ofertę", o['link'])
                st.divider()

        if odrzucone:
            with st.expander(f"🗑️ Zobacz odrzucone oferty ({len(odrzucone)})"):
                st.caption(
                    "Poniższe oferty zostały zignorowane jako niezgodne z szukanym przedmiotem lub poniżej ceny min:")
                for item in odrzucone[:50]:
                    st.text(item)