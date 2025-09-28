import os, requests
from fastapi import FastAPI, Request
from report_core import build_report, build_section_nuovo, build_section_km0, build_section_usato

# ✅ leggi variabili da Railway (TG_BOT_TOKEN e TG_CHAT_ID devono essere settate nelle Variables)
BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
ALLOWED_CHAT_ID = int(os.getenv("TG_CHAT_ID", "0") or "0")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = FastAPI()

def send_message(chat_id: int, text: str):
    """Invia messaggi Telegram a blocchi di max 3800 caratteri"""
    if not BOT_TOKEN or not ALLOWED_CHAT_ID:
        print("⚠️ Mancano TG_BOT_TOKEN o TG_CHAT_ID, skip send.")
        return
    parts = [text[i:i+3800] for i in range(0, len(text), 3800)] or ["(vuoto)"]
    for p in parts:
        try:
            requests.post(f"{API}/sendMessage", data={
                "chat_id": chat_id,
                "text": p,
                "disable_web_page_preview": "true"
            }, timeout=20)
        except Exception as e:
            print("Errore invio Telegram:", e)

@app.get("/health")
def health():
    """Verifica stato app e variabili"""
    return {
        "ok": True,
        "has_token": bool(BOT_TOKEN),
        "has_chat": bool(ALLOWED_CHAT_ID)
    }

@app.post("/tg")
async def tg_webhook(req: Request):
    """Riceve update Telegram e risponde ai comandi"""
    update = await req.json()
    msg = update.get("message") or update.get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip().lower()

    if not BOT_TOKEN or not ALLOWED_CHAT_ID:
        print("Webhook ricevuto ma ENV mancanti.")
        return {"ok": True}

    # accetta solo il tuo chat ID
    if not chat_id or int(chat_id) != ALLOWED_CHAT_ID:
        return {"ok": True}

    if text.startswith("/report") or text == "report":
        send_message(chat_id, build_report())
    elif text.startswith("/nuovo") or text == "nuovo":
        send_message(chat_id, build_section_nuovo())
    elif text.startswith("/km0") or text == "km0":
        send_message(chat_id, build_section_km0())
    elif text.startswith("/usato") or text == "usato":
        send_message(chat_id, build_section_usato())
    else:
        send_message(chat_id, "ℹ️ Comandi disponibili: /report, /nuovo, /km0, /usato")

    return {"ok": True}
