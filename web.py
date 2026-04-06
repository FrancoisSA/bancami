"""
web.py — Interface web de suivi budgétaire.

Accessible sur http://FSA-PI5.local:5000
Lance avec : venv/bin/python web.py
"""

from __future__ import annotations

import calendar
from datetime import datetime

from flask import Flask, jsonify, render_template, request

import config  # noqa: F401
from budget import (compute_bilan, load_budgets, load_global_budget, save_budgets, save_global_budget,
                    load_opening_balance, save_opening_balance, rename_category_in_budgets,
                    load_income_cats, save_income_cats, rename_category_in_income_cats)
from classifier import load_rules, save_rules, rename_category_in_rules
from storage import (get_transactions_for_month, load_transactions, update_transaction_category,
                     update_transaction, rename_category_in_transactions)

app = Flask(__name__)


@app.route("/")
def index():
    now = datetime.now()
    return render_template("dashboard.html", year=now.year, month=now.month)


@app.route("/api/transactions")
def api_transactions():
    """Retourne toutes les transactions, avec filtre mois/année optionnel."""
    year  = request.args.get("year",  type=int)
    month = request.args.get("month", type=int)

    if year and month:
        txs = get_transactions_for_month(year, month)
    else:
        txs = load_transactions()

    # Trier par date décroissante
    txs = sorted(txs, key=lambda t: t.get("date", ""), reverse=True)
    return jsonify(txs)


@app.route("/api/transactions/<transaction_id>", methods=["PATCH"])
def api_transaction_update(transaction_id):
    """Met à jour un ou plusieurs champs d'une transaction."""
    data    = request.get_json()
    updates = {}
    if "category" in data:
        updates["category"] = data["category"]
    if "date" in data:
        updates["date"] = data["date"]
    if "label" in data:
        updates["label"] = str(data["label"]).upper().strip()
    if "amount" in data:
        try:
            updates["amount"] = float(data["amount"])
        except (ValueError, TypeError):
            return jsonify({"ok": False, "error": "amount invalide"}), 400
    if "type" in data and data["type"] in ("debit", "credit"):
        updates["type"] = data["type"]
    ok = update_transaction(transaction_id, updates)
    return jsonify({"ok": ok}), (200 if ok else 404)


@app.route("/api/settings/opening-balance", methods=["GET", "PUT"])
def api_opening_balance():
    now   = datetime.now()
    year  = request.args.get("year",  default=now.year,  type=int)
    month = request.args.get("month", default=now.month, type=int)
    if request.method == "GET":
        return jsonify({"amount": load_opening_balance(year, month)})
    try:
        amount = float(request.get_json().get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "amount invalide"}), 400
    save_opening_balance(year, month, amount)
    return jsonify({"ok": True})


@app.route("/api/settings/global-budget", methods=["GET", "PUT"])
def api_global_budget():
    if request.method == "GET":
        return jsonify({"amount": load_global_budget()})
    try:
        amount = float(request.get_json()["amount"])
    except (TypeError, KeyError, ValueError):
        return jsonify({"ok": False, "error": "amount invalide"}), 400
    save_global_budget(amount)
    return jsonify({"ok": True})


@app.route("/api/bilan")
def api_bilan():
    """Retourne le bilan par catégorie pour un mois donné."""
    now   = datetime.now()
    year  = request.args.get("year",  default=now.year,  type=int)
    month = request.args.get("month", default=now.month, type=int)

    txs   = get_transactions_for_month(year, month)
    bilan = compute_bilan(txs)

    result = []
    for cat, data in sorted(bilan.items(), key=lambda x: -x[1]["budget"]):
        if data["budget"] > 0 or data["spent"] > 0:
            result.append({
                "category": cat,
                "spent":    round(data["spent"],  2),
                "budget":   round(data["budget"], 2),
                "pct":      round(data["pct"],    1),
            })

    total_spent    = round(sum(r["spent"]  for r in result), 2)
    total_budget   = round(sum(r["budget"] for r in result), 2)
    global_budget  = load_global_budget()
    opening_balance = load_opening_balance(year, month)

    # Revenus prévus = somme des budgets marqués "revenu" (ex: Salaire)
    # Les catégories revenus sont exclues du calcul des dépenses
    income_cats  = load_income_cats()
    budgets      = load_budgets()
    income_total = round(sum(v for k, v in budgets.items() if k in income_cats), 2)

    return jsonify({
        "rows":            result,
        "total_spent":     total_spent,
        "total_budget":    total_budget,
        "global_budget":   global_budget,
        "opening_balance": opening_balance,
        "income_total":    income_total,
        "income_categories": sorted(income_cats),
    })


