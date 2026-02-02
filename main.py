def get_ue_grouping():
    """Regroupe les matières par UE en se basant sur le nom UE dans le tableau."""
    notes = load_notes()
    ue_matieres = {}
    ue_courante = None
    for matiere in notes.keys():
        # Si la matière commence par 'UE-', c'est une UE
        if matiere.startswith("UE-"):
            ue_courante = matiere
            if ue_courante not in ue_matieres:
                ue_matieres[ue_courante] = []
        elif ue_courante:
            ue_matieres[ue_courante].append(matiere)
    return ue_matieres
import os
import json
import asyncio
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
def format_ue():
    """Liste toutes les UE et leur moyenne si dispo"""
    notes = load_notes()
    if not notes:
        return "❌ Aucune donnée."

    # Regroupe par préfixe de code matière (avant le deuxième tiret)
    import re
    notes = load_notes()
    msg = "📚 *Liste des UE*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    for ue, bloc in notes.items():
        if isinstance(bloc, dict):
            msg += f"*{ue}*\n"
            msg += f"Moyenne UE : {bloc.get('moyenne', '-')}/20\n"
            for mat, note in bloc.get('matieres', {}).items():
                msg += f"  • {mat} : {note}\n"
            msg += "\n"
        else:
            msg += f"*{ue}* (format inattendu)\n"
            msg += f"  Donnée brute : {bloc}\n\n"
    if not notes:
        msg += "Aucune UE trouvée."
    return msg
async def ue_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_ue(), parse_mode="Markdown")
import os
import json
import asyncio
import logging
from datetime import datetime

# Logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
NOTES_FILE = "notes.json"
CHECK_INTERVAL = 300  # 5 minutes

def load_notes():
    """Charge les notes"""
    if not os.path.exists(NOTES_FILE):
        return {}
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            with open(NOTES_FILE, "r", encoding=enc) as f:
                return json.load(f)
        except:
            continue
    return {}

def save_notes(notes):
    """Sauvegarde les notes"""
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)

    # ...rien d'autre ici...

def format_notes():
    """Formate les notes pour Telegram"""
    notes = load_notes()
    if not notes:
        return "❌ Aucune note enregistrée."

    dispo = [(m, n) for m, n in notes.items() if n and n.strip() and n != "-"]
    attente = [(m, n) for m, n in notes.items() if not n or not n.strip() or n == "-"]

    msg = "📊 *VOS NOTES*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if dispo:
        import re
        for matiere, note in dispo:
            # Extraction du coef si présent dans le nom
            coef_match = re.search(r"\((\d+(?:,\d+)?)\)", matiere)
            coef = coef_match.group(1) if coef_match else "?"
            # Nom de la matière sans code UE, sans coef, sans tiret final
            nom = re.sub(r"\s*\(\d+(?:,\d+)?\)", "", matiere)  # retire le coef
            nom = nom.rstrip(" -")  # retire le tiret final
            # Si c'est un stage, garder le nom complet
            if "Stage" in nom or "stage" in nom:
                pass  # nom déjà complet
            elif '-' in nom:
                nom = nom.split('-')[-1].strip()
            msg += f"📚 {nom}\n      Note: {note} │ Coef: {coef}\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"⏳ En attente: {len(attente)} matières\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📈 {len(dispo)}/{len(notes)} notes disponibles"
    return msg
            
def format_stats():
    """Statistiques"""
    notes = load_notes()
    if not notes:
        return "❌ Aucune donnée."

    dispo = [(m, n) for m, n in notes.items() if n and n.strip() and n != "-"]
    ue_dict = {}
    import re
    for matiere, note in dispo:
        # Cherche le code UE au début du nom (ex: UE-GEC-STM-GE-01)
        ue_match = re.match(r"(UE-[A-Z0-9-]+)", matiere)
        if ue_match:
            ue = ue_match.group(1)
        else:
            ue = "Autres"
        try:
            v = float(note.replace(",", "."))
        except:
            continue
        if ue not in ue_dict:
            ue_dict[ue] = []
        ue_dict[ue].append(v)

    msg = "� *MOYENNES PAR UE*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    for ue, notes_ue in ue_dict.items():
        if notes_ue:
            moyenne = sum(notes_ue) / len(notes_ue)
            msg += f"• {ue} : *{moyenne:.2f}/20* ({len(notes_ue)} notes)\n"

    if not ue_dict:
        msg += "Aucune note disponible pour calculer les moyennes."

    return msg

def format_attente():
    """Liste des matières en attente"""
    notes = load_notes()
    if not notes:
        return "❌ Aucune donnée."
    
    attente = [(m, n) for m, n in notes.items() if not n or not n.strip() or n == "-"]
    
    if not attente:
        return "✅ Toutes les notes sont disponibles !"
    
    msg = "⏳ *NOTES EN ATTENTE*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for mat, _ in attente:
        parts = mat.split(" - ")
        if len(parts) >= 2:
            segments = parts[0].split("-")
            nom = segments[-1].strip() if len(segments) > 1 else parts[0]
            coef = parts[-1].replace("(", "").replace(")", "").strip()
        else:
            nom = mat
            coef = "?"
        
        if len(nom) > 25:
            nom = nom[:22] + "..."
        
        msg += f"• {nom} (coef {coef})\n"
    
    msg += f"\n📊 *{len(attente)}* matières en attente"
    return msg

# === COMMANDES TELEGRAM ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎓 *Bot INSA Notes*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📚 /notes - Voir vos notes\n"
        "📈 /stats - Statistiques\n"
        "⏳ /attente - Notes en attente\n"
        "🔄 /check - Forcer une vérification\n"
        "❓ /help - Aide\n\n"
        "_Vérification auto toutes les 5 min_",
        parse_mode="Markdown"
    )

