"""
charts.py — Génération du burndown chart par catégorie.

matplotlib.use('Agg') est appelé en tête de ce module — OBLIGATOIRE en mode
headless (Raspberry Pi sans serveur X). Ne pas déplacer cet appel.
"""

from __future__ import annotations

import calendar
import io
import logging
from datetime import date

# ── IMPORTANT : backend headless, DOIT être avant tout import pyplot ──────────
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D

from budget import MONTHLY_BUDGETS

logger = logging.getLogger(__name__)

# Palette de couleurs distinctes pour les catégories
_COLORS = [
    "#4FC3F7", "#81C784", "#FFB74D", "#F06292", "#CE93D8",
    "#80DEEA", "#FFCC80", "#A5D6A7", "#EF9A9A", "#90CAF9",
    "#FFF176", "#BCAAA4",
]


def _strip_emoji(text: str) -> str:
    """Retire les emojis d'un libellé — matplotlib (DejaVu Sans) ne les supporte pas."""
    import re
    # Supprimer les caractères non-ASCII qui ne sont pas des lettres accentuées
    return re.sub(r"[^\x00-\x7FÀ-ÿ\s]", "", text).strip()


def generate_burndown_chart(transactions: list[dict], year: int, month: int) -> bytes:
    """
    Génère un burndown chart mensuel par catégorie.

    - Axe X : jours du mois (1 → dernier jour)
    - Axe Y : budget restant (commence à 100 %, descend à mesure des dépenses)
    - Une ligne par catégorie avec budget > 0
    - Ligne de référence diagonale (consommation idéale linéaire)
    - Les catégories dépassées apparaissent en rouge sous zéro

    Args:
        transactions : liste de transactions du mois (déjà filtrées)
        year, month  : année et mois courant

    Returns:
        Contenu PNG en bytes (prêt à être envoyé via Telegram).
    """
    last_day = calendar.monthrange(year, month)[1]
    today    = date.today()

    # Limiter l'affichage jusqu'à aujourd'hui (ou fin de mois)
    max_day = min(today.day, last_day) if (today.year == year and today.month == month) else last_day

    # ── Accumuler les dépenses jour par jour par catégorie ────────────────────
    # Structure : day_totals[cat][day] = montant dépensé ce jour-là
    day_totals: dict[str, dict[int, float]] = {
        cat: {d: 0.0 for d in range(1, last_day + 1)}
        for cat in MONTHLY_BUDGETS
        if MONTHLY_BUDGETS[cat] > 0
    }

    for tx in transactions:
        try:
            day = int(tx["date"].split("-")[2])
        except (KeyError, ValueError, IndexError):
            continue
        cat = tx.get("category", "❓ Non classé")
        if cat in day_totals:
            day_totals[cat][day] += tx["amount"]

    # ── Construire les courbes : budget restant cumulé ────────────────────────
    # remaining[cat][day] = budget_initial - cumul_dépenses_jusqu'au_jour
    curves: dict[str, list[float]] = {}
    for cat, budget in MONTHLY_BUDGETS.items():
        if budget <= 0 or cat not in day_totals:
            continue
        cumul = 0.0
        pts   = []
        for d in range(1, last_day + 1):
            cumul += day_totals[cat].get(d, 0.0)
            pts.append(budget - cumul)
        curves[cat] = pts

    # ── Figure ────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor("#1E1E2E")
    ax.set_facecolor("#1E1E2E")

    days = list(range(1, last_day + 1))

    # Ligne de référence : budget total idéal, consommation linéaire
    total_budget = sum(b for b in MONTHLY_BUDGETS.values() if b > 0)
    ideal = [total_budget * (1 - d / last_day) for d in days]
    ax.plot(days, ideal, "--", color="#555577", linewidth=1.2, label="Idéal (total)", zorder=1)

    # Ligne zéro
    ax.axhline(0, color="#888899", linewidth=0.8, linestyle=":")

    # Tracer chaque catégorie
    legend_handles = []
    for idx, (cat, pts) in enumerate(sorted(curves.items(), key=lambda x: -MONTHLY_BUDGETS[x[0]])):
        color = _COLORS[idx % len(_COLORS)]
        # Afficher uniquement jusqu'à aujourd'hui
        visible_days = days[:max_day]
        visible_pts  = pts[:max_day]

        ax.plot(visible_days, visible_pts, linewidth=2.0, color=color, zorder=2)

        # Marquer le point courant
        if visible_days:
            last_val = visible_pts[-1]
            marker_color = "#FF6B6B" if last_val < 0 else color
            ax.plot(visible_days[-1], last_val, "o", color=marker_color, markersize=6, zorder=3)

        budget    = MONTHLY_BUDGETS[cat]
        spent     = budget - pts[max_day - 1] if max_day > 0 else 0
        cat_label = _strip_emoji(cat)
        legend_handles.append(
            Line2D([0], [0], color=color, linewidth=2,
                   label=f"{cat_label}  ({spent:.0f}€ / {budget:.0f}€)")
        )

    # ── Mise en forme ─────────────────────────────────────────────────────────
    month_name = calendar.month_name[month]  # ex: "April"
    # Noms français
    _FR_MONTHS = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    ax.set_title(f"Burndown Chart — {_FR_MONTHS[month]} {year}",
                 color="white", fontsize=14, pad=12)
    ax.set_xlabel("Jour du mois", color="#AAAACC", fontsize=11)
    ax.set_ylabel("Budget restant (€)", color="#AAAACC", fontsize=11)

    ax.tick_params(colors="#AAAACC")
    ax.xaxis.set_major_locator(mticker.MultipleLocator(5))
    ax.xaxis.set_minor_locator(mticker.MultipleLocator(1))
    ax.set_xlim(1, last_day)

    for spine in ax.spines.values():
        spine.set_edgecolor("#444466")

    ax.grid(True, which="major", color="#333355", linestyle="-", linewidth=0.5, zorder=0)
    ax.grid(True, which="minor", color="#2A2A44", linestyle=":", linewidth=0.3, zorder=0)

    # Légende à droite de la figure
    legend = ax.legend(
        handles=legend_handles,
        loc="upper right",
        framealpha=0.3,
        facecolor="#1E1E2E",
        edgecolor="#444466",
        labelcolor="white",
        fontsize=9,
    )

    plt.tight_layout()

    # ── Export PNG en mémoire ─────────────────────────────────────────────────
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()