@app.route("/api/settings/budgets", methods=["GET", "PUT"])
def api_budgets():
    if request.method == "GET":
        budgets = load_budgets()
        return jsonify([{"category": k, "amount": v} for k, v in budgets.items()])
    # PUT — remplace un budget ou ajoute une catégorie
    data = request.get_json() or {}
    try:
        cat    = str(data["category"]).strip()
        amount = float(data["amount"])
        if not cat:
            raise ValueError("category vide")
    except (KeyError, ValueError, TypeError):
        return jsonify({"ok": False, "error": "category ou amount invalide"}), 400
    budgets = load_budgets()
    budgets[cat] = amount
    save_budgets(budgets)
    return jsonify({"ok": True})


@app.route("/api/settings/budgets/<path:category>", methods=["DELETE"])
def api_budget_delete(category):
    budgets = load_budgets()
    budgets.pop(category, None)
    save_budgets(budgets)
    return jsonify({"ok": True})


@app.route("/api/settings/income-categories", methods=["GET", "PUT"])
def api_income_categories():
    if request.method == "GET":
        return jsonify(sorted(load_income_cats()))
    # PUT {category, income: true|false}
    data = request.get_json()
    cats = load_income_cats()
    if data.get("income"):
        cats.add(data["category"])
    else:
        cats.discard(data["category"])
    save_income_cats(cats)
    return jsonify({"ok": True})


@app.route("/api/settings/rules", methods=["GET", "POST"])
def api_rules():
    if request.method == "GET":
        rules = load_rules()
        return jsonify([{"keyword": k, "category": v} for k, v in rules.items()])
    # POST — ajoute ou modifie une règle
    data = request.get_json()
    rules = load_rules()
    rules[data["keyword"].upper().strip()] = data["category"]
    save_rules(rules)
    return jsonify({"ok": True})


@app.route("/api/settings/rules/<path:keyword>", methods=["DELETE", "PUT"])
def api_rule_update(keyword):
    rules = load_rules()
    if request.method == "DELETE":
        rules.pop(keyword.upper(), None)
    else:  # PUT — modifier catégorie ou renommer le keyword
        data = request.get_json()
        rules.pop(keyword.upper(), None)          # supprimer l'ancienne clé
        new_kw = data.get("keyword", keyword).upper().strip()
        rules[new_kw] = data["category"]
    save_rules(rules)
    return jsonify({"ok": True})


@app.route("/api/settings/categories/rename", methods=["POST"])
def api_rename_category():
    data    = request.get_json()
    old     = (data.get("old_name") or "").strip()
    new     = (data.get("new_name") or "").strip()
    if not old or not new or old == new:
        return jsonify({"ok": False, "error": "invalid"}), 400
    rename_category_in_budgets(old, new)
    rename_category_in_rules(old, new)
    rename_category_in_income_cats(old, new)
    tx_count = rename_category_in_transactions(old, new)
    return jsonify({"ok": True, "transactions_updated": tx_count})


@app.route("/api/settings/categories")
def api_categories():
    """Liste toutes les catégories connues (union budgets + règles)."""
    cats = set(load_budgets().keys()) | set(load_rules().values())
    return jsonify(sorted(cats))


