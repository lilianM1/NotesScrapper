import os
import json
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- CONFIGURATION (GitHub Secrets) ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
USERNAME = os.getenv("INSA_USER")
PASSWORD = os.getenv("INSA_PWD")

CACHE_FILE = "notes.json"

# --- TELEGRAM ---
def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erreur Telegram : {e}")

# --- COMPARAISON DES NOTES ---
def comparer_et_notifier(notes_nouvelles):
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                notes_anciennes = json.load(f)
        else:
            notes_anciennes = {}
    except json.JSONDecodeError:
        notes_anciennes = {}

    changements = []

    for matiere, note in notes_nouvelles.items():
        ancienne = notes_anciennes.get(matiere)

        if ancienne is None and note != "-":
            changements.append(f"📚 *{matiere}*\n➡️ Nouvelle note : *{note}*")
        elif ancienne != note and note != "-":
            changements.append(
                f"📚 *{matiere}*\n"
                f"Ancienne : `{ancienne}`\n"
                f"Nouvelle : *{note}*"
            )

    if changements:
        envoyer_telegram(
            "🔔 *MISE À JOUR DES NOTES INSA*\n\n" +
            "\n\n".join(changements)
        )
        print(f"{len(changements)} changement(s) détecté(s).")
    else:
        print("RAS : aucune nouvelle note.")

    with open(CACHE_FILE, "w") as f:
        json.dump(notes_nouvelles, f, indent=4, ensure_ascii=False)

# --- SCRIPT PRINCIPAL ---
def executer():
    if not USERNAME or not PASSWORD:
        print("Erreur : Les identifiants INSA_USER ou INSA_PWD sont vides !")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            print("Connexion à l'extranet INSA...")
            page.goto("https://extranet.insa-strasbourg.fr/", wait_until="domcontentloaded", timeout=60000)

            # --- LOGIN CAS ---
            # Vérifier si on est sur la page de login CAS (présence du champ username)
            try:
                if page.locator("#username").is_visible(timeout=3000):
                    print("Authentification CAS...")
                    page.fill("#username", USERNAME)
                    page.fill("#password", PASSWORD)
                    page.click("button[type='submit'], input[type='submit']")
            except:
                print("Pas de page CAS détectée, déjà connecté ?")
            
            # Attendre que la page soit complètement chargée
            print("Attente du chargement de l'extranet...")
            page.wait_for_load_state("networkidle", timeout=30000)
            
            print(f"✅ Connecté ! URL: {page.url}")
            page.screenshot(path="debug_after_login.png", full_page=True)

            # --- ACCÈS AUX NOTES DU 1ER SEMESTRE ---
            print("Clic sur 'Consulter vos notes du 1er semestre'...")
            
            # Chercher le bouton exact
            bouton = page.locator("input[value*='1er semestre']")
            if not bouton.is_visible(timeout=5000):
                # Essayer avec un autre sélecteur
                bouton = page.locator("input[value*='1er']")
            
            if bouton.is_visible(timeout=3000):
                bouton.click()
                print("Bouton cliqué !")
            else:
                print("❌ Bouton 1er semestre non trouvé")
                # Lister tous les inputs pour debug
                inputs = page.locator("input").all()
                for inp in inputs:
                    try:
                        val = inp.get_attribute("value") or ""
                        print(f"  Input trouvé: '{val}'")
                    except:
                        pass
                page.screenshot(path="debug_no_button.png", full_page=True)
                envoyer_telegram("❌ Bouton des notes introuvable")
                return

            # Attendre que la page des notes charge
            print("Chargement de la page des notes...")
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_selector("table", timeout=30000)

            # --- EXTRACTION DES NOTES ---
            print("Extraction des notes...")
            page.screenshot(path="debug_notes_page.png", full_page=True)
            
            notes_actuelles = {}

            tables = page.locator("table").all()
            print(f"Nombre de tableaux trouvés: {len(tables)}")
            
            for table in tables:
                rows = table.locator("tr").all()
                for row in rows:
                    cells = row.locator("td").all()
                    if len(cells) >= 3:
                        matiere = " ".join(cells[1].inner_text().split())
                        note = cells[2].inner_text().strip()
                        if matiere and matiere.lower() not in ["matière", "matiere", ""]:
                            notes_actuelles[matiere] = note
                            print(f"  -> {matiere}: {note}")

            if notes_actuelles:
                print(f"\n✅ {len(notes_actuelles)} notes extraites")
                comparer_et_notifier(notes_actuelles)
            else:
                print("⚠️ Aucune note trouvée dans les tableaux.")
                envoyer_telegram("⚠️ Aucune note trouvée sur l'extranet.")

        except PlaywrightTimeoutError as e:
            page.screenshot(path="timeout_error.png", full_page=True)
            print(f"Timeout Playwright. URL: {page.url}")
            print(f"Détails: {e}")
            envoyer_telegram("❌ *Erreur INSA* : délai dépassé (timeout).")

        except Exception as e:
            page.screenshot(path="error.png", full_page=True)
            print(f"Erreur technique : {e}")
            print(f"URL: {page.url}")
            envoyer_telegram(f"❌ *Erreur INSA* : {str(e)[:100]}")

        finally:
            browser.close()

# --- LANCEMENT ---
if __name__ == "__main__":
    executer()
