"""
bot.py — Point d'entrée principal du bot Telegram de suivi budgétaire.

Fonctionnement :
  - Seul l'utilisateur whitelisté (TELEGRAM_USER_ID) est traité
  - Toute photo reçue déclenche l'extraction via Claude Vision
  - Commandes disponibles : /bilan /graphique /transactions /budget /reset_mois /sante

Lancement : python bot.py
"""

from __future__ import annotations

import io
import logging
import logging.handlers
import os
import platform
import shutil
import sys
import time
import calendar
from datetime import datetime, time as dtime
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config  # noqa: F401 — charge les variables d'env en premier
from budget import MONTHLY_BUDGETS, compute_bilan, format_bilan, load_budgets, load_global_budget, load_income_cats
from charts import generate_burndown_chart
from classifier import classify
from extractor import (
    extract_transactions_from_image,
    extract_transactions_from_pdf,
    extract_transactions_from_text,
)
from storage import (
    add_transactions,
    count_transactions,
    get_transactions_for_month,
    load_transactions,
    reset_month,
)

# ── Logging avec rotation ─────────────────────────────────────────────────────
LOG_FILE = Path(__file__).parent / "budget-bot.log"

_handler_file = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_handler_console = logging.StreamHandler(sys.stdout)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[_handler_file, _handler_console],
)
logger = logging.getLogger(__name__)

# Horodatage de démarrage (pour /sante)
_START_TIME = time.monotonic()


# ── Décorateur de sécurité : whitelist stricte ────────────────────────────────

def _authorized(update: Update) -> bool:
    """Vérifie que le message provient de l'utilisateur autorisé."""
    return update.effective_user is not None and update.effective_user.id == config.TELEGRAM_USER_ID


async def _reject(update: Update) -> None:
    """Rejette un message non autorisé avec un message d'erreur."""
    uid  = update.effective_user.id if update.effective_user else "?"
    user = update.effective_user.username or str(uid)
    logger.warning("Message refusé de @%s (id=%s)", user, uid)
    await update.message.reply_text("⛔ Accès non autorisé.")


# ── Pipeline commun ───────────────────────────────────────────────────────────