async def notes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_notes(), parse_mode="Markdown")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_stats(), parse_mode="Markdown")

async def attente_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_attente(), parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Aide - Bot INSA Notes*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📚 /notes - Liste de vos notes\n"
        "📈 /stats - Moyenne, min, max\n"
        "⏳ /attente - Matières sans note\n"
        "🔄 /check - Vérifier maintenant\n\n"
        "_Le bot vérifie automatiquement_\n"
        "_vos notes toutes les 5 minutes._",
        parse_mode="Markdown"
    )

async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Vérification en cours...")
    changes = await run_scraper()
    if changes:
        await update.message.reply_text(f"✅ {len(changes)} nouvelle(s) note(s) détectée(s) !")
    else:
        await update.message.reply_text("✅ Aucune nouvelle note.")

# === SCRAPER ===

async def run_scraper():
    """Exécute le scraper et retourne les changements"""
    from playwright.async_api import async_playwright
    
    INSA_USER = os.environ.get("INSA_USER")
    INSA_PWD = os.environ.get("INSA_PWD")
    
    old_notes = load_notes()
    new_notes = {}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Connexion
            await page.goto("https://extranet.insa-strasbourg.fr/", timeout=60000)

            try:
                if await page.locator("#username").is_visible(timeout=3000):
                    await page.fill("#username", INSA_USER)
                    await page.fill("#password", INSA_PWD)
                    await page.click("button[type='submit'], input[type='submit']")
            except:
                pass

            await page.wait_for_load_state("networkidle", timeout=30000)

            # Clic sur notes
            bouton = page.locator("input[value*='1er semestre']")
            if await bouton.is_visible(timeout=5000):
                await bouton.click()

            await page.wait_for_load_state("networkidle", timeout=30000)
            await page.wait_for_selector("table", timeout=30000)

            # Extraction
            tables = await page.locator("table").all()
            logger.info(f"Nombre de tables trouvées : {len(tables)}")
            ue_notes = {}
            for idx, table in enumerate(tables):
                rows = await table.locator("tr").all()
                logger.info(f"Table {idx+1} : {len(rows)} lignes")
                ue_name = None
                ue_moyenne = "-"
                matieres = {}
                for r_idx, row in enumerate(rows):
                    cells = await row.locator("td").all()
                    cell_texts = [await c.inner_text() for c in cells]
                    logger.info(f"Table {idx+1}, ligne {r_idx+1} : {cell_texts}")
                    # Si la ligne a une seule cellule et commence par UE-
                    if len(cells) == 1:
                        txt = cell_texts[0].strip()
                        if txt.startswith("UE-"):
                            ue_name = txt
                    # Si la ligne a 3 cellules, c'est une matière
                    elif len(cells) == 3 and ue_name:
                        matiere = " ".join(cell_texts[1].split())
                        note = cell_texts[2].strip()
                        if matiere and matiere.lower() not in ["matière", "matiere", ""]:
                            matieres[matiere] = note
                    # Si la ligne a 2 cellules, c'est la moyenne UE (colonne de droite)
                    elif len(cells) == 2 and ue_name:
                        moy = cell_texts[1].strip()
                        if moy:
                            ue_moyenne = moy
                # Si on a trouvé une UE et des matières
                if ue_name and matieres:
                    ue_notes[ue_name] = {"matieres": matieres, "moyenne": ue_moyenne}
            await browser.close()

            new_notes = ue_notes

    except Exception as e:
        logger.error(f"Erreur scraping: {e}")
        return []

    # Trouver les changements
    changes = []
    for ue, bloc in new_notes.items():
        for mat, note in bloc["matieres"].items():
            old = old_notes.get(ue, {}).get("matieres", {}).get(mat)
            if note and note != "-" and (not old or note != old):
                changes.append({"matiere": mat, "ancienne": old, "nouvelle": note})

    # Log du contenu extrait
    logger.info(f"Contenu extrait (new_notes): {json.dumps(new_notes, ensure_ascii=False, indent=2)}")

    # Sauvegarder
    if new_notes:
        save_notes(new_notes)

    return changes

# === TÂCHE AUTOMATIQUE ===

async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
    """Vérification programmée"""
    logger.info("🔄 Vérification automatique...")
    
    try:
        changes = await run_scraper()
        
        if changes:
            msg = "🎉 *NOUVELLES NOTES !*\n"
            msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for c in changes:
                # Extraire nom court
                parts = c['matiere'].split(" - ")
                if len(parts) >= 2:
                    segments = parts[0].split("-")
                    nom = segments[-1].strip() if len(segments) > 1 else parts[0]
                    coef = parts[-1].replace("(", "").replace(")", "").strip()
                else:
                    nom = c['matiere'][:30]
                    coef = "?"
                
                msg += f"📚 *{nom}*\n"
                msg += f"      Note: *{c['nouvelle']}* │ Coef: {coef}\n\n"
            
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=msg,
                parse_mode="Markdown"
            )
            logger.info(f"✅ {len(changes)} nouvelle(s) note(s)")
        else:
            logger.info("✅ RAS")
            
    except Exception as e:
        logger.error(f"Erreur: {e}")

# === MAIN ===

def main():
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN manquant !")
        return
    
    # Créer l'application
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Commandes
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("notes", notes_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("ue", ue_cmd))
    app.add_handler(CommandHandler("attente", attente_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("check", check_cmd))
    
    # Job toutes les 5 minutes
    app.job_queue.run_repeating(
        scheduled_check,
        interval=CHECK_INTERVAL,
        first=10  # Premier check après 10 secondes
    )
    
    logger.info("🚀 Bot démarré ! Vérification toutes les 5 min.")
    
    # Lancer le bot (polling)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
