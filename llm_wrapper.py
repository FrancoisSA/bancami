"""
LLM Wrapper — Abstraction pour basculer entre différents providers LLM.
Gère aussi le logging des échanges pour l'onglet admin.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import config

# ── Configuration ────────────────────────────────────────────────────────────
LLM_LOGS_FILE = Path(__file__).parent / "llm_logs.json"
MAX_LOGS = 100  # Garder les 100 derniers échanges


def log_exchange(prompt: str, response: str, provider: str, duration_ms: float) -> None:
    """Enregistre un échange LLM dans le journal."""
    exchange = {
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt,
        "response": response,
        "provider": provider,
        "duration_ms": round(duration_ms, 2)
    }

    logs = []
    if LLM_LOGS_FILE.exists():
        try:
            logs = json.loads(LLM_LOGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    logs.insert(0, exchange)  # Ajouter en début de liste
    logs = logs[:MAX_LOGS]    # Garder seulement les plus récents

    try:
        LLM_LOGS_FILE.write_text(
            json.dumps(logs, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except OSError as e:
        print(f"[WARNING] Impossible d'écrire les logs LLM: {e}")


def get_llm_client() -> Any:
    """Retourne un client LLM configuré selon LLM_PROVIDER."""
    if config.LLM_PROVIDER == "anthropic":
        import anthropic
        return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    
    elif config.LLM_PROVIDER == "mistral":
        if not hasattr(config, 'MISTRAL_API_KEY') or not config.MISTRAL_API_KEY:
            raise ValueError("MISTRAL_API_KEY requis pour le provider mistral")
        # Implémentation Mistral à ajouter
        # import mistralai
        # return mistralai.Mistral(api_key=config.MISTRAL_API_KEY)
        raise NotImplementedError("Provider Mistral pas encore implémenté")
    
    else:
        raise ValueError(f"Provider LLM inconnu: {config.LLM_PROVIDER}")


def extract_text_with_logging(client: Any, image_data: bytes, prompt_template: str) -> str:
    """
    Interface unifiée pour l'extraction de texte avec logging.
    
    Args:
        client: Client LLM initialisé
        image_data: Données binaires de l'image
        prompt_template: Template de prompt à utiliser
    
    Returns:
        Texte extrait de l'image
    """
    start_time = time.time()
    
    try:
        if config.LLM_PROVIDER == "anthropic":
            from classifier import anthropic_extract_text
            response = anthropic_extract_text(client, image_data, prompt_template)
        
        elif config.LLM_PROVIDER == "mistral":
            # Implémentation Mistral à ajouter
            raise NotImplementedError("Provider Mistral pas encore implémenté")
        
        else:
            raise ValueError(f"Provider inconnu: {config.LLM_PROVIDER}")
    
    finally:
        duration_ms = (time.time() - start_time) * 1000
        log_exchange(prompt_template, response, config.LLM_PROVIDER, duration_ms)
    
    return response


def get_recent_exchanges(limit: int = 3) -> list[dict]:
    """Récupère les échanges récents pour l'interface admin."""
    try:
        if LLM_LOGS_FILE.exists():
            logs = json.loads(LLM_LOGS_FILE.read_text(encoding="utf-8"))
            return logs[:limit]
    except (json.JSONDecodeError, OSError):
        pass
    return []
