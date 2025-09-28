# report_core.py
import re, math, json, os, hashlib, requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

HDRS = {"User-Agent": "Mozilla/5.0 (AutoReport/2.0)"}
TIMEOUT = 15
DATA_DIR = "/app/data"
os.makedirs(DATA_DIR, exist_ok=True)
STATE_PATH = os.path.join(DATA_DIR, "state.json")     # fondi/nuove promo/occasioni (ultimo invio)
USERS_PATH = os.path.join(DATA_DIR, "users.json")     # preferenze utenti e preferiti
HIST_PATH  = os.path.join(DATA_DIR, "history.jsonl")  # storico prezzi (append)

SOURCES = {
    "aerre_motor_usato": "https://www.aerremotor.it/usato/",
    "tizzi_km0": "https://www.tizziautomobili.it/km0/",
    "nuovauto_km0": "https://www.nuovauto.it/km0/",
    "scotti_km0": "https://www.scottiauto.it/km0/",
    "tosoni_km0": "https://www.tosoniauto.it/km0/",
    "ecobonus_fondi": "https://ecobonus.mimit.gov.it/",
}

BRAND_LIST = ["peugeot","opel","kia","alfa","alfa romeo","volkswagen","vw","fiat","renault"]

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

def _km(text):
    mk = re.search(r'(\d[\d\.\s]{1,7})\s*km', text, re.I)
    if not mk: return None
    return int(mk.group(1).replace('.','').replace(' ',''))

def _is_ev(text):
    return bool(re.search(r'\b(500e|bev|electric|ev|e-tech|e-?208|mokka-?e|id\.\d)\b', text, re.I))

def _is_phev(text):
    return bool(re.search(r'\b(phev|plug[-\s]?in|e[-\s]?hybrid|hybrid4|recharge)\b', text, re.I))

def _brand(text):
    t = text.lower()
    for b in BRAND_LIST:
        if b in t: 
            return "volkswagen" if b=="vw" else b
    return None

def _icons(price, km, is_ev, is_phev):
    out=[]
    if isinstance(km,(int,float)) and km<30000: out.append("🌟")
    if is_ev or is_phev: out.append("⚡")
    if price and price<10000: out.append("💶")
    return "".join(out)

def _img_hint(tag):
    # best-effort: prova a pescare la prima immagine sensata
    img = tag.find("img")
    if img and img.get("src"): 
        src = img["src"]
        if src.startswith("//"): src = "https:" + src
        return src
    return None

def _hash_id(*parts):
    h = hashlib.sha1(("||".join([str(p) for p in parts])).encode("utf-8")).hexdigest()[:10]
    return h

def _parse_list(html, dealer):
    out=[]
    if not html: return out
    soup = BeautifulSoup(html, "html.parser")
    for c in soup.find_all(["article","div","li"], limit=30):
        t = c.get_text(" ", strip=True)
        if not t or len(t) < 15: 
            continue
        price=_price(t)
        km=_km(t)
        br=_brand(t)
        ev=_is_ev(t)
        phev=_is_phev(t)
        title = _clean(t[:80])
        image = _img_hint(c)
        # id univoco
        uid=_hash_id(title, dealer, price)
        out.append({
            "id": uid,
            "title": title,
            "brand": br,
            "price": price if not math.isnan(price) else None,
            "km": km,
            "dealer": dealer,
            "is_ev": ev,
            "is_phev": phev,
            "image": image
        })
    return out

