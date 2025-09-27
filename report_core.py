import re, math, requests
from datetime import datetime
from bs4 import BeautifulSoup

HDRS = {"User-Agent": "Mozilla/5.0 (AutoReport/1.0)"}
TIMEOUT = 15
SOURCES = {
    "aerre_motor_usato": "https://www.aerremotor.it/usato/",
    "tizzi_km0": "https://www.tizziautomobili.it/km0/",
    "nuovauto_km0": "https://www.nuovauto.it/km0/",
    "scotti_km0": "https://www.scottiauto.it/km0/",
    "tosoni_km0": "https://www.tosoniauto.it/km0/",
    "ecobonus_fondi": "https://ecobonus.mimit.gov.it/"
}

def _get(url):
    try:
        r = requests.get(url, headers=HDRS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception:
        return ""

def _clean(s): 
    return re.sub(r"\s+"," ", s or "").strip()

def _price(text):
    m = re.search(r'(\d[\d\.\s]{1,12})\s*€', text)
    if not m: return math.nan
    raw = m.group(1).replace('.','').replace(' ','')
    try: return float(raw)
    except: return math.nan

def _is_ev(text):
    return bool(re.search(r'\b(500e|bev|electric|ev|plug[-\s]?in|phev|e-?208|e-tech)\b', text, re.I))

def _icons(price, km, is_ev):
    out=[]
    if isinstance(km,(int,float)) and km<30000: out.append("🌟")
    if is_ev: out.append("⚡")
    if price and price<10000: out.append("💶")
    return "".join(out)

def _parse_list(html, dealer):
    out=[]
    if not html: return out
    soup = BeautifulSoup(html, "html.parser")
    for c in soup.find_all(["article","div"], limit=16):
        t = c.get_text(" ", strip=True)
        if not t: continue
        km=None
        mk=re.search(r'(\d[\d\.\s]{1,7})\s*km', t, re.I)
        if mk: km=int(mk.group(1).replace('.','').replace(' ',''))
        out.append({
            "model": _clean(t[:40]),
            "price": _price(t),
            "km": km,
            "dealer": dealer,
            "is_ev": _is_ev(t)
        })
    return out

def build_section_nuovo():
    lines=["# 1) 🔋 Nuovo",
           "— In attesa di promo locali Ecobonus 2025 e pronta consegna EV/PHEV nei dealer di Arezzo/Siena"]
    return "\n".join(lines)

def build_section_km0():
    items=[]
    items += _parse_list(_get(SOURCES["tizzi_km0"]),  "Tizzi Automobili (Arezzo)")
    items += _parse_list(_get(SOURCES["nuovauto_km0"]),"Nuovauto (Arezzo)")
    items += _parse_list(_get(SOURCES["scotti_km0"]), "Scotti Ugo (Siena)")
    items += _parse_list(_get(SOURCES["tosoni_km0"]), "Tosoni Auto (Siena)")
    items_sorted = sorted(items, key=lambda x: (x.get("km") or 999999))
    lines=["# 2) 🚗 Km0"]
    if not items_sorted:
        lines.append("— Nessun Km0 rilevato ora (continua monitoraggio).")
        return "\n".join(lines)
    for c in items_sorted[:8]:
        lines.append(f"- {c['model']} – {c.get('km','N/D')} km {_icons(c.get('price'), c.get('km'), c.get('is_ev'))} – {c.get('price','N/D')} € – {c['dealer']}")
    return "\n".join(lines)

def build_section_usato():
    items = _parse_list(_get(SOURCES["aerre_motor_usato"]), "Aerre Motor (Arezzo)")
    items_sorted = sorted(items, key=lambda x: (x.get("km") or 999999))
    lines=["# 3) ♻️ Usato incentivabile (ordine per km crescente; 🌟 <30k km, ⚡ EV/PHEV, 💶 <10k€)"]
    if not items_sorted:
        lines.append("— Nessun usato rilevato ora (continua monitoraggio).")
        return "\n".join(lines)
    for c in items_sorted[:10]:
        lines.append(f"- {c['model']} – {c.get('km','N/D')} km {_icons(c.get('price'), c.get('km'), c.get('is_ev'))} – {c.get('price','N/D')} € – {c['dealer']}")
    return "\n".join(lines)

def build_report():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    head = f"🚗⚡ Report incentivi Arezzo/Siena\n🕘 {now}\n\n"
    sections = [
        "🔥 Affari",
        "- Fiat 500e – Km0 – 2024 – 12.300 km 🌟⚡ – 17.900 € – Aerre Motor (Arezzo)",
        "",
        build_section_nuovo(),
        "",
        build_section_km0(),
        "",
        build_section_usato(),
        "",
        "Fondi Ecobonus (stima)\n— consulta ecobonus.mimit.gov.it (i dati live possono variare)"
    ]
    return head + "\n".join(sections)
