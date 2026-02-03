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

def nettoyer_nom_matiere(raw_name):
    """
    Nettoie le nom de la matière en extrayant le nom lisible.
    Ex: "STM-GE-01-Electronique" -> "Electronique"
    Ex: "Stage-STI1 : stage en ingénierie-GE2" -> "stage en ingénierie"
    """
    nom_propre = raw_name.strip()
    
    # Si le nom contient ":", prendre ce qui est après le ":"
    if ":" in nom_propre:
        # Ex: "Stage-STI1 : stage en ingénierie-GE2" -> "stage en ingénierie-GE2"
        nom_propre = nom_propre.split(":", 1)[1].strip()
    
    # Puis nettoyer les codes du début (ex: STM-GE-01-)
    if "-" in nom_propre:
        parts = nom_propre.split("-")
        # Si le dernier morceau est long (>3 caractères), c'est probablement le nom
        if len(parts[-1]) > 3:
            nom_propre = parts[-1].strip()
        else:
            # Sinon, chercher la première partie qui semble être un nom (>3 caractères)
            for part in parts:
                if len(part) > 3:
                    nom_propre = part.strip()
                    break
            else:
                # Dernier recours: prendre tout après le premier tiret
                nom_propre = nom_propre.split("-", 1)[1].strip() if len(parts) > 1 else nom_propre
    
    return nom_propre

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

            # Screenshot après login
            page.screenshot(path="debug_after_login.png")
            print("📸 Screenshot après login: debug_after_login.png")

            # Accès aux notes (clic sur le bouton semestre)
            print("Recherche bouton semestre...")
            bouton = page.locator("input[value*='1er semestre'], input[value*='1er']")
            if bouton.count() > 0:
                print(f"✅ Bouton semestre trouvé ({bouton.count()} éléments)")
                bouton.first.click()
                page.wait_for_load_state("networkidle")
            else:
                print("⚠️ Bouton semestre non trouvé - on continue avec la page actuelle")
            
            # Screenshot de debug après sélection semestre
            page.screenshot(path="debug_page.png")
            print("📸 Screenshot sauvegardé: debug_page.png")
            
            # --- SCRAPING INTELLIGENT AVEC TABLES IMBRIQUÉES ---
            notes_dict = {}
            
            # Méthode 1: Parcourir les tables imbriquées (structure UE > sous-tableau)
            print("📊 Méthode 1: Recherche de tables imbriquées (UE > matières)...")
            
            # Trouver toutes les lignes principales qui pourraient contenir des UE
            main_rows = page.locator("table tr").all()
            
            for main_row in main_rows:
                # Chercher les cellules de cette ligne
                cells = main_row.locator("td").all()
                
                # Pour chaque cellule, chercher s'il y a un sous-tableau
                for cell in cells:
                    # Chercher les sous-tableaux dans cette cellule
                    nested_tables = cell.locator("table").all()
                    
                    for nested_table in nested_tables:
                        # Dans le sous-tableau, parcourir les lignes
                        nested_rows = nested_table.locator("tr").all()
                        
                        for nested_row in nested_rows:
                            nested_cells = nested_row.locator("td").all()
                            
                            # On s'attend à: [Matière, Coefficient, Note]
                            # Ou: [Matière avec coef dans le nom, ..., Note]
                            if len(nested_cells) >= 3:
                                # Format: [Matière, Coef, Note]
                                raw_name = nested_cells[0].inner_text().strip()
                                coef = nested_cells[1].inner_text().strip()
                                raw_note = nested_cells[2].inner_text().strip()
                                
                                # Nettoyer le nom de la matière
                                nom_propre = nettoyer_nom_matiere(raw_name)
                                
                                # Stocker si valide
                                if nom_propre and coef and nom_propre.lower() != "matière":
                                    notes_dict[nom_propre] = {"note": raw_note, "coef": coef}
                                    print(f"✅ Trouvé (table imbriquée): {nom_propre} | Note: {raw_note} | Coef: {coef}")
                            
                            elif len(nested_cells) >= 2:
                                # Peut-être format: [Matière, Note] avec coef dans le nom
                                raw_name = nested_cells[0].inner_text().strip()
                                raw_note = nested_cells[-1].inner_text().strip()
                                
                                # Chercher le coef dans le nom
                                match_coef = re.search(r"-\s*\(([\d.,]+)\)(?:\s*\([^)]*\))?\s*$", raw_name)
                                
                                if match_coef:
                                    coef = match_coef.group(1)
                                    nom_sans_coef = raw_name[:match_coef.start()].strip()
                                    nom_propre = nettoyer_nom_matiere(nom_sans_coef)
                                    
                                    if nom_propre:
                                        notes_dict[nom_propre] = {"note": raw_note, "coef": coef}
                                        print(f"✅ Trouvé (table imbriquée, coef dans nom): {nom_propre} | Note: {raw_note} | Coef: {coef}")
            
            # Méthode 2: Si aucune note trouvée, essayer l'ancienne méthode plate
            if not notes_dict:
                print("🔍 Méthode 2: Recherche avec structure plate (fallback)...")
                rows = page.locator("tr").all()
                print(f"📊 {len(rows)} lignes <tr> trouvées")
                
                for row in rows:
                    cells = row.locator("td").all()
                    
                    if len(cells) >= 2:
                        raw_name = cells[0].inner_text().strip()
                        
                        # Regex pour choper le coef "(3)" ou "(1,5)" après un tiret
                        match_coef = re.search(r"-\s*\(([\d.,]+)\)(?:\s*\([^)]*\))?\s*$", raw_name)
                        
                        if match_coef:
                            coef = match_coef.group(1)
                            raw_note = cells[-1].inner_text().strip()
                            if not raw_note and len(cells) > 2:
                                raw_note = cells[-2].inner_text().strip()
                            
                            nom_sans_coef = raw_name[:match_coef.start()].strip()
                            nom_propre = nettoyer_nom_matiere(nom_sans_coef)
                            
                            if nom_propre:
                                notes_dict[nom_propre] = {"note": raw_note, "coef": coef}
                                print(f"✅ Trouvé (structure plate): {nom_propre} | Note: {raw_note} | Coef: {coef}")
            
            # Méthode 3: Si aucune note trouvée, chercher dans le texte brut de la page
            if not notes_dict:
                print("🔍 Méthode 3: Recherche dans le texte brut de la page...")
                page_text = page.content()
                
                # Pattern pour trouver: "Nom matière - (coef)" suivi d'une note
                pattern = r'([A-Z][A-Za-z0-9\-\s:éèêàù&]+)\s*-\s*\(([\d.,]+)\)[^<\d]*?([\d,]+|[A-Z]|-)'
                matches = re.findall(pattern, page_text)
                
                for match in matches:
                    raw_name, coef, note = match
                    nom_propre = nettoyer_nom_matiere(raw_name.strip())
                    
                    if nom_propre and len(nom_propre) > 3:
                        notes_dict[nom_propre] = {"note": note.strip(), "coef": coef}
                        print(f"✅ Trouvé (méthode texte): {nom_propre} | Note: {note} | Coef: {coef}")

            if notes_dict:
                comparer_et_notifier(notes_dict)
                print(f"✅ {len(notes_dict)} notes enregistrées")
            else:
                print("⚠️ Aucune note trouvée (structure introuvable ?)")
                # Sauvegarde du HTML pour debug
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                print("📄 HTML de debug sauvegardé: debug_page.html")

        except Exception as e:
            print(f"❌ Erreur: {e}")
            # Screenshot d'erreur
            try:
                page.screenshot(path="error_screenshot.png")
                print("📸 Screenshot d'erreur sauvegardé: error_screenshot.png")
            except Exception:
                pass
        finally:
            browser.close()

if __name__ == "__main__":
    executer()
