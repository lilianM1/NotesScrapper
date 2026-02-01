import os
import json
import requests
from playwright.sync_api import sync_playwright

# --- CONFIGURATION (Via GitHub Secrets) ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
USERNAME = os.getenv("INSA_USER")
PASSWORD = os.getenv("INSA_PWD")

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def comparer_et_notifier(notes_neuves):
    fichier_cache = "notes.json"
    nouvelles_notes = []
    
    if os.path.exists(fichier_cache):
        with open(fichier_cache, "r") as f:
            notes_anciennes = json.load(f)
    else:
        notes_anciennes = {}

    for matiere, note in notes_neuves.items():
        if matiere in notes_anciennes:
            if notes_anciennes[matiere] == "-" and note != "-":
                nouvelles_notes.append(f"📚 *{matiere}* : {note}")
    
    if nouvelles_notes:
        envoyer_telegram("🔔 *NOUVELLE NOTE !*\n\n" + "\n".join(nouvelles_notes))
        print(f"Succès : {len(nouvelles_notes)} nouvelle(s) note(s) envoyée(s).")
    else:
        # Le print que tu voulais pour visualiser dans les logs GitHub
        print("RAS : Le scan a été effectué, aucune nouvelle note détectée.")

    with open(fichier_cache, "w") as f:
        json.dump(notes_neuves, f)

def executer():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto("https://extranet.insa-strasbourg.fr/")
            if "cas/login" in page.url:
                page.fill("#username", USERNAME)
                page.fill("#password", PASSWORD)
                page.keyboard.press("Enter")
                page.wait_for_url("**/extranet.insa-strasbourg.fr/**", timeout=15000)

            page.click("input[value='Consulter vos notes du 1er semestre']")
            page.wait_for_selector("table")
            
            notes_actuelles = {}
            tables = page.locator("td > table").all()
            for t in tables:
                for row in t.locator("tr").all():
                    cells = row.locator("td").all()
                    if len(cells) >= 3:
                        m = " ".join(cells[1].inner_text().split())
                        n = cells[2].inner_text().strip()
                        if m: notes_actuelles[m] = n
            
            comparer_et_notifier(notes_actuelles)
        except Exception as e:
            print(f"Erreur technique : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    executer()