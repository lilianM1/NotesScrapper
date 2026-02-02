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
    
    # On compare
    for matiere, data_new in notes_nouvelles.items():
        note_new = data_new["note"]
        coef_new = data_new["coef"]
        
        # Récup ancienne donnée
        data_old = notes_anciennes.get(matiere)
        note_old = data_old.get("note", "-") if isinstance(data_old, dict) else str(data_old or "-")

        # Détection changement
        if (note_old in ["-", "None", ""]) and (note_new not in ["-", "None", ""]):
            changements.append(f"🎉 *{matiere}*\n➡️ Note : *{note_new}* (Coef {coef_new})\n")
        elif note_old != note_new and note_new not in ["-", "None", ""]:
            changements.append(f"📝 *{matiere}*\nAncienne: `{note_old}`\nNouvelle: *{note_new}*")

    if changements:
        envoyer_telegram("🔔 *NOUVELLES NOTES !*\n\n" + "\n".join(changements))

    # Sauvegarde
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(notes_nouvelles, f, indent=4, ensure_ascii=False)

def executer():
    if not USERNAME or not PASSWORD:
        print("❌ ID manquants")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()

        try:
            print("Connexion...")
            page.goto("https://extranet.insa-strasbourg.fr/", timeout=60000)
            
            # Login
            if page.locator("#username").is_visible():
                page.fill("#username", USERNAME)
                page.fill("#password", PASSWORD)
                page.click("button[type='submit'], input[type='submit']")
                page.wait_for_load_state("networkidle")

            # Accès aux notes (clic sur le bouton semestre)
            print("Recherche tableau...")
            bouton = page.locator("input[value*='1er semestre'], input[value*='1er']")
            if bouton.count() > 0:
                bouton.first.click()
                page.wait_for_load_state("networkidle")
            
            # --- SCRAPING INTELLIGENT ---
            notes_dict = {}
            
            # On prend toutes les lignes de tableaux
            rows = page.locator("tr").all()
            
            for row in rows:
                text_content = row.inner_text()
                
                # On cherche le pattern : "Blabla - (Chiffre)" dans une cellule
                # Et une note (chiffre avec virgule ou lettre ou tiret) dans une autre
                cells = row.locator("td").all()
                
                if len(cells) >= 2:
                    # Cellule 1 : Contient souvent le nom + coef
                    raw_name = cells[0].inner_text().strip() # ex: STM-GE-01-Elec - (3)
                    
                    # Regex pour choper le coef à la fin "(3)" ou "(1,5)"
                    match_coef = re.search(r"-\s*\(([\d.,]+)\)$", raw_name)
                    
                    if match_coef:
                        # On a trouvé une ligne de matière !
                        coef = match_coef.group(1) # Le "3"
                        
                        # Note: Elle est souvent dans la dernière cellule de la ligne
                        raw_note = cells[-1].inner_text().strip()
                        # Si la dernière cellule est vide ou bizarre, on tente l'avant-dernière
                        if not raw_note and len(cells) > 2:
                            raw_note = cells[-2].inner_text().strip()
                        
                        # NETTOYAGE NOM : Enlever "STM-GE-01-" et " - (3)"
                        # 1. On enlève la fin (le coef)
                        nom_propre = raw_name[:match_coef.start()].strip()
                        
                        # 2. On enlève le code au début (tout ce qui est avant le dernier tiret du groupe de code)
                        # Souvent c'est le 3ème tiret. Ex: UE-GEC-STM-GE-01
                        # Méthode bourrin mais efficace : on garde ce qu'il y a après le dernier tiret SI y'a des tirets
                        if "-" in nom_propre:
                             # Ex: "STM-GE-01-Electronique" -> split -> ["STM", "GE", "01", "Electronique"]
                             parts = nom_propre.split("-")
                             # Si le dernier morceau est long (>2 lettres), c'est probablement le nom
                             if len(parts[-1]) > 2:
                                 nom_propre = parts[-1].strip()
                             else:
                                 # Cas bizarre, on prend tout après le premier tiret
                                 nom_propre = nom_propre.split("-", 1)[1].strip()

                        # Stockage
                        if nom_propre:
                            notes_dict[nom_propre] = {"note": raw_note, "coef": coef}
                            print(f"✅ Trouvé: {nom_propre} | Note: {raw_note} | Coef: {coef}")

            if notes_dict:
                comparer_et_notifier(notes_dict)
            else:
                print("⚠️ Aucune note trouvée (structure introuvable ?)")

        except Exception as e:
            print(f"❌ Erreur: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    executer()
