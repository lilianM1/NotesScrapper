import os
import json
import asyncio
import logging
import re
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configuration du logging pour suivre l'activité du bot
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Récupération des variables d'environnement (configurées dans ton fichier .env)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
INSA_USER = os.environ.get("INSA_USER")
INSA_PWD = os.environ.get("INSA_PWD")
NOTES_FILE = "notes.json"
CHECK_INTERVAL = 300  # Vérification toutes les 5 minutes (300 secondes)

# === UTILITAIRES DE DONNÉES ===

def load_notes():
    """Charge les notes depuis le fichier JSON avec gestion d'erreurs d'encodage."""
    if not os.path.exists(NOTES_FILE):
        return {}
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            with open(NOTES_FILE, "r", encoding=enc) as f:
                return json.load(f)
        except Exception:
            continue
    return {}

def save_notes(notes):
    """Sauvegarde les notes dans le format hiérarchique UE -> matieres -> moyenne."""
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)

def clean_subject_name(raw_name):
    """Nettoie le nom des matières pour l'affichage (enlève les codes et coefficients)."""
    # Enlève les coefficients type (1,5)
    name = re.sub(r"\s*\(\d+(?:,\d+)?\)", "", raw_name)
    # Enlève les préfixes UE si présents
    if ' - ' in name:
        name = name.split(' - ')[0]
    if '-' in name:
        parts = name.split('-')
        name = parts[-1].strip()
    return name

