import asyncio
import logging
import os
import json
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
import insa_bot  # Import scraping logic

# --- CONFIGURATION ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
AUTHORIZED_USER_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

last_check_time = "Jamais"

# --- COMMANDES ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bonjour! Je suis le bot INSA Notes.\n\n"
        "Commandes :\n"
        "/notes - Voir les notes enregistrées\n"
        "/check - Forcer une vérification\n"
        "/stats - Infos système"
    )

async def view_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sécurité basique
    if AUTHORIZED_USER_ID and str(update.effective_chat.id) != str(AUTHORIZED_USER_ID):
        await update.message.reply_text("⛔ Accès non autorisé.")
        return

    try:
        if os.path.exists("notes.json"):
            with open("notes.json", "r", encoding="utf-8") as f:
                notes = json.load(f)
        else:
            notes = {}

        if not notes:
            await update.message.reply_text("📂 Aucune note en cache.")
            return

        message = "📚 *Notes actuelles (Cache):*\n\n"
        for matiere, note in notes.items():
            if isinstance(note, dict):
                valeur = note.get('note', note.get('moyenne', str(note)))
            else:
                valeur = str(note)
                
            message += f"• *{matiere}* : `{valeur}`\n"
            
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur lecture : {e}")

async def run_scraping():
    """Fonction principale de scraping (utilitaire)"""
    global last_check_time
    logging.info("⏳ Lancement du scraping...")
    last_check_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    loop = asyncio.get_running_loop()
    try:
        # Exécute le code bloquant (playwright sync) dans un thread à part
        await loop.run_in_executor(None, insa_bot.executer)
        logging.info("✅ Scraping terminé.")
        return True
    except Exception as e:
        logging.error(f"❌ Erreur scraping background: {e}")
        return False

async def scheduled_job(context: ContextTypes.DEFAULT_TYPE):
    """Ce job est appelé automatiquement par le JobQueue du bot"""
    logging.info("⏰ Exécution automatique planifiée.")
    await run_scraping()

async def force_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if AUTHORIZED_USER_ID and str(update.effective_chat.id) != str(AUTHORIZED_USER_ID):
        await update.message.reply_text("⛔")
        return

    await update.message.reply_text("🕵️‍♂️ Vérification des notes lancée...")
    success = await run_scraping()
    if success:
        await update.message.reply_text("✅ Vérification terminée. Tapez /notes pour voir le résultat.")
    else:
        await update.message.reply_text("❌ Erreur lors de la vérification.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 *Stats Bot*\n"
        f"Dernier check : {last_check_time}\n"
        f"Status : En ligne 🟢",
        parse_mode="Markdown"
    )

# --- MAIN ---
def main():
    if not TOKEN:
        print("❌ CRITIQUE : Variable TELEGRAM_TOKEN manquante.")
        return

    print("🚀 Démarrage du bot Telegram...")
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Enregistrement des commandes
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("notes", view_notes))
    application.add_handler(CommandHandler("check", force_check))
    application.add_handler(CommandHandler("stats", stats))

    # REMPLACEMENT APSCHEDULER PAR JOBQUEUE DU BOT
    # check toutes les 1200 secondes (20 minutes)
    if application.job_queue:
        application.job_queue.run_repeating(scheduled_job, interval=1200, first=10)
        print("⏰ Planificateur intégré activé (20min)")

    # Lancement du bot
    print("✅ Bot prêt à recevoir des commandes.")
    application.run_polling()

if __name__ == '__main__':
    main()