async def _process_and_reply(update: Update, raw_transactions: list[dict]) -> None:
    """Classification + stockage + réponse — partagé entre tous les handlers."""
    if not raw_transactions:
        await update.message.reply_text(
            "⚠️ Aucune transaction détectée.\n"
            "Vérifiez que le document contient bien un relevé bancaire."
        )
        return

    for tx in raw_transactions:
        tx["category"] = await classify(tx["label"])

    added, skipped = add_transactions(raw_transactions)

    lines = [f"✅ <b>{added} transaction(s) ajoutée(s)</b>"]
    if skipped:
        lines.append(f"   ↩️ {skipped} doublon(s) ignoré(s)")

    stored = {tx["transaction_id"]: tx for tx in load_transactions()}
    for tx in raw_transactions:
        t = stored.get(tx["transaction_id"])
        if t and t.get("added_at"):
            lines.append(f"• {t['label']} — {t['amount']:.2f} € → {t['category']}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# ── Handler photo ─────────────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Photo → Claude Vision → transactions."""
    if not _authorized(update):
        await _reject(update)
        return

    await update.message.reply_text("📸 Image reçue, analyse en cours...")

    buf = io.BytesIO()
    await (await update.message.photo[-1].get_file()).download_to_memory(buf)

    try:
        raw = await extract_transactions_from_image(buf.getvalue(), "image/jpeg")
    except RuntimeError as exc:
        logger.error("Erreur extraction image : %s", exc)
        await update.message.reply_text(
            f"❌ Erreur analyse image :\n<code>{exc}</code>", parse_mode=ParseMode.HTML
        )
        return

    await _process_and_reply(update, raw)


# ── Handler PDF ───────────────────────────────────────────────────────────────

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """PDF ou document texte → extraction Claude → transactions."""
    if not _authorized(update):
        await _reject(update)
        return

    doc      = update.message.document
    filename = (doc.file_name or "").lower()
    mime     = (doc.mime_type or "").lower()

    is_pdf  = filename.endswith(".pdf") or mime == "application/pdf"
    is_text = (
        filename.endswith((".txt", ".csv"))
        or mime in ("text/plain", "text/csv")
    )

    if not is_pdf and not is_text:
        await update.message.reply_text(
            "⚠️ Format non supporté. Envoie un <b>PDF</b> ou un fichier <b>.txt/.csv</b>.",
            parse_mode=ParseMode.HTML,
        )
        return

    icon  = "📄" if is_pdf else "📝"
    label = "PDF" if is_pdf else "fichier texte"
    await update.message.reply_text(f"{icon} {label} reçu, analyse en cours...")

    buf = io.BytesIO()
    await (await doc.get_file()).download_to_memory(buf)
    content = buf.getvalue()

    try:
        if is_pdf:
            raw = await extract_transactions_from_pdf(content)
        else:
            raw = await extract_transactions_from_text(content.decode("utf-8", errors="replace"))
    except RuntimeError as exc:
        logger.error("Erreur extraction document : %s", exc)
        await update.message.reply_text(
            f"❌ Erreur analyse {label} :\n<code>{exc}</code>", parse_mode=ParseMode.HTML
        )
        return

    await _process_and_reply(update, raw)


# ── Handler texte libre ───────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Texte collé directement dans le chat → extraction Claude.
    Ignoré si le message est trop court (probablement une question, pas un relevé).
    """
    if not _authorized(update):
        await _reject(update)
        return

    text = update.message.text or ""
    if len(text.strip()) < 20:
        await update.message.reply_text(
            "💬 Pour extraire des transactions, envoie :\n"
            "• Une <b>photo</b> de ton relevé\n"
            "• Un <b>PDF</b>\n"
            "• Du <b>texte copié</b> depuis ton relevé (min. 20 caractères)\n\n"
            "Ou utilise /start pour voir les commandes.",
            parse_mode=ParseMode.HTML,
        )
        return

    await update.message.reply_text("📝 Texte reçu, analyse en cours...")

    try:
        raw = await extract_transactions_from_text(text)
    except RuntimeError as exc:
        logger.error("Erreur extraction texte : %s", exc)
        await update.message.reply_text(
            f"❌ Erreur analyse texte :\n<code>{exc}</code>", parse_mode=ParseMode.HTML
        )
        return

    await _process_and_reply(update, raw)


# ── Commandes ─────────────────────────────────────────────────────────────────

async def cmd_bilan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/bilan — Bilan texte des dépenses du mois courant."""
    if not _authorized(update):
        await _reject(update)
        return

    now   = datetime.now()
    txs   = get_transactions_for_month(now.year, now.month)
    bilan = compute_bilan(txs)

    _FR_MONTHS = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    label = f"{_FR_MONTHS[now.month]} {now.year}"

    await update.message.reply_text(
        format_bilan(bilan, label),
        parse_mode=ParseMode.HTML,
    )


async def cmd_graphique(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/graphique — Envoie le burndown chart PNG du mois courant."""
    if not _authorized(update):
        await _reject(update)
        return

    await update.message.reply_text("📈 Génération du graphique...")

    now = datetime.now()
    txs = get_transactions_for_month(now.year, now.month)

    try:
        png_bytes = generate_burndown_chart(txs, now.year, now.month)
    except Exception as exc:
        logger.error("Erreur génération graphique : %s", exc)
        await update.message.reply_text(f"❌ Erreur graphique : {exc}")
        return

    await update.message.reply_photo(
        photo=io.BytesIO(png_bytes),
        caption=f"📊 Burndown chart — {now.strftime('%B %Y')}",
    )


async def cmd_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/transactions [N] — Affiche les N dernières transactions (défaut : 10)."""
    if not _authorized(update):
        await _reject(update)
        return

    # Lire l'argument optionnel (nombre de transactions à afficher)
    n = 10
    if context.args:
        try:
            n = max(1, min(int(context.args[0]), 50))
        except ValueError:
            pass

    all_txs = load_transactions()
    recent  = sorted(all_txs, key=lambda t: t.get("date", ""), reverse=True)[:n]

    if not recent:
        await update.message.reply_text("📭 Aucune transaction enregistrée.")
        return

    lines = [f"🧾 <b>{n} dernières transactions</b>\n"]
    for tx in recent:
        lines.append(
            f"<code>{tx['date']}</code>  {tx['label'][:30]:<30}  "
            f"{tx['amount']:>8.2f} €  {tx.get('category', '❓')}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/budget — Affiche les budgets mensuels définis par catégorie."""
    if not _authorized(update):
        await _reject(update)
        return

    lines = ["💰 <b>Budgets mensuels</b>\n"]
    total = 0.0
    for cat, amount in sorted(MONTHLY_BUDGETS.items(), key=lambda x: -x[1]):
        if amount > 0:
            lines.append(f"{cat:<22}: {amount:>6.0f} €")
            total += amount

    lines.append(f"\n<b>Total</b>             : {total:>6.0f} €")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_reset_mois(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/reset_mois — Remet les transactions du mois courant à zéro."""
    if not _authorized(update):
        await _reject(update)
        return

    now     = datetime.now()
    removed = reset_month(now.year, now.month)

    _FR_MONTHS = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    await update.message.reply_text(
        f"🗑️ {removed} transaction(s) de {_FR_MONTHS[now.month]} {now.year} supprimée(s)."
    )


async def cmd_sante(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/sante — État du système Raspberry Pi (uptime, disque, température CPU)."""
    if not _authorized(update):
        await _reject(update)
        return

    # ── Uptime du bot ─────────────────────────────────────────────────────────
    elapsed  = int(time.monotonic() - _START_TIME)
    days     = elapsed // 86400
    hours    = (elapsed % 86400) // 3600
    minutes  = (elapsed % 3600) // 60
    uptime   = f"{days}j {hours}h {minutes}min"

    # ── Espace disque ─────────────────────────────────────────────────────────
    disk     = shutil.disk_usage(Path(__file__).parent)
    free_gb  = disk.free  / 1e9
    total_gb = disk.total / 1e9
    disk_str = f"{free_gb:.1f} Go libres / {total_gb:.1f} Go"

    # ── Température CPU (spécifique Raspberry Pi) ─────────────────────────────
    temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if temp_path.exists():
        try:
            temp_c = int(temp_path.read_text().strip()) / 1000
            temp_str = f"{temp_c:.1f} °C"
        except (OSError, ValueError):
            temp_str = "N/A"
    else:
        temp_str = f"N/A ({platform.system()})"

    # ── Version Python ────────────────────────────────────────────────────────
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    msg = (
        "🩺 <b>Santé du système</b>\n\n"
        f"🤖 Bot actif depuis : {uptime}\n"
        f"💾 Espace disque : {disk_str}\n"
        f"🌡️ Température CPU : {temp_str}\n"
        f"🐍 Python : {py_ver}\n"
        f"📦 Transactions stockées : {count_transactions()}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — Message de bienvenue."""
    if not _authorized(update):
        await _reject(update)
        return

    await update.message.reply_text(
        "👋 <b>Budget Bot actif !</b>\n\n"
        "<b>Pour ajouter des transactions, envoie :</b>\n"
        "📸 Une photo de ton relevé bancaire\n"
        "📄 Un fichier PDF\n"
        "📝 Du texte copié depuis ton relevé\n\n"
        "<b>Commandes :</b>\n"
        "/bilan — Bilan détaillé du mois courant\n"
        "/resume — Résumé rapide (budget + solde)\n"
        "/graphique — Burndown chart\n"
        "/transactions [N] — N dernières transactions\n"
        "/budget — Budgets par catégorie\n"
        "/reset_mois — Remettre le mois à zéro\n"
        "/sante — État du système",
        parse_mode=ParseMode.HTML,
    )




# ── Bilan quotidien automatique (9h00) ───────────────────────────────────────

def _build_resume_msg() -> str:
    """Construit le message de résumé budgétaire du mois en cours."""
    now   = datetime.now()
    txs   = get_transactions_for_month(now.year, now.month)
    bilan = compute_bilan(txs)

    _FR = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
           "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    date_str = f"{now.day:02d} {_FR[now.month]} {now.year}"

    income_cats   = load_income_cats()
    budgets_cfg   = load_budgets()
    income_total  = sum(v for k, v in budgets_cfg.items() if k in income_cats)
    global_budget = load_global_budget()
    ref_budget    = global_budget or sum(v for k, v in budgets_cfg.items() if k not in income_cats and v > 0)
    total_spent   = sum(max(d["spent"], 0) for cat, d in bilan.items() if cat not in income_cats)
    pct_consumed  = (total_spent / ref_budget * 100) if ref_budget else 0

    days_in_month   = calendar.monthrange(now.year, now.month)[1]
    elapsed         = max(now.day, 1)
    total_projected = 0.0
    for cat, data in bilan.items():
        if cat in income_cats:
            continue  # Les revenus ne sont pas des dépenses
        spent  = max(data["spent"], 0)
        budget = data["budget"]
        if budget > 0:
            # Formule 3 : si on dépense plus vite que le budget → extrapole
            # sinon on suppose qu'on atteindra le budget en fin de mois
            total_projected += max(spent, budget)
        else:
            # Pas de budget défini → projection linéaire sur le reste du mois
            total_projected += (spent / elapsed) * days_in_month
    solde = income_total - total_projected

    icon_budget = "✅" if pct_consumed < 70 else "⚠️" if pct_consumed < 90 else "🔴"
    icon_solde  = "💚" if solde >= 0 else "🔴"
    sign_solde  = "+" if solde >= 0 else ""

    lines = [
        f"<b>───── {date_str} ─────</b>",
        f"{icon_budget} Budget consommé : <b>{total_spent:.2f} € / {ref_budget:.0f} €</b> ({pct_consumed:.0f}%)",
        f"{icon_solde} Solde prévisionnel : <b>{sign_solde}{solde:.2f} €</b>",
    ]
    return chr(10).join(lines)


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/resume — Résumé budgétaire rapide du mois en cours."""
    if not _authorized(update):
        await _reject(update)
        return
    await update.message.reply_text(_build_resume_msg(), parse_mode=ParseMode.HTML)


async def daily_bilan(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envoie chaque matin le résumé budgétaire du mois en cours."""
    await context.bot.send_message(
        chat_id=config.TELEGRAM_USER_ID,
        text=_build_resume_msg(),
        parse_mode=ParseMode.HTML,
    )

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Initialise et démarre le bot en mode polling."""
    logger.info("Démarrage du Budget Bot (user_id autorisé : %s)", config.TELEGRAM_USER_ID)

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Commandes
    app.add_handler(CommandHandler("start",        cmd_start))
    app.add_handler(CommandHandler("bilan",        cmd_bilan))
    app.add_handler(CommandHandler("resume",       cmd_resume))
    app.add_handler(CommandHandler("graphique",    cmd_graphique))
    app.add_handler(CommandHandler("transactions", cmd_transactions))
    app.add_handler(CommandHandler("budget",       cmd_budget))
    app.add_handler(CommandHandler("reset_mois",   cmd_reset_mois))
    app.add_handler(CommandHandler("sante",        cmd_sante))

    # Médias
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(
        filters.Document.PDF |
        filters.Document.MimeType("text/plain") |
        filters.Document.MimeType("text/csv") |
        filters.Document.FileExtension("txt") |
        filters.Document.FileExtension("csv"),
        handle_document,
    ))

    # Texte libre (exclure les commandes pour éviter les doublons)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Bilan quotidien à 9h00
    app.job_queue.run_daily(daily_bilan, time=dtime(9, 0, 0))

    logger.info("Bot en écoute (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