# === COMMANDES TELEGRAM ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche le menu d'aide."""
    msg = (
        "🎓 *Bot INSA Notes*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📚 /notes - Voir toutes les notes par UE\n"
        "📈 /stats - Moyennes par UE\n"
        "⏳ /attente - Notes non encore parues\n"
        "🔄 /check - Forcer une vérification\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def notes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche la liste complète des notes classées par UE."""
    notes = load_notes()
    if not notes:
        await update.message.reply_text("❌ Aucune donnée disponible. Lancez /check.")
        return

    msg = "📊 *VOS NOTES PAR UE*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for ue, data in notes.items():
        msg += f"🔹 *{ue}*\n"
        moy_ue = data.get('moyenne', '-')
        msg += f"  _Moyenne UE: {moy_ue}/20_\n"
        
        for mat, note in data.get('matieres', {}).items():
            status = "✅" if note and note not in ["-", ""] else "⏳"
            msg += f"  {status} {clean_subject_name(mat)} : *{note}*\n"
        msg += "\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche uniquement les moyennes par UE."""
    notes = load_notes()
    if not notes:
        await update.message.reply_text("❌ Aucune donnée.")
        return

    msg = "📈 *RÉSUMÉ DES MOYENNES*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for ue, data in notes.items():
        moy = data.get('moyenne', '-')
        count = len([n for n in data.get('matieres', {}).values() if n and n not in ["-", ""]])
        total = len(data.get('matieres', {}))
        msg += f"• *{ue}* : `{moy}/20` ({count}/{total} notes parues)\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def attente_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Liste les matières dont la note n'est pas encore disponible."""
    notes = load_notes()
    attente_list = []
    
    for ue, data in notes.items():
        for mat, note in data.get('matieres', {}).items():
            if not note or note in ["-", ""]:
                attente_list.append((ue, clean_subject_name(mat)))

    if not attente_list:
        await update.message.reply_text("✅ Toutes les notes sont publiées !")
        return

    msg = "⏳ *NOTES EN ATTENTE*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    for ue, mat in attente_list:
        msg += f"• {mat} _({ue})_\n"
    
    msg += f"\nTotal : {len(attente_list)} matières en attente."
    await update.message.reply_text(msg, parse_mode="Markdown")

async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force un scraping immédiat."""
    await update.message.reply_text("🔄 Connexion à l'extranet en cours...")
    changes = await run_scraper()
    if changes:
        await update.message.reply_text(f"🔔 {len(changes)} nouvelle(s) note(s) trouvée(s) !")
    else:
        await update.message.reply_text("✅ Aucune modification détectée.")

# === SCRAPER (PLAYWRIGHT) ===

async def run_scraper():
    """Scrape l'extranet et retourne la liste des nouvelles notes."""
    from playwright.async_api import async_playwright
    
    old_notes = load_notes()
    new_ue_structure = {}
    changes = []

    try:
        async with async_playwright() as p:
            # Lancement du navigateur en mode headless (sans fenêtre)
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Connexion à l'extranet
            await page.goto("https://extranet.insa-strasbourg.fr/", timeout=60000)
            if await page.locator("#username").is_visible(timeout=5000):
                await page.fill("#username", INSA_USER)
                await page.fill("#password", INSA_PWD)
                await page.click("button[type='submit'], input[type='submit']")

            await page.wait_for_load_state("networkidle")

            # Navigation vers la page des notes du semestre
            # On cherche le bouton qui contient 'semestre'
            bouton = page.locator("input[value*='semestre']")
            if await bouton.count() > 0:
                await bouton.first.click()
            
            await page.wait_for_selector("table", timeout=15000)

            # Analyse des tables de notes
            tables = await page.locator("table").all()
            for table in tables:
                rows = await table.locator("tr").all()
                current_ue = None
                
                for row in rows:
                    cells = await row.locator("td").all()
                    texts = [ (await c.inner_text()).strip() for c in cells ]
                    
                    if not texts: continue

                    # Détection d'une ligne de titre d'UE
                    if len(texts) == 1 and texts[0].startswith("UE-"):
                        current_ue = texts[0]
                        if current_ue not in new_ue_structure:
                            new_ue_structure[current_ue] = {"matieres": {}, "moyenne": "-"}
                    
                    # Détection d'une ligne de matière (3 colonnes)
                    elif len(texts) == 3 and current_ue:
                        if texts[1].lower() in ["matière", "matiere"]: continue
                        
                        matiere_nom = texts[1]
                        note_val = texts[2]
                        new_ue_structure[current_ue]["matieres"][matiere_nom] = note_val
                        
                        # Comparaison avec les anciennes notes pour les notifications
                        old_val = old_notes.get(current_ue, {}).get("matieres", {}).get(matiere_nom)
                        if note_val and note_val != "-" and note_val != old_val:
                            changes.append({"ue": current_ue, "mat": matiere_nom, "val": note_val})

                    # Détection de la ligne de moyenne d'UE (2 colonnes)
                    elif len(texts) == 2 and current_ue and "moyenne" in texts[0].lower():
                        new_ue_structure[current_ue]["moyenne"] = texts[1]

            await browser.close()
            
            if new_ue_structure:
                save_notes(new_ue_structure)
                return changes
                
    except Exception as e:
        logger.error(f"Erreur Scraper: {e}")
    return []

# === TÂCHE PLANIFIÉE ===

async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
    """Vérification automatique périodique."""
    logger.info("Lancement de la vérification automatique...")
    changes = await run_scraper()
    if changes:
        msg = "🎉 *NOUVELLES NOTES DÉTECTÉES !*\n\n"
        for c in changes:
            msg += f"📍 *{c['ue']}*\n"
            msg += f"📚 {clean_subject_name(c['mat'])}\n"
            msg += f"➡️ Note : *{c['val']}*\n\n"
        
        await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="Markdown")

# === POINT D'ENTRÉE ===

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Tokens manquants. Vérifiez votre fichier .env")
        return

    # Initialisation de l'application Telegram
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Ajout des gestionnaires de commandes
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("notes", notes_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("attente", attente_cmd))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(CommandHandler("help", start))

    # Configuration de la tâche répétitive
    app.job_queue.run_repeating(scheduled_check, interval=CHECK_INTERVAL, first=10)

    logger.info("Le bot a démarré avec succès.")
    
    # Lancement du polling (écoute des messages)
    app.run_polling()

if __name__ == "__main__":
    main()