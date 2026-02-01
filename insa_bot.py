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

        # Nouvelle note
        if ancienne is None and note != "-":
            changements.append(f"📚 *{matiere}*\n➡️ Nouvelle note : *{note}*")

        # Note publiée ou modifiée
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
        # Ajout d'un user_agent pour éviter d'être détecté comme un robot basique
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
        page = context.new_page()

        try:
            print("Connexion à l'extranet INSA...")
            page.goto("https://extranet.insa-strasbourg.fr/", wait_until="domcontentloaded", timeout=60000)

            # --- LOGIN CAS ---
            if "cas" in page.url:
                print("Authentification CAS...")
                page.fill("#username", USERNAME)
                page.fill("#password", PASSWORD)
                page.keyboard.press("Enter")
                
                # ATTENDRE QUE LA PAGE CHARGE COMPLÈTEMENT
                # "networkidle" attend qu'il n'y ait plus de trafic réseau pendant 500ms
                page.wait_for_load_state("networkidle", timeout=60000)

            # --- ACCÈS AUX NOTES ---
            print("Recherche du bouton des notes...")
            # On utilise un sélecteur qui cherche n'importe quel input contenant "semestre"
            selector_bouton = "input[value*='semestre']"

            try:
                # Attendre que l'élément soit réellement présent et cliquable
                page.wait_for_selector(selector_bouton, state="visible", timeout=45000)
                print("Bouton trouvé, clic...")
                page.locator(selector_bouton).first.click(force=True)
            except Exception as e:
                print(f"Le bouton n'a pas été trouvé. URL actuelle : {page.url}")
                page.screenshot(path="debug_bouton.png", full_page=True)
                raise e
            
            page.wait_for_selector(selector_bouton, state="visible", timeout=30000)
            print("Bouton trouvé, clic en cours...")
            
            # Forcer le clic si un élément invisible est devant
            page.locator(selector_bouton).first.click(force=True)

            # Attendre que le tableau des notes apparaisse
            page.wait_for_selector("table", timeout=30000)

            # --- EXTRACTION DES NOTES ---
            print("Extraction des notes...")
            notes_actuelles = {}

            tables = page.locator("table").all()
            for table in tables:
                rows = table.locator("tr").all()
                for row in rows:
                    cells = row.locator("td").all()
                    if len(cells) >= 3:
                        matiere = " ".join(cells[1].inner_text().split())
                        note = cells[2].inner_text().strip()
                        if matiere:
                            notes_actuelles[matiere] = note

            comparer_et_notifier(notes_actuelles)

        except PlaywrightTimeoutError:
            page.screenshot(path="timeout_error.png", full_page=True)
            envoyer_telegram("❌ *Erreur INSA* : délai dépassé (timeout).")
            page.screenshot(path="timeout_error.png", full_page=True)
            print("Timeout Playwright.")

        except Exception as e:
            page.screenshot(path="error.png", full_page=True)
            envoyer_telegram("❌ *Erreur INSA* : script interrompu.")
            print(f"Erreur technique : {e}")

        finally:
            browser.close()

# --- LANCEMENT ---
if __name__ == "__main__":
    executer()
