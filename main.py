import asyncio
import logging
import os
import json
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# Charger le fichier .env AVANT TOUT LE RESTE
from dotenv import load_dotenv
load_dotenv()

# Maintenant on peut charger insa_bot, car les variables d'environnement existent !
import insa_bot


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
    # Sécurité : Vérification de l'utilisateur autorisé
    if AUTHORIZED_USER_ID and str(update.effective_chat.id) != str(AUTHORIZED_USER_ID):
        await update.message.reply_text("⛔ Accès refusé.")
        return

    # Charge le fichier JSON propre généré par insa_bot
    if not os.path.exists("notes.json"):
        await update.message.reply_text("📂 Pas encore de notes.")
        return

    with open("notes.json", "r", encoding="utf-8") as f:
        notes = json.load(f)

    notes_dispo = {}
    notes_attente = []

    for nom, data in notes.items():
        if isinstance(data, dict):
            note = data.get("note", "-")
            coef = data.get("coef", "?")
        else:
            note = str(data)
            coef = "?"
        
        if note in ["-", "", None]:
            notes_attente.append(nom)
        else:
            notes_dispo[nom] = {"n": note, "c": coef}

    # --- AFFICHAGE IDENTIQUE A LA DEMANDE ---
    msg = "📊 *VOS NOTES*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if notes_dispo:
        for nom, info in notes_dispo.items():
            msg += f"📚 *{nom}*\n"
            msg += f"      Note: *{info['n']}* │ Coef: {info['c']}\n\n"
    else:
        msg += "🚫 _Aucune note pour l'instant._\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    if notes_attente:
        msg += f"⏳ *En attente:* {len(notes_attente)} matières\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        
    msg += f"📈 *{len(notes_dispo)}/{len(notes)}* notes disponibles"

    await update.message.reply_text(msg, parse_mode="Markdown")

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

    await update.message.reply_text("🔎 Vérification des notes lancée...")

    # Charger les notes avant scraping
    notes_avant = {}
    if os.path.exists("notes.json"):
        with open("notes.json", "r", encoding="utf-8") as f:
            notes_avant = json.load(f)

    success = await run_scraping()

    # Charger les notes après scraping
    notes_apres = {}
    if os.path.exists("notes.json"):
        with open("notes.json", "r", encoding="utf-8") as f:
            notes_apres = json.load(f)

    # Détecter les nouvelles notes
    nouvelles_notes = []
    for nom, data in notes_apres.items():
        note_apres = data.get("note") if isinstance(data, dict) else data
        note_avant = notes_avant.get(nom, {}).get("note") if isinstance(notes_avant.get(nom), dict) else notes_avant.get(nom)
        if (note_apres not in ["-", "", None]) and (note_avant in ["-", "", None, None] or nom not in notes_avant):
            nouvelles_notes.append(nom)

    if success:
        if nouvelles_notes:
            msg = "🎉 Nouvelle(s) note(s) détectée(s) :\n"
            for nom in nouvelles_notes:
                note = notes_apres[nom].get("note") if isinstance(notes_apres[nom], dict) else notes_apres[nom]
                coef = notes_apres[nom].get("coef", "?") if isinstance(notes_apres[nom], dict) else "?"
                msg += f"• *{nom}* : {note} (coef {coef})\n"
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text("✅ Vérification terminée. Pas de nouvelle note.")
    else:
        await update.message.reply_text("❌ Erreur lors de la vérification.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 *Stats Bot*\n"
        f"Dernier check : {last_check_time}\n"
        f"Status : En ligne 🟢",
        parse_mode="Markdown"
    )

async def ue_moyenne(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Fonction à implémenter si nécessaire
    await update.message.reply_text("⚙️ Fonction UE Moyenne en cours de développement.")

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
    application.add_handler(CommandHandler("ue", ue_moyenne))

    # REMPLACEMENT APSCHEDULER PAR JOBQUEUE DU BOT
    # check toutes les 300 secondes (5 minutes)
    if application.job_queue:
        application.job_queue.run_repeating(scheduled_job, interval=300, first=10)
        print("⏰ Planificateur intégré activé (5min)")

    # Lancement du bot
    print("✅ Bot prêt à recevoir des commandes.")
    application.run_polling()

if __name__ == '__main__':
    main()
