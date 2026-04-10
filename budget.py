"""
budget.py — Budgets mensuels par catégorie et calcul du bilan.

Les budgets sont lus depuis budgets.json s'il existe,
sinon les valeurs par défaut ci-dessous sont utilisées.
L'interface web écrit dans budgets.json via save_budgets().
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# ── Valeurs par défaut ────────────────────────────────────────────────────────
_DEFAULTS: dict[str, float] = {
    "🛒 Supermarché":       400,
    "🥩 Boucherie":          80,
    "🌿 Bio":                60,
    "🛍️ Bazar / Discount":   50,
    "🚚 Livraison surgelés": 40,
    "📱 Abonnement":         60,
    "🎬 Streaming":          20,
    "🍽️ Restaurant":        100,
    "⛽ Carburant":           80,
    "💊 Pharmacie":          30,
    "🏠 Maison":             50,
    "❓ Non classé":           0,
}

# ── Mapping icônes/catégories ───────────────────────────────────────────────
CATEGORY_ICONS: dict[str, str] = {
    "Supermarché": "🛒",
    "Boucherie": "🥩",
    "Bio": "🌿",
    "Bazar / Discount": "🛍️",
    "Livraison surgelés": "🚚",
    "Abonnement": "📱",
    "Streaming": "🎬",
    "Restaurant": "🍽️",
    "Carburant": "⛽",
    "Pharmacie": "💊",
    "Maison": "🏠",
    "Non classé": "❓",
    "Salaire": "💰",
    "Loisirs": "🎮",
    "Vêtements": "👕",
    "Cadeaux": "🎁",
    "Voyage": "✈️",
    "Santé": "🏥",
    "Éducation": "📚",
    "Transport": "🚆",
    "Impôts": "📋",
}


def get_category_with_icon(category: str) -> str:
    """Retourne la catégorie avec son icône."""
    # Extraire le nom sans icône existante
    name = category.replace("🛒", "").replace("🥩", "").replace("🌿", "") \
                   .replace("🛍️", "").replace("🚚", "").replace("📱", "") \
                   .replace("🎬", "").replace("🍽️", "").replace("⛽", "") \
                   .replace("💊", "").replace("🏠", "").replace("❓", "") \
                   .strip()
    
    # Trouver l'icône correspondante
    icon = CATEGORY_ICONS.get(name, "❓")
    return f"{icon} {name}"

_BUDGETS_FILE          = Path(__file__).parent / "budgets.json"
_GLOBAL_BUDGET_FILE    = Path(__file__).parent / "global_budget.json"
_OPENING_BALANCES_FILE = Path(__file__).parent / "opening_balances.json"


def load_budgets() -> dict[str, float]:
    """Charge les budgets depuis budgets.json, ou retourne les valeurs par défaut."""
    if _BUDGETS_FILE.exists():
        try:
            return json.loads(_BUDGETS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULTS)


def save_budgets(budgets: dict[str, float]) -> None:
    """Sauvegarde atomique des budgets dans budgets.json."""
    tmp = Path(str(_BUDGETS_FILE) + ".tmp")
    tmp.write_text(json.dumps(budgets, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _BUDGETS_FILE)


def load_global_budget() -> float | None:
    """Retourne le budget global mensuel, ou None s'il n'est pas défini."""
    if _GLOBAL_BUDGET_FILE.exists():
        try:
            return float(json.loads(_GLOBAL_BUDGET_FILE.read_text(encoding="utf-8")).get("amount", 0)) or None
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    return None


def save_global_budget(amount: float) -> None:
    """Sauvegarde atomique du budget global."""
    tmp = Path(str(_GLOBAL_BUDGET_FILE) + ".tmp")
    tmp.write_text(json.dumps({"amount": amount}), encoding="utf-8")
    os.replace(tmp, _GLOBAL_BUDGET_FILE)


def load_opening_balance(year: int, month: int) -> float | None:
    """Retourne le solde initial du mois, ou None s'il n'est pas défini."""
    if _OPENING_BALANCES_FILE.exists():
        try:
            data = json.loads(_OPENING_BALANCES_FILE.read_text(encoding="utf-8"))
            key  = f"{year:04d}-{month:02d}"
            val  = data.get(key)
            return float(val) if val else None
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    return None


def rename_category_in_budgets(old: str, new: str) -> bool:
    """Renomme une catégorie dans les budgets. Retourne True si trouvée."""
    budgets = load_budgets()
    if old not in budgets:
        return False
    budgets[new] = budgets.pop(old)
    save_budgets(budgets)
    return True


def save_opening_balance(year: int, month: int, amount: float) -> None:
    """Sauvegarde atomique du solde initial d'un mois."""
    data = {}
    if _OPENING_BALANCES_FILE.exists():
        try:
            data = json.loads(_OPENING_BALANCES_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    key = f"{year:04d}-{month:02d}"
    if amount > 0:
        data[key] = amount
    else:
        data.pop(key, None)
    tmp = Path(str(_OPENING_BALANCES_FILE) + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _OPENING_BALANCES_FILE)


# Snapshot des budgets au démarrage — utilisé par bot.py pour les commandes legacy.
# Note : ne se met pas à jour automatiquement si budgets.json change en cours de route.
# Préférer load_budgets() pour toute logique qui doit refléter l'état courant.
MONTHLY_BUDGETS: dict[str, float] = load_budgets()


def compute_bilan(transactions: list[dict]) -> dict[str, dict]:
    """Calcule les totaux nets (débits − crédits) par catégorie.

    Un débit augmente le montant "spent", un crédit le diminue.
    Retourne un dict {catégorie: {spent, budget, pct}} pour toutes
    les catégories qui ont un budget OU des transactions ce mois.
    """
    budgets = load_budgets()
    totals: dict[str, float] = {}
    for tx in transactions:
        cat    = tx.get("category", "❓ Non classé")
        amount = tx["amount"] if tx.get("type", "debit") == "debit" else -tx["amount"]
        totals[cat] = totals.get(cat, 0.0) + amount

    result: dict[str, dict] = {}
    for cat in set(budgets) | set(totals):
        spent  = totals.get(cat, 0.0)
        budget = budgets.get(cat, 0.0)
        pct    = (spent / budget * 100) if budget > 0 else 0.0
        result[cat] = {"spent": spent, "budget": budget, "pct": pct}
    return result


def format_bilan(bilan: dict[str, dict], month_label: str) -> str:
    """Formate le bilan en texte HTML pour Telegram."""
    lines = [f"📊 <b>Bilan du mois — {month_label}</b>\n"]
    total_spent = total_budget = 0.0

    def sort_key(item):
        cat, data = item
        return (1, 0) if cat == "❓ Non classé" else (0, -data["budget"])

    for cat, data in sorted(bilan.items(), key=sort_key):
        spent, budget, pct = data["spent"], data["budget"], data["pct"]
        if spent == 0 and budget == 0:
            continue
        icon = "✅" if pct < 70 else "⚠️" if pct <= 90 else "🔴"
        budget_str = f"{budget:.0f} €" if budget > 0 else "—"
        pct_str    = f"({pct:.0f}%)" if budget > 0 else ""
        lines.append(f"{cat:<22}: {spent:>7.2f} € / {budget_str:<7} {pct_str} {icon}")
        total_spent  += spent
        total_budget += budget

    lines += [
        "",
        f"💸 <b>Total dépensé</b>  : {total_spent:.2f} €",
        f"💰 <b>Budget total</b>   : {total_budget:.2f} €",
        f"📉 <b>Reste</b>           : {total_budget - total_spent:.2f} €",
    ]
    return "\n".join(lines)


# ── Catégories de revenus ─────────────────────────────────────────────────────
_INCOME_CATS_FILE = Path(__file__).parent / "income_categories.json"

def load_income_cats() -> set:
    """Charge la liste des catégories de revenus (ex: Salaire) depuis income_categories.json."""
    if _INCOME_CATS_FILE.exists():
        try:
            return set(json.loads(_INCOME_CATS_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return set()

def save_income_cats(cats: set) -> None:
    """Sauvegarde atomique des catégories de revenus."""
    tmp = Path(str(_INCOME_CATS_FILE) + ".tmp")
    tmp.write_text(json.dumps(sorted(cats), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _INCOME_CATS_FILE)

def rename_category_in_income_cats(old: str, new: str) -> None:
    """Renomme une catégorie dans la liste des revenus si elle y figure."""
    cats = load_income_cats()
    if old in cats:
        cats.discard(old)
        cats.add(new)
        save_income_cats(cats)
