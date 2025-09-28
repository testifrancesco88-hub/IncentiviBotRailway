# cron_tick.py
import os, requests
from datetime import datetime

URL = "https://incentivibotrailway-production.up.railway.app/tick"
KEY = os.getenv("RUN_SECRET", "")

def main():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] ⏱️ Tick proattivo")
    if not KEY:
        print("❌ RUN_SECRET non trovato")
        return
    r = requests.get(URL, params={"key": KEY}, timeout=30)
    print("Status:", r.status_code, "Body:", r.text)

if __name__ == "__main__":
    main()
