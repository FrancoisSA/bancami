"""
classifier.py — Classification des transactions par catégorie.

Pipeline :
  1. Règles par mots-clés (RULES) — instantané, sans appel API
  2. Mémoire des commerçants connus (merchants.json) — appris au fil du temps
  3. Classifieur Claude (optionnel) — pour les libellés inconnus

Ajouter un commerçant : ajouter une entrée dans RULES ci-dessous.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, MERCHANTS_FILE

logger = logging.getLogger(__name__)

_RULES_FILE = Path(__file__).parent / "rules.json"

# ── Règles par défaut ─────────────────────────────────────────────────────────
_DEFAULT_RULES: dict[str, str] = {
    "CHEZ LUDO":     "🥩 Boucherie",
    "BOUCHERIE":     "🥩 Boucherie",
    "ACTION":        "🛍️ Bazar / Discount",
    "GIFI":          "🛍️ Bazar / Discount",
    "GREECE":        "🛒 Supermarché",
    "INTERMARCHE":   "🛒 Supermarché",
    "LECLERC":       "🛒 Supermarché",
    "CARREFOUR":     "🛒 Supermarché",
    "CASINO":        "🛒 Supermarché",
    "LIDL":          "🛒 Supermarché",
    "ALDI":          "🛒 Supermarché",
    "ORANGE":        "📱 Abonnement",
    "FREE":          "📱 Abonnement",
    "SFR":           "📱 Abonnement",
    "BOUYGUES":      "📱 Abonnement",
    "SAMANRO":       "🚚 Livraison surgelés",
    "PICARD":        "🚚 Livraison surgelés",
    "BIO":           "🌿 Bio",
    "BIOCOOP":       "🌿 Bio",
    "NATURALIA":     "🌿 Bio",
    "NETFLIX":       "🎬 Streaming",
    "SPOTIFY":       "🎬 Streaming",
    "AMAZON PRIME":  "🎬 Streaming",
    "DISNEY":        "🎬 Streaming",
    "UBER EATS":     "🍽️ Restaurant",
    "DELIVEROO":     "🍽️ Restaurant",
    "JUST EAT":      "🍽️ Restaurant",
    "RESTAURANT":    "🍽️ Restaurant",
    "BRASSERIE":     "🍽️ Restaurant",
    "TOTAL":         "⛽ Carburant",
    "BP ":           "⛽ Carburant",
    "ESSO":          "⛽ Carburant",
    "SHELL":         "⛽ Carburant",
    "PHARMACIE":     "💊 Pharmacie",
    "PARAPHARMACIE": "💊 Pharmacie",
    "IKEA":          "🏠 Maison",
    "LEROY MERLIN":  "🏠 Maison",
    "CASTORAMA":     "🏠 Maison",
}

_UNKNOWN = "❓ Non classé"


def load_rules() -> dict[str, str]:
    """Charge les règles depuis rules.json, ou retourne les règles par défaut."""
    if _RULES_FILE.exists():
        try:
            return json.loads(_RULES_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULT_RULES)


def save_rules(rules: dict[str, str]) -> None:
    """Sauvegarde atomique des règles dans rules.json."""
    import os
    tmp = Path(str(_RULES_FILE) + ".tmp")
    tmp.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _RULES_FILE)


def rename_category_in_rules(old: str, new: str) -> int:
    """Remplace toutes les occurrences de l'ancienne catégorie dans les règles."""
    rules = load_rules()
    count = sum(1 for v in rules.values() if v == old)
    if count:
        updated = {k: (new if v == old else v) for k, v in rules.items()}
        save_rules(updated)
    return count


# Accessible comme avant
RULES: dict[str, str] = load_rules()


def _load_merchants() -> dict[str, str]:
    """Charge le fichier merchants.json (mémoire des catégories apprises)."""
    if MERCHANTS_FILE.exists():
        try:
            return json.loads(MERCHANTS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_merchants(merchants: dict[str, str]) -> None:
    """Sauvegarde atomique du fichier merchants.json."""
    tmp = Path(str(MERCHANTS_FILE) + ".tmp")
    tmp.write_text(json.dumps(merchants, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(MERCHANTS_FILE)


def classify_by_rules(label: str) -> str | None:
    """Tente de classer un libellé via les règles (rechargées depuis rules.json)."""
    upper = label.upper()
    for keyword, category in load_rules().items():
        if keyword.upper() in upper:
            return category
    return None


async def classify(label: str) -> str:
    """
    Classifie un libellé de transaction.

    Priorité :
      1. Règles statiques (RULES)
      2. Mémoire apprise (merchants.json)
      3. Claude API (fallback, résultat mémorisé)
    """
    # 1. Règles statiques
    cat = classify_by_rules(label)
    if cat:
        return cat

    # 2. Mémoire des commerçants
    merchants = _load_merchants()
    if label.upper() in merchants:
        return merchants[label.upper()]

    # 3. Claude API
    cat = await _classify_with_claude(label)
    if cat and cat != _UNKNOWN:
        # Mémoriser pour la prochaine fois
        merchants[label.upper()] = cat
        _save_merchants(merchants)

    return cat or _UNKNOWN


async def _classify_with_claude(label: str) -> str:
    """
    Appelle Claude pour classifier un libellé inconnu.
    Retourne "❓ Non classé" en cas d'erreur ou de réponse invalide.
    """
    categories = list({**RULES}.values())
    # Dédupliquer en préservant l'ordre
    seen: set[str] = set()
    unique_cats: list[str] = []
    for c in categories:
        if c not in seen:
            seen.add(c)
            unique_cats.append(c)
    unique_cats.append(_UNKNOWN)

    cats_str = "\n".join(f"- {c}" for c in unique_cats)
    prompt = (
        f"Tu es un assistant de classification de transactions bancaires.\n"
        f"Classe ce libellé de transaction dans UNE des catégories suivantes.\n"
        f"Réponds UNIQUEMENT avec le nom exact de la catégorie, rien d'autre.\n\n"
        f"Libellé : {label}\n\n"
        f"Catégories disponibles :\n{cats_str}"
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        result = message.content[0].text.strip()
        # Vérifier que la réponse est une catégorie valide
        if result in unique_cats:
            return result
        logger.warning("Claude a retourné une catégorie inconnue : %s", result)
        return _UNKNOWN
    except Exception as exc:
        logger.error("Erreur classification Claude : %s", exc)
        return _UNKNOWN
