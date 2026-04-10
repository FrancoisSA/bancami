"""
config.py — Chargement des variables d'environnement depuis .env

Toutes les clés sensibles (tokens, IDs) sont lues ici et jamais codées en dur.
Importer ce module en premier dans tout autre module qui en a besoin.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Charger le .env depuis le dossier du projet
load_dotenv(Path(__file__).parent / ".env")

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]

# L'ID numérique Telegram du seul utilisateur autorisé (whitelist stricte)
TELEGRAM_USER_ID: int = int(os.environ["TELEGRAM_USER_ID"])

# ── LLM Provider ──────────────────────────────────────────────────────────────
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")  # anthropic ou mistral

# ── Anthropic ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")

# Modèle Claude à utiliser pour l'extraction vision
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

# ── Mistral (optionnel) ───────────────────────────────────────────────────────
MISTRAL_API_KEY: str | None = os.getenv("MISTRAL_API_KEY")

# ── Fichiers de données ───────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent

# Fichier de stockage des transactions
DATA_FILE: Path = DATA_DIR / os.getenv("DATA_FILE", "transactions.json")

# Fichier de mémoire des commerçants classifiés
MERCHANTS_FILE: Path = DATA_DIR / os.getenv("MERCHANTS_FILE", "merchants.json")
