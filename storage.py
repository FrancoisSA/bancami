"""
storage.py — Lecture/écriture atomique du fichier transactions.json.

L'écriture est toujours atomique (fichier .tmp + os.replace) pour éviter
la corruption sur carte SD en cas de coupure de courant.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from config import DATA_FILE

logger = logging.getLogger(__name__)


def _load_raw() -> dict:
    """Charge le contenu brut du fichier JSON. Retourne une structure vide si absent."""
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Impossible de lire %s : %s", DATA_FILE, exc)
    return {"transactions": []}


def _save_raw(data: dict) -> None:
    """
    Sauvegarde atomique : écriture dans .tmp puis os.replace().
    Critique sur carte SD / SSD pour éviter la corruption.
    """
    tmp = Path(str(DATA_FILE) + ".tmp")
    try:
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, DATA_FILE)
    except OSError as exc:
        logger.error("Échec écriture atomique : %s", exc)
        raise


def load_transactions() -> list[dict]:
    """Retourne la liste complète des transactions."""
    return _load_raw().get("transactions", [])


def add_transactions(new_txs: list[dict]) -> tuple[int, int]:
    """
    Ajoute les transactions sans doublon.

    Un doublon est détecté via transaction_id (SHA1 de date+label+amount).

    Returns:
        (nb_added, nb_duplicates)
    """
    data = _load_raw()
    existing: list[dict] = data.get("transactions", [])

    existing_ids = {tx["transaction_id"] for tx in existing}
    added    = 0
    skipped  = 0

    for tx in new_txs:
        tid = tx.get("transaction_id", "")
        if tid in existing_ids:
            skipped += 1
            continue
        # Horodatage d'insertion
        tx["added_at"] = datetime.now().isoformat(timespec="seconds")
        existing.append(tx)
        existing_ids.add(tid)
        added += 1

    if added > 0:
        data["transactions"] = existing
        _save_raw(data)

    return added, skipped


def get_transactions_for_month(year: int, month: int) -> list[dict]:
    """Filtre les transactions pour un mois/année donné."""
    prefix = f"{year:04d}-{month:02d}"
    return [
        tx for tx in load_transactions()
        if tx.get("date", "").startswith(prefix)
    ]


def reset_month(year: int, month: int) -> int:
    """
    Supprime toutes les transactions du mois spécifié.
    Retourne le nombre de transactions supprimées.
    """
    prefix = f"{year:04d}-{month:02d}"
    data   = _load_raw()
    before = data.get("transactions", [])
    after  = [tx for tx in before if not tx.get("date", "").startswith(prefix)]
    removed = len(before) - len(after)

    if removed > 0:
        data["transactions"] = after
        _save_raw(data)

    return removed


def update_transaction_category(transaction_id: str, new_category: str) -> bool:
    """
    Met à jour la catégorie d'une transaction existante.
    Retourne True si trouvée et mise à jour, False sinon.
    """
    return bool(update_transaction(transaction_id, {"category": new_category}))


def update_transaction(transaction_id: str, updates: dict) -> bool:
    """
    Met à jour les champs d'une transaction existante.
    Champs acceptés : date, label, amount, currency, type, category.
    Retourne True si trouvée et mise à jour, False sinon.
    """
    _ALLOWED = {"date", "label", "amount", "currency", "type", "category"}
    data = _load_raw()
    for tx in data.get("transactions", []):
        if tx.get("transaction_id") == transaction_id:
            for key, val in updates.items():
                if key in _ALLOWED:
                    tx[key] = val
            _save_raw(data)
            return True
    return False


def rename_category_in_transactions(old: str, new: str) -> int:
    """
    Renomme une catégorie dans toutes les transactions.
    Retourne le nombre de transactions modifiées.
    """
    data  = _load_raw()
    count = 0
    for tx in data.get("transactions", []):
        if tx.get("category") == old:
            tx["category"] = new
            count += 1
    if count > 0:
        _save_raw(data)
    return count


def count_transactions() -> int:
    """Retourne le nombre total de transactions stockées."""
    return len(load_transactions())
