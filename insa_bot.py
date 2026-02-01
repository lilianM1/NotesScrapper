from playwright.sync_api import sync_playwright
import time
import json
import os
import requests

# --- CONFIGURATION ---
TOKEN = "8318629768:AAE_BT1HgypiBe2ctusWb_KHg8zQIG1Qvg8"
CHAT_ID = "5053621995"
USERNAME = "leymin01"
PASSWORD = "tve7u235!Insa" 

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Erreur envoi Telegram : {e}")

def comparer_et_notifier(notes_neuves):
    fichier_cache = "notes.json"
    nouvelles_notes_liste = []
     
    if os.path.exists(fichier_cache):
        with open(fichier_cache, "r") as f:
            notes_anciennes = json.load(f)
    else:
        notes_anciennes = {}
        print("Initialisation : Premier scan effectué.")

    for matiere, note in notes_neuves.items():
        if matiere in notes_anciennes:
            if notes_anciennes[matiere] == "-" and note != "-":
                nouvelles_notes_liste.append(f"📚 *{matiere}* : {note}")
        elif notes_anciennes and note != "-":
            nouvelles_notes_liste.append(f"📚 *{matiere}* : {note}")

    if nouvelles_notes_liste:
        header = "🔔 *NOUVELLE NOTE DÉTECTÉE !*\n\n"
        corps = "\n".join(nouvelles_notes_liste)
        envoyer_telegram(header + corps)
        print(f"Notification envoyée : {len(nouvelles_notes_liste)} note(s).")
    else:
        print("RAS : Aucune nouvelle note.")

    with open(fichier_cache, "w") as f:
        json.dump(notes_neuves, f)

def executer_surveillance():
    with sync_playwright() as p:
        # headless=True pour ne pas être dérangé par l'ouverture de fenêtres
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto("https://extranet.insa-strasbourg.fr/", wait_until="networkidle")
            
            if "cas/login" in page.url:
                page.fill("#username", USERNAME)
                page.fill("#password", PASSWORD)
                page.keyboard.press("Enter")
                page.wait_for_url("**/extranet.insa-strasbourg.fr/**", timeout=15000)

            page.click("input[value='Consulter vos notes du 1er semestre']")
            page.wait_for_selector("table")
            
            notes_actuelles = {}
            tables_matieres = page.locator("td > table").all()
            for table in tables_matieres:
                lignes = table.locator("tr").all()
                for ligne in lignes:
                    cellules = ligne.locator("td").all()
                    if len(cellules) >= 3:
                        matiere = cellules[1].inner_text().strip()
                        note = cellules[2].inner_text().strip()
                        if matiere:
                            matiere_propre = " ".join(matiere.split())
                            notes_actuelles[matiere_propre] = note

            comparer_et_notifier(notes_actuelles)
        except Exception as e:
            print(f"Erreur lors du scan : {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    print("🚀 Surveillance INSA active (Toutes les 5 minutes)...")
    while True:
        executer_surveillance()
        # 300 secondes = 5 minutes
        time.sleep(300)