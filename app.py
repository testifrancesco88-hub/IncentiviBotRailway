import os, requests
from fastapi import FastAPI, Request
from report_core import build_report, build_section_nuovo, build_section_km0, build_section_usato

BOT_TOKEN = os.environ["TG_BOT_TOKEN"]          # es: 8416...nILU
ALLOWED_CHAT_ID = int(os.environ["TG_CHAT_ID"]) # es: 6950900648
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = FastAPI()

def send_message(chat_id: int, text: str):
    parts = [text[i:i+3800] for i in range(0, len(text), 3800)] or ["(vuoto)"]
    for p in parts:
        requests.post(f"{API}/sendMessage", data={
            "chat_id": chat_id, "text": p, "disable_web_page_preview": "true"
        }, timeout=20)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/tg")
async def tg_webhook(req: Request):
    update = await req.json()
    msg = update.get("message") or update.get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip().lower()

    # accetta solo messaggi dal tuo chat ID
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
        send_message(chat_id, "Comandi: /report, /nuovo, /km0, /usato")
    return {"ok": True}