def _save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _append_history(items):
    ts = datetime.utcnow().isoformat()
    with open(HIST_PATH, "a", encoding="utf-8") as f:
        for it in items:
            rec = {"ts": ts, "id": it["id"], "title": it["title"], "dealer": it["dealer"], "price": it["price"], "km": it["km"]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ---------- sezioni principali ----------
def build_section_nuovo():
    lines=["# 1) 🔋 Nuovo",
           "— In attesa di promo locali Ecobonus e pronta consegna EV/PHEV nei dealer di Arezzo/Siena"]
    return "\n".join(lines)

def build_section_km0():
    items=[]
    items += _parse_list(_get(SOURCES["tizzi_km0"]),  "Tizzi Automobili (Arezzo)")
    items += _parse_list(_get(SOURCES["nuovauto_km0"]),"Nuovauto (Arezzo)")
    items += _parse_list(_get(SOURCES["scotti_km0"]), "Scotti Ugo (Siena)")
    items += _parse_list(_get(SOURCES["tosoni_km0"]), "Tosoni Auto (Siena)")
    items_sorted = sorted(items, key=lambda x: (x.get("km") or 999999))
    _append_history(items_sorted)
    lines=["# 2) 🚗 Km0"]
    if not items_sorted:
        lines.append("— Nessun Km0 rilevato ora (continua monitoraggio).")
        return "\n".join(lines)
    for c in items_sorted[:8]:
        icons = _icons(c.get('price'), c.get('km'), c.get('is_ev'), c.get('is_phev'))
        price = "N/D" if c.get("price") is None else f"{int(c['price']):,} €".replace(",",".")
        km = "N/D" if c.get("km") is None else f"{c['km']:,}".replace(",",".")
        lines.append(f"- [{c['id']}] {c['title']} – {km} km {icons} – {price} – {c['dealer']}")
    return "\n".join(lines)

def build_section_usato():
    items = _parse_list(_get(SOURCES["aerre_motor_usato"]), "Aerre Motor (Arezzo)")
    items_sorted = sorted(items, key=lambda x: (x.get("km") or 999999))
    _append_history(items_sorted)
    lines=["# 3) ♻️ Usato incentivabile (ordine per km crescente; 🌟 <30k km, ⚡ EV/PHEV, 💶 <10k€)"]
    if not items_sorted:
        lines.append("— Nessun usato rilevato ora (continua monitoraggio).")
        return "\n".join(lines)
    for c in items_sorted[:10]:
        icons = _icons(c.get('price'), c.get('km'), c.get('is_ev'), c.get('is_phev'))
        price = "N/D" if c.get("price") is None else f"{int(c['price']):,} €".replace(",",".")
        km = "N/D" if c.get("km") is None else f"{c['km']:,}".replace(",",".")
        lines.append(f"- [{c['id']}] {c['title']} – {km} km {icons} – {price} – {c['dealer']}")
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

# ---------- filtri & query ----------
def fetch_all_items():
    items=[]
    items += _parse_list(_get(SOURCES["tizzi_km0"]),  "Tizzi Automobili (Arezzo)")
    items += _parse_list(_get(SOURCES["nuovauto_km0"]),"Nuovauto (Arezzo)")
    items += _parse_list(_get(SOURCES["scotti_km0"]), "Scotti Ugo (Siena)")
    items += _parse_list(_get(SOURCES["tosoni_km0"]), "Tosoni Auto (Siena)")
    items += _parse_list(_get(SOURCES["aerre_motor_usato"]), "Aerre Motor (Arezzo)")
    return items

def filter_by_brand(items, brand):
    b = brand.lower()
    return [i for i in items if (i.get("brand") and b in i["brand"]) or (i["title"].lower().find(b)>=0)]

def filter_by_type(items, t):
    t=t.lower()
    if t in ("elettriche","ev"): return [i for i in items if i.get("is_ev")]
    if t in ("ibride","phev","ibrida"): return [i for i in items if i.get("is_phev")]
    if t in ("benzina","diesel","termiche"): return [i for i in items if not (i.get("is_ev") or i.get("is_phev"))]
    return items

def filter_by_dealer(items, dealer_kw):
    d = dealer_kw.lower()
    return [i for i in items if d in i["dealer"].lower()]

def filter_by_caps(items, max_price=None, max_km=None):
    out=[]
    for i in items:
        ok=True
        if max_price is not None and (i.get("price") is None or i["price"]>max_price): ok=False
        if max_km is not None and (i.get("km") is None or i["km"]>max_km): ok=False
        if ok: out.append(i)
    return out

def format_cards(items, with_images=False):
    lines=[]
    for i in items:
        price = "N/D" if i.get("price") is None else f"{int(i['price']):,} €".replace(",",".")
        km = "N/D" if i.get("km") is None else f"{i['km']:,}".replace(",",".")
        icons = _icons(i.get('price'), i.get('km'), i.get('is_ev'), i.get('is_phev'))
        lines.append(
            f"**[{i['id']}] {i['title']}**\n"
            f"Km: {km}\n"
            f"Prezzo: {price}\n"
            f"📍 {i['dealer']}\n"
            f"{'🔗 Foto: ' + i['image'] if (with_images and i.get('image')) else ''}"
            f"{'' if icons=='' else f'\n{icons}'}"
        )
    return "\n\n".join(lines) if lines else "— Nessun risultato"

# ---------- fondi & alert ----------
def get_funds_estimate():
    html=_get(SOURCES["ecobonus_fondi"])
    if not html: return {}
    txt = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    m = re.findall(r'(\d{1,3})\s*%', txt)
    out={}
    if len(m)>=1: out["ev"]=int(m[0])
    if len(m)>=2: out["phev"]=int(m[1])
    if len(m)>=3: out["low"]=int(m[2])
    return out

def should_alert_low_funds(th=15):
    st = _load_json(STATE_PATH, {"last_funds_alert_ts": None})
    funds = get_funds_estimate()
    now = datetime.utcnow()
    need = False
    below = {}
    for k in ("ev","phev"):
        v = funds.get(k)
        if isinstance(v,int) and v < th:
            below[k]=v; need=True
    if need:
        last = st.get("last_funds_alert_ts")
        if last:
            try:
                last_dt=datetime.fromisoformat(last)
                if now - last_dt < timedelta(hours=12):
                    return None  # evita spam
            except: pass
        st["last_funds_alert_ts"]=now.isoformat()
        _save_json(STATE_PATH, st)
        return {"below": below, "funds": funds}
    return None

def detect_new_deals(items):
    """Allerte nuove promo: confronta con ultimo snapshot in state"""
    st = _load_json(STATE_PATH, {"seen_ids": []})
    seen = set(st.get("seen_ids", []))
    fresh = [i for i in items if i["id"] not in seen]
    if fresh:
        # aggiorna seen con max 300 id
        new_seen = list(seen) + [i["id"] for i in fresh]
        st["seen_ids"] = new_seen[-300:]
        _save_json(STATE_PATH, st)
    return fresh

def detect_flash_deals(items, km_cap=15000, price_cap=18000):
    hits=[]
    for i in items:
        if (i.get("km") is not None and i["km"]<=km_cap) and (i.get("price") is not None and i["price"]<=price_cap):
            hits.append(i)
    return hits

# ---------- preferenze & preferiti ----------
def load_user(chat_id: int):
    data = _load_json(USERS_PATH, {})
    return data.get(str(chat_id), {"brands": [], "max_price": None, "max_km": None, "favs": []})

def save_user(chat_id: int, user):
    data = _load_json(USERS_PATH, {})
    data[str(chat_id)] = user
    _save_json(USERS_PATH, data)
