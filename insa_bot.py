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

# --- CONSTANTES DE SCRAPING ---
MIN_SUBJECT_NAME_LENGTH = 3
HEADER_MATIERE = "matière"

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
        coef_new = data_new["coef"]
        
        data_old = notes_anciennes.get(matiere)
        if isinstance(data_old, dict):
            note_old = data_old.get("note", "-")
        else:
            note_old = str(data_old or "-")

        if (note_old in ["-", "None", "", "A"]) and (note_new not in ["-", "None", "", "A"]):
            changements.append(f"🎉 *{matiere}*\n➡️ Note : *{note_new}* (Coef {coef_new})\n")
        elif note_old != note_new and note_new not in ["-", "None", ""]:
            changements.append(f"📝 *{matiere}*\nAncienne: `{note_old}`\nNouvelle: *{note_new}*")

    if changements:
        envoyer_telegram("🔔 *NOUVELLES NOTES !*\n\n" + "\n".join(changements))

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(notes_nouvelles, f, indent=4, ensure_ascii=False)

def nettoyer_nom_matiere(raw_name):
    nom_propre = raw_name.strip()
    if ":" in nom_propre:
        nom_propre = nom_propre.split(":", 1)[1].strip()
    
    if "-" in nom_propre:
        parts = nom_propre.split("-")
        if len(parts[-1].strip()) > MIN_SUBJECT_NAME_LENGTH:
            nom_propre = parts[-1].strip()
        else:
            for part in parts:
                if len(part.strip()) > MIN_SUBJECT_NAME_LENGTH:
                    nom_propre = part.strip()
                    break
    return nom_propre

def executer():
    if not USERNAME or not PASSWORD:
        print("❌ Identifiants manquants")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()

        try:
            print("Connexion à l'extranet...")
            page.goto("https://extranet.insa-strasbourg.fr/", timeout=60000)
            
            if page.locator("#username").is_visible():
                page.fill("#username", USERNAME)
                page.fill("#password", PASSWORD)
                page.click("button[type='submit'], input[type='submit']")
                page.wait_for_timeout(5000)

            # Navigation vers le semestre actuel
            bouton = page.locator("input[value*='1er semestre'], input[value*='1er']")
            if bouton.count() > 0:
                bouton.first.click()
                page.wait_for_timeout(5000)
            
            notes_dict = {}
            
            # Ciblage du tableau principal des notes
            rows = page.locator("table.bgtable tr").all()
            
            for row in rows:
                # Chaque UE contient un sous-tableau avec les matières
                nested_tables = row.locator("table").all()
                for table in nested_tables:
                    nested_rows = table.locator("tr").all()
                    for n_row in nested_rows:
                        cells = n_row.locator("td").all()
                        
                        # Structure observée : [Vide, Nom + Coef, Note]
                        if len(cells) >= 3:
                            raw_name = cells[1].inner_text().strip()
                            raw_note = cells[2].inner_text().strip()
                            
                            # Extraction du coefficient entre parenthèses
                            match_coef = re.search(r"\((\d+[\.,]?\d*)\)", raw_name)
                            coef = match_coef.group(1) if match_coef else "1"
                            
                            # Nettoyage du nom (on enlève la partie coef du nom)
                            name_clean = re.sub(r"\s*-\s*\(\d+[\.,]?\d*\).*", "", raw_name)
                            nom_propre = nettoyer_nom_matiere(name_clean)
                            
                            if nom_propre and nom_propre.lower() != HEADER_MATIERE:
                                notes_dict[nom_propre] = {"note": raw_note, "coef": coef}
                                print(f"✅ Trouvé : {nom_propre} | Note: {raw_note} | Coef: {coef}")

            if notes_dict:
                comparer_et_notifier(notes_dict)
                print(f"✅ {len(notes_dict)} notes traitées avec succès")
            else:
                print("⚠️ Aucune note n'a pu être extraite.")
                with open("debug_error.html", "w", encoding="utf-8") as f:
                    f.write(page.content())

        except Exception as e:
            print(f"❌ Erreur lors du scraping: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    executer()

