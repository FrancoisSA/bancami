# Bancami — Manuel utilisateur v1.0

**Version :** 1.0  
**Date :** 06 avril 2026  
**Plateforme :** Raspberry Pi 5 (FSA-PI5.local)

---

## Présentation

Bancami est un assistant budgétaire personnel composé de deux services :

- **Bot Telegram** (`budget-bot`) — reçoit les relevés bancaires (photo, PDF, texte), extrait les transactions via Claude Vision, les classe automatiquement et répond à des commandes de suivi.
- **Interface web** (`budget-web`) — tableau de bord accessible sur `http://FSA-PI5.local:5000` depuis le réseau local.

---

## Commandes Telegram

| Commande | Description |
|---|---|
| `/start` | Message de bienvenue et liste des commandes |
| `/resume` | Résumé rapide : budget consommé + solde prévisionnel |
| `/bilan` | Bilan détaillé par catégorie (dépensé / budget / %) |
| `/graphique` | Burndown chart PNG du mois courant |
| `/transactions [N]` | N dernières transactions (défaut : 10) |
| `/budget` | Budgets mensuels par catégorie |
| `/reset_mois` | Supprime toutes les transactions du mois courant |
| `/sante` | Uptime, espace disque, température CPU |

### Envoi de relevés

Envoyer directement au bot :
- **Une photo** — capture d'écran d'un relevé bancaire
- **Un PDF** — export bancaire
- **Du texte** — copier-coller d'un relevé

Le bot extrait les transactions, les déduplique et les classe automatiquement.

### Bilan quotidien automatique

Chaque jour à **9h00**, le bot envoie automatiquement un résumé :

```
───── 06 Avril 2026 ─────
✅ Budget consommé : 1 763,01 € / 4 370 € (40%)
💚 Solde prévisionnel : +130,00 €
```

---

## Interface web — Dashboard

Accessible sur `http://FSA-PI5.local:5000`

### Onglet Dashboard

**Budget global du mois**
- Barre de progression du budget global (configurable dans Paramètres)
- **Solde prévisionnel révisé** : estimation fin de mois basée sur le rythme de dépense actuel
  - Formule : pour chaque catégorie budgétée, on projette `max(dépensé, budget)` — si on dépense plus vite que prévu on extrapole, sinon on suppose qu'on atteindra le budget
  - ✅ Budget tenu / ⚠️ Découvert probable

**Burndown chart**
- Courbe du solde estimé jour par jour (ligne pleine bleue)
- Courbe du mois précédent (ligne pointillée grise) pour comparaison
- Sélection de catégories individuelles via les chips sous le graphique
  - Chaque catégorie cochée affiche sa courbe pleine (mois courant) + pointillée (mois précédent)
  - Les sélections sont **mémorisées** entre les sessions (localStorage)
- Échelle Y en puissance 0.4 pour visualiser simultanément petites et grandes catégories

**Bilan par catégorie**
- Tableau trié par % de budget consommé (les plus critiques en haut)
- Barre de progression colorée : vert < 70% / orange 70–90% / rouge > 90%

**Transactions du mois**
- Tableau complet avec recherche et tri par colonne
- Modification de catégorie directement dans le tableau
- Édition inline (date, libellé, montant, type)

---

## Interface web — Catégories & Budgets

### Budget prévisionnel global
En haut de la section, un bandeau affiche :
- **Solde prévisionnel fin de mois** = Revenus budgétés − Dépenses budgétées
- Détail : `In : X€  /  Out : Y€`

### Gestion des catégories
- **Renommer** une catégorie (propagé dans toutes les transactions, règles et budgets)
- **Supprimer** une catégorie
- **Type** : bouton 💸 (dépense) / 💰 (revenu) — les catégories revenus (ex: Salaire) sont exclues des calculs de dépenses

### Budgets par catégorie
- Montant mensuel alloué par catégorie
- Utilisé pour le burndown, le bilan et les projections

### Règles de classification
- Association mot-clé → catégorie
- Le mot-clé est mis en majuscules et comparé au libellé des transactions

---

## Paramètres avancés

| Paramètre | Emplacement | Description |
|---|---|---|
| Budget global mensuel | Onglet Catégories | Enveloppe totale — utilisée pour la barre de progression et le burndown |
| Solde initial du mois | Onglet Catégories | Si défini, le burndown part de ce solde plutôt que du budget |

---

## Architecture technique

```
budget-bot/
├── bot.py              # Bot Telegram + job quotidien 9h
├── web.py              # API Flask + interface web
├── budget.py           # Budgets, bilan, catégories revenus
├── storage.py          # Stockage JSON atomique (anti-corruption SD)
├── classifier.py       # Règles de classification
├── extractor.py        # Extraction Claude Vision
├── charts.py           # Burndown chart matplotlib
├── config.py           # Variables d'environnement
├── templates/
│   └── dashboard.html  # Interface web (SPA)
├── transactions.json   # Base de données transactions
├── budgets.json        # Budgets par catégorie
├── income_categories.json  # Catégories de revenus
├── global_budget.json  # Budget global mensuel
├── opening_balances.json   # Soldes initiaux par mois
└── .env                # Tokens (ne pas commiter)
```

### Services systemd

```bash
sudo systemctl status budget-bot    # Bot Telegram
sudo systemctl status budget-web    # Interface web (port 5000)
```

### Logs

```bash
journalctl -u budget-bot -f    # Logs bot en direct
journalctl -u budget-web -f    # Logs web en direct
```

---

## Installation (depuis zéro)

Voir `README.md` pour l'installation complète sur Raspberry Pi OS Bookworm.

Variables d'environnement requises dans `.env` :
```
TELEGRAM_BOT_TOKEN=...
ANTHROPIC_API_KEY=...
TELEGRAM_USER_ID=...
```
