import os, requests

URL = "https://incentivibotrailway-production.up.railway.app/run"
KEY = os.getenv("sabato", "")

def main():
    if not KEY:
        print("❌ RUN_SECRET mancante")
        return
    try:
        r = requests.get(URL, params={"key": KEY}, timeout=20)
        print("✅ Report inviato:", r.text)
    except Exception as e:
        print("Errore:", e)

if __name__ == "__main__":
    main()