@app.route("/api/burndown")
def api_burndown():
    """Retourne les données du burndown chart jour par jour."""
    now   = datetime.now()
    year  = request.args.get("year",  default=now.year,  type=int)
    month = request.args.get("month", default=now.month, type=int)

    txs      = get_transactions_for_month(year, month)
    last_day = calendar.monthrange(year, month)[1]
    days     = list(range(1, last_day + 1))
    budgets  = load_budgets()

    def signed(tx: dict) -> float:
        """Débit = positif (consomme le budget), crédit = négatif (le recharge).
        Convention : on mesure la consommation du budget, donc un remboursement
        (crédit) réduit le montant dépensé dans la catégorie."""
        return tx["amount"] if tx.get("type", "debit") == "debit" else -tx["amount"]

    # Accumuler dépenses nettes par catégorie et par jour
    day_totals: dict[str, dict[int, float]] = {
        cat: {d: 0.0 for d in days}
        for cat, b in budgets.items() if b > 0
    }
    for tx in txs:
        try:
            day = int(tx["date"].split("-")[2])
        except (KeyError, ValueError, IndexError):
            continue
        cat = tx.get("category", "❓ Non classé")
        if cat in day_totals:
            day_totals[cat][day] += signed(tx)

    # Série globale : flux net jour par jour
    global_budget_val   = load_global_budget() or sum(b for b in budgets.values() if b > 0)
    opening_balance_val = load_opening_balance(year, month)
    # Si solde initial défini, le burndown part de ce solde ; sinon du budget global
    effective_start = opening_balance_val if opening_balance_val else global_budget_val

    global_day: dict[int, float] = {d: 0.0 for d in days}
    for tx in txs:
        try:
            day = int(tx["date"].split("-")[2])
        except (KeyError, ValueError, IndexError):
            continue
        global_day[day] = global_day.get(day, 0.0) + signed(tx)

    global_pts = []
    cumul_g = 0.0
    for d in days:
        cumul_g += global_day.get(d, 0.0)
        global_pts.append(round(effective_start - cumul_g, 2))

    # Séries par catégorie
    series = []
    for cat, budget in budgets.items():
        if budget <= 0 or cat not in day_totals:
            continue
        cumul = 0.0
        pts   = []
        for d in days:
            cumul += day_totals[cat].get(d, 0.0)
            pts.append(round(budget - cumul, 2))
        series.append({"category": cat, "budget": budget, "data": pts})

    # ── Mois précédent : burndown global comme référence ─────────────────────
    prev_month = month - 1 if month > 1 else 12
    prev_year  = year if month > 1 else year - 1
    prev_txs      = get_transactions_for_month(prev_year, prev_month)
    prev_last_day = calendar.monthrange(prev_year, prev_month)[1]
    prev_gb       = load_global_budget() or sum(b for b in budgets.values() if b > 0)

    # Flux net du mois précédent par jour (débits − crédits)
    prev_day: dict[int, float] = {d: 0.0 for d in range(1, prev_last_day + 1)}

    # Accumulation par catégorie pour le mois précédent
    prev_day_totals: dict = {cat: {} for cat in budgets if budgets[cat] > 0}
    for tx in prev_txs:
        try:
            d = int(tx["date"].split("-")[2])
        except (KeyError, ValueError, IndexError):
            continue
        prev_day[d] = prev_day.get(d, 0.0) + signed(tx)
        cat = tx.get("category", "❓ Non classé")
        if cat in prev_day_totals:
            prev_day_totals[cat][d] = prev_day_totals[cat].get(d, 0.0) + signed(tx)

    # Ajouter prev_data par catégorie
    for s in series:
        cat    = s["category"]
        budget = s["budget"]
        cumul  = 0.0
        pts    = []
        for d in range(1, prev_last_day + 1):
            cumul += prev_day_totals.get(cat, {}).get(d, 0.0)
            pts.append(round(budget - cumul, 2))
        if len(pts) >= last_day:
            s["prev_data"] = pts[:last_day]
        else:
            s["prev_data"] = pts + [pts[-1]] * (last_day - len(pts)) if pts else [budget] * last_day

    # Construire la courbe sur prev_last_day jours puis aligner sur last_day
    prev_pts_raw = []
    cumul_p = 0.0
    for d in range(1, prev_last_day + 1):
        cumul_p += prev_day.get(d, 0.0)
        prev_pts_raw.append(round(prev_gb - cumul_p, 2))

    # Aligner sur le nombre de jours du mois courant
    # (tronquer ou étendre avec la dernière valeur)
    if len(prev_pts_raw) >= last_day:
        prev_pts = prev_pts_raw[:last_day]
    else:
        prev_pts = prev_pts_raw + [prev_pts_raw[-1]] * (last_day - len(prev_pts_raw))

    return jsonify({
        "days":            days,
        "series":          series,
        "global":          {"budget": round(effective_start, 2), "data": global_pts,
                            "is_balance": opening_balance_val is not None},
        "previous":        {"budget": round(prev_gb, 2), "data": prev_pts,
                            "label": f"{prev_month:02d}/{prev_year}"},
        "opening_balance": opening_balance_val,
    })


@app.route("/api/months")
def api_months():
    """Retourne la liste des mois disponibles dans les transactions."""
    txs    = load_transactions()
    months = sorted({tx["date"][:7] for tx in txs if "date" in tx}, reverse=True)
    result = []
    for m in months:
        y, mo = m.split("-")
        _FR = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
               "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        result.append({"value": m, "label": f"{_FR[int(mo)]} {y}", "year": int(y), "month": int(mo)})
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
