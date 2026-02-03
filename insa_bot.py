import os
import json
import re
import requests
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
USERNAME = os.getenv("INSA_USER")
PASSWORD = os.getenv("INSA_PWD")
CACHE_FILE = "notes.json"

def envoyer_telegram(message):
    if not TOKEN or not CHAT_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def comparer_et_notifier(notes_nouvelles):
    notes_anciennes = {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            notes_anciennes = json.load(f)
    except: pass

    changements = []
    for matiere, data_new in notes_nouvelles.items():
        note_new = data_new["note"]
        data_old = notes_anciennes.get(matiere, {})
        note_old = data_old.get("note", "-") if isinstance(data_old, dict) else str(data_old)

        if (note_old in ["-", ""]) and (note_new not in ["-", ""]):
            changements.append(f"🎉 *{matiere}*\n➡️ Note : *{note_new}* (Coef {data_new['coef']})\n")
    
    if changements:
        envoyer_telegram("🔔 *NOUVELLES NOTES !*\n\n" + "\n".join(changements))

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(notes_nouvelles, f, indent=4, ensure_ascii=False)

def executer():
    if not USERNAME or not PASSWORD:
        print("❌ Identifiants manquants")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # On force une taille de fenêtre standard pour le rendu
        page = browser.new_context(viewport={'width': 1280, 'height': 720}).new_page()

        try:
            print("Connexion à l'extranet...")
            page.goto("https://extranet.insa-strasbourg.fr/", timeout=60000)
            
            if page.locator("#username").is_visible():
                page.fill("#username", USERNAME)
                page.fill("#password", PASSWORD)
                page.click("button[type='submit'], input[type='submit']")
                page.wait_for_timeout(3000) # Pause pour laisser charger le portail

            # Clic sur le bouton du semestre
            bouton = page.locator("input[value*='1er semestre'], input[value*='1er']")
            if bouton.count() > 0:
                bouton.first.click()
                page.wait_for_timeout(3000) # Attente indispensable sur petite VM
            
            notes_dict = {}
            # Ciblage via la classe spécifique du tableau INSA
            rows = page.locator("table.bgtable tr").all()
            
            for row in rows:
                nested_tables = row.locator("table").all()
                for table in nested_tables:
                    nested_rows = table.locator("tr").all()
                    for n_row in nested_rows:
                        cells = n_row.locator("td").all()
                        if len(cells) >= 3:
                            raw_name = cells[1].inner_text().strip()
                            raw_note = cells[2].inner_text().strip()
                            
                            match_coef = re.search(r"\((\d+[\.,]?\d*)\)", raw_name)
                            coef = match_coef.group(1) if match_coef else "1"
                            
                            # Nettoyage du nom
                            name_clean = re.sub(r"\s*-\s*\(\d+[\.,]?\d*\).*", "", raw_name)
                            if ":" in name_clean: name_clean = name_clean.split(":", 1)[1]
                            nom = name_clean.split("-")[-1].strip() if "-" in name_clean else name_clean.strip()
                            
                            if len(nom) > 2 and nom.lower() != "matière":
                                notes_dict[nom] = {"note": raw_note, "coef": coef}
                                print(f"✅ Trouvé : {nom} | Note: {raw_note}")

            if notes_dict:
                comparer_et_notifier(notes_dict)
                print(f"✅ {len(notes_dict)} notes traitées")
            else:
                print("⚠️ Aucune note n'a pu être extraite.")
                page.screenshot(path="debug_error.png")

        except Exception as e:
            print(f"❌ Erreur: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    executer()
