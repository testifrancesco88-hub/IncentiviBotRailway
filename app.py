import os, requests
from fastapi import FastAPI, Request
from report_core import (
    build_report, build_section_nuovo, build_section_km0, build_section_usato,
    fetch_all_items, filter_by_brand, filter_by_type, filter_by_dealer, filter_by_caps,
    format_cards, get_funds_estimate, should_alert_low_funds, detect_new_deals,
    detect_flash_deals, load_user, save_user
)

BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
ALLOWED_CHAT_ID = int(os.getenv("TG_CHAT_ID", "0") or "0")
RUN_SECRET = os.getenv("RUN_SECRET", "")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = FastAPI()

def send_message(chat_id: int, text: str, parse_mode: str = None):
    if not BOT_TOKEN or not chat_id:
        print("Missing TG creds, skip send.")
        return
    for chunk in [text[i:i+3800] for i in range(0, len(text), 3800)] or ["(vuoto)"]:
        data = {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": "true"}
        if parse_mode: data["parse_mode"] = parse_mode
        try:
            requests.post(f"{API}/sendMessage", data=data, timeout=20)
        except Exception as e:
            print("Send error:", e)

def send_photo(chat_id: int, photo_url: str, caption: str = ""):
    if not BOT_TOKEN or not chat_id or not photo_url: return
    try:
        requests.post(f"{API}/sendPhoto", data={"chat_id": chat_id, "photo": photo_url, "caption": caption}, timeout=20)
    except Exception as e:
        print("Photo error:", e)

@app.get("/health")
def health():
    return {"ok": True, "has_token": bool(BOT_TOKEN), "has_chat": bool(ALLOWED_CHAT_ID)}

# ===== Manual run (for cron/GET) =====
@app.get("/run")
def run(key: str = ""):
    if not RUN_SECRET or key != RUN_SECRET:
        return {"ok": False, "error": "unauthorized"}
    send_message(ALLOWED_CHAT_ID, build_report())
    return {"ok": True}

# ===== Periodic tick (alerts proattive) =====
@app.get("/tick")
def tick(key: str = ""):
    if not RUN_SECRET or key != RUN_SECRET:
        return {"ok": False, "error": "unauthorized"}
    # 1) fondi bassi
    low = should_alert_low_funds(th=15)
    if low:
        below = ", ".join([f"{k.upper()} {v}%" for k,v in low["below"].items()])
        send_message(ALLOWED_CHAT_ID, f"⚠️ Fondi bassi: {below}. Consiglio: prenota subito.", None)

    # 2) nuove promo
    items = fetch_all_items()
    fresh = detect_new_deals(items)
    if fresh:
        msg = "🆕 Nuove promo rilevate:\n\n" + format_cards(fresh[:5], with_images=False)
        send_message(ALLOWED_CHAT_ID, msg, parse_mode="Markdown")
        # immagini (best-effort)
        for it in fresh[:3]:
            if it.get("image"):
                send_photo(ALLOWED_CHAT_ID, it["image"], caption=it["title"])

    # 3) occasioni lampo
    hot = detect_flash_deals(items, km_cap=15000, price_cap=18000)
    if hot:
        msg = "🔥 Occasioni lampo (<=15.000 km e <=18.000 €):\n\n" + format_cards(hot[:5], with_images=False)
        send_message(ALLOWED_CHAT_ID, msg, parse_mode="Markdown")
    return {"ok": True}

# ===== Webhook Telegram =====
@app.post("/tg")
async def tg_webhook(req: Request):
    update = await req.json()
    msg = update.get("message") or update.get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip().lower()

    if not chat_id or int(chat_id) != ALLOWED_CHAT_ID:
        return {"ok": True}

    if text.startswith("/start") or text.startswith("/help"):
        send_message(chat_id,
            "Comandi:\n"
            "/report – report completo\n"
            "/nuovo  – solo Nuovo\n"
            "/km0    – solo Km0\n"
            "/usato  – solo Usato\n"
            "/brand <marca> – es. /brand peugeot\n"
            "/dealer <nome> – es. /dealer aerre\n"
            "/elettriche | /ibride | /benzina\n"
            "/config brand=peugeot,fiat maxprice=20000 maxkm=30000\n"
            "/segna <id_auto> – salva nei preferiti\n"
            "/preferiti – mostra i preferiti\n"
        )
        return {"ok": True}

    # --- comandi base già esistenti ---
    if text.startswith("/report") or text == "report":
        send_message(chat_id, build_report())
        return {"ok": True}
    if text.startswith("/nuovo"):
        send_message(chat_id, build_section_nuovo())
        return {"ok": True}
    if text.startswith("/km0"):
        send_message(chat_id, build_section_km0())
        return {"ok": True}
    if text.startswith("/usato"):
        send_message(chat_id, build_section_usato())
        return {"ok": True}

    # --- brand/dealer/type filters ---
    if text.startswith("/brand"):
        parts = text.split(maxsplit=1)
        if len(parts)<2:
            send_message(chat_id, "Uso: /brand <marca> (es. /brand peugeot)")
        else:
            brand = parts[1]
            items = filter_by_brand(fetch_all_items(), brand)
            send_message(chat_id, f"🔎 Filtra marca: {brand}\n\n" + format_cards(items[:10], with_images=False), parse_mode="Markdown")
        return {"ok": True}

    # scorciatoie /peugeot /fiat /renault …
    for b in ["peugeot","fiat","renault","opel","kia","alfa","volkswagen","vw"]:
        if text.startswith("/"+b):
            items = filter_by_brand(fetch_all_items(), b)
            send_message(chat_id, f"🔎 {b.title()}\n\n" + format_cards(items[:10], with_images=False), parse_mode="Markdown")
            return {"ok": True}

    if text.startswith("/dealer"):
        parts = text.split(maxsplit=1)
        if len(parts)<2:
            send_message(chat_id, "Uso: /dealer <nome> (es. /dealer aerre)")
        else:
            items = filter_by_dealer(fetch_all_items(), parts[1])
            send_message(chat_id, "🏪 Dealer\n\n" + format_cards(items[:10], with_images=False), parse_mode="Markdown")
        return {"ok": True}

    if text.startswith("/elettriche") or text.startswith("/ibride") or text.startswith("/benzina"):
        t = "elettriche" if "/elettriche" in text else ("ibride" if "/ibride" in text else "benzina")
        items = filter_by_type(fetch_all_items(), t)
        send_message(chat_id, f"⚡ Tipo: {t}\n\n" + format_cards(items[:10], with_images=False), parse_mode="Markdown")
        return {"ok": True}

    # --- config utente ---
    if text.startswith("/config"):
        # es: /config brand=peugeot,fiat maxprice=20000 maxkm=30000
        u = load_user(chat_id)
        try:
            body = text.replace("/config","").strip()
            for token in body.split():
                if token.startswith("brand="):
                    brands = token.split("=",1)[1].split(",")
                    u["brands"] = [b.strip().lower() for b in brands if b.strip()]
                elif token.startswith("maxprice="):
                    u["max_price"] = int(token.split("=",1)[1])
                elif token.startswith("maxkm="):
                    u["max_km"] = int(token.split("=",1)[1])
            save_user(chat_id, u)
            send_message(chat_id, f"✅ Config salvata: {u}")
        except Exception as e:
            send_message(chat_id, f"❌ Config non valida. Esempio: /config brand=peugeot,fiat maxprice=20000 maxkm=30000\nErrore: {e}")
        return {"ok": True}

    if text.startswith("/preferiti"):
        u = load_user(chat_id)
        favs = u.get("favs", [])
        if not favs:
            send_message(chat_id, "⭐ Nessun preferito salvato. Usa /segna <id_auto> sulle liste.")
        else:
            # ricostruisci card dai risultati correnti
            items = fetch_all_items()
            index = {i["id"]: i for i in items}
            selected = [index[i] for i in favs if i in index]
            send_message(chat_id, "⭐ Preferiti\n\n" + format_cards(selected, with_images=False), parse_mode="Markdown")
        return {"ok": True}

    if text.startswith("/segna"):
        parts = text.split(maxsplit=1)
        if len(parts)<2:
            send_message(chat_id, "Uso: /segna <id_auto>")
        else:
            idwanted = parts[1].strip().strip("[]")
            u = load_user(chat_id)
            favs = set(u.get("favs", []))
            favs.add(idwanted)
            u["favs"] = list(favs)[:50]
            save_user(chat_id, u)
            send_message(chat_id, f"✅ Aggiunto ai preferiti: {idwanted}")
        return {"ok": True}

    # fallback
    send_message(chat_id, "Non ho capito. Scrivi /help per l’elenco comandi.")
    return {"ok": True}
