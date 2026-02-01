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

# --- VÉRIFICATION DES VARIABLES ---
def verifier_config():
    manquantes = []
    if not TOKEN:
        manquantes.append("TELEGRAM_TOKEN")
    if not CHAT_ID:
        manquantes.append("TELEGRAM_CHAT_ID")
    if not USERNAME:
        manquantes.append("INSA_USER")
    if not PASSWORD:
        manquantes.append("INSA_PWD")
    
    if manquantes:
        raise ValueError(f"Variables d'environnement manquantes : {', '.join(manquantes)}")

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
    verifier_config()  # Ajoutez cette ligne au début
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            print("Connexion à l'extranet INSA...")
            page.goto(
                "https://extranet.insa-strasbourg.fr/",
                wait_until="networkidle",
                timeout=60000
            )

            # --- LOGIN CAS ---
            if "cas" in page.url:
                print("Authentification CAS...")
                page.fill("#username", USERNAME)
                page.fill("#password", PASSWORD)
                page.keyboard.press("Enter")

                page.wait_for_selector(
                    "text=Consulter vos notes",
                    timeout=30000
                )

            # --- ACCÈS AUX NOTES ---
            print("Ouverture des notes du 1er semestre...")
            bouton = page.locator("input[value*='1er semestre']").first
            bouton.click(force=True)

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
