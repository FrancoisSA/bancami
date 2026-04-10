"""
extractor.py — Extraction des transactions depuis image, PDF ou texte via Claude.

Trois modes d'entrée :
  - Image (JPEG/PNG/WEBP) → Claude Vision
  - PDF                   → Claude Document API (support natif, pas de dépendance externe)
  - Texte brut            → Claude texte

Notes importantes :
  - Les dates des relevés sont au format français JJ/MM/AAAA — précisé explicitement dans le prompt
  - L'année courante est injectée dynamiquement pour éviter que Claude infère une année incorrecte
  - Aucun fichier n'est jamais écrit sur disque (tout en mémoire)
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
from datetime import datetime

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)


# ── Prompt commun ─────────────────────────────────────────────────────────────
def _build_extraction_prompt() -> str:
    """
    Génère le prompt d'extraction pour Claude API.
    
    Points clés :
    - Année courante injectée pour éviter les erreurs d'inférence
    - Format de date français JJ/MM/AAAA explicitement spécifié
    - Exemples concrets pour guider la conversion
    - Sortie strictement JSON sans texte supplémentaire
    
    Note: Ce prompt est appelé à chaque extraction. Pour améliorer les performances,
    envisager un cache si le même prompt est utilisé fréquemment.
    """
    current_year = datetime.now().year
    return f"""Tu es un assistant d'analyse de relevés bancaires.

Extrait TOUTES les transactions présentes dans ce document.

IMPORTANT : ta réponse doit être UNIQUEMENT un tableau JSON brut.
Pas de texte avant. Pas de texte après. Pas de markdown. Pas d'explication.
Commence directement par [ et termine par ].

Format de chaque transaction :
[
  {{
    "date": "YYYY-MM-DD",
    "label": "LIBELLÉ EN MAJUSCULES",
    "amount": 37.14,
    "currency": "EUR",
    "type": "debit"
  }}
]

Règles :
- date : les dates sont au format français JJ/MM/AAAA (ex: 31/12/2024) ou JJ/MM/AA (ex: 31/12/24).
  Convertis TOUJOURS en format ISO YYYY-MM-DD (ex: 2024-12-31).
  Si l'année n'est pas spécifiée (format JJ/MM), utilise {current_year}.
  Exemples :
    "31/12/2024" → "2024-12-31"
    "31/12/24" → "2024-12-31"
    "31/12" → "{current_year}-12-31"
- label : libellé exact en majuscules
- amount : valeur absolue positive (jamais négatif)
- currency : EUR par défaut
- type : "debit" si argent sortant, "credit" si argent entrant (virement reçu, salaire, remboursement)
- Si aucune transaction détectable : retourne exactement []
- Ne jamais inclure soldes, totaux ou virements internes"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_transaction_id(date: str, label: str, amount: float) -> str:
    """SHA1 de date+label+amount — sert de clé de déduplication."""
    raw = f"{date}|{label.upper()}|{amount:.2f}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _parse_json_response(text: str) -> list[dict] | None:
    """
    Parse la réponse Claude en JSON.
    Stratégies successives :
      1. Parse direct
      2. Suppression des blocs markdown ```json ... ```
      3. Extraction du premier tableau [ ... ] trouvé dans le texte
    """
    logger.info("Réponse brute Claude (%d chars) : %s", len(text), text[:500])

    candidates = [text.strip()]

    # Supprimer les blocs markdown
    stripped = re.sub(r"```(?:json)?\s*", "", text)
    stripped = re.sub(r"```", "", stripped).strip()
    candidates.append(stripped)

    # Extraire le premier tableau JSON du texte (entre [ et le ] fermant correspondant)
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            continue

    logger.error("Impossible d'extraire un tableau JSON. Réponse complète : %s", text)
    return None


def _validate(transactions: list[dict]) -> list[dict]:
    """Valide et enrichit les transactions brutes retournées par Claude."""
    validated = []
    for tx in transactions:
        if not all(k in tx for k in ("date", "label", "amount")):
            logger.warning("Transaction incomplète ignorée : %s", tx)
            continue
        tx["label"]          = str(tx["label"]).upper().strip()
        tx["amount"]         = float(tx["amount"])
        tx["currency"]       = tx.get("currency", "EUR")
        tx["type"]           = tx.get("type", "debit") if tx.get("type") in ("debit", "credit") else "debit"
        tx["transaction_id"] = _generate_transaction_id(tx["date"], tx["label"], tx["amount"])
        validated.append(tx)
    return validated


async def _call_claude(content: list[dict], max_tokens: int = 4096) -> list[dict]:
    """Appelle l'API Claude avec le contenu donné et retourne les transactions validées."""
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    try:
        message = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.APIError as exc:
        raise RuntimeError(f"Erreur API Anthropic : {exc}") from exc

    raw = message.content[0].text
    logger.debug("Réponse Claude : %s", raw[:500])

    transactions = _parse_json_response(raw)
    if transactions is None:
        raise RuntimeError("Claude a retourné un JSON invalide ou malformé.")
    return _validate(transactions)


# ── API publique ──────────────────────────────────────────────────────────────

async def extract_transactions_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> list[dict]:
    """Extrait les transactions depuis une image (JPEG, PNG, WEBP)."""
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    content = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": mime_type, "data": image_b64},
        },
        {"type": "text", "text": _build_extraction_prompt()},
    ]
    return await _call_claude(content)


async def extract_transactions_from_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    Extrait les transactions depuis un fichier PDF.
    Utilise le support natif PDF de l'API Anthropic (aucune dépendance externe).
    """
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    content = [
        {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
        },
        {"type": "text", "text": _build_extraction_prompt()},
    ]
    return await _call_claude(content, max_tokens=8192)


async def extract_transactions_from_text(text: str) -> list[dict]:
    """
    Extrait les transactions depuis du texte brut (copier-coller de relevé,
    saisie manuelle, export CSV collé, etc.).
    """
    content = [
        {
            "type": "text",
            "text": f"{_build_extraction_prompt()}\n\nTexte à analyser :\n\n{text}",
        }
    ]
    return await _call_claude(content, max_tokens=8192)
