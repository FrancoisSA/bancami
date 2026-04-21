# Bancami — Manuel utilisateur v1.2

**Version :** 1.2  
**Date :** 10 avril 2026  
**Plateforme :** Raspberry Pi 5 (FSA-PI5.local)

---

## Nouveautés v1.2

### 🎯 Améliorations majeures

- **Suppression de transactions** directement depuis le dashboard web
  - Bouton 🗑️ ajouté à côté de chaque transaction
  - Confirmation avant suppression
  - Mise à jour automatique du bilan après suppression

- **Détection et suppression automatique des doublons**
  - Script `check_doublons.py` pour identifier les transactions suspectes
  - 12 doublons supprimés automatiquement lors de la migration
  - Système de déduplication renforcé via `transaction_id` (SHA1 de date+label+montant)

- **Format des dates clarifié** dans les prompts Claude
  - Exemples concrets ajoutés : "31/12/2024" → "2024-12-31"
  - Meilleure gestion des formats JJ/MM/AAAA et JJ/MM/AA
  - Année courante injectée dynamiquement pour les dates incomplètes

- **Onglet Admin** pour surveiller les échanges LLM
  - Affiche les 3 derniers prompts et réponses
  - Permet de vérifier la qualité des extractions
  - Accessible sur `http://FSA-PI5.local:5000/admin`

- **Interface de suppression dédiée** sur `/delete`
  - Recherche par mot-clé dans les libellés
  - Suppression ciblée avec confirmation
  - Alternative à la suppression depuis le dashboard

### 🐛 Corrections

- Correction du bug d'affichage des icônes de catégories
- Mapping centralisé des émoticônes dans `budget.py`
- Standardisation des noms de catégories avec icônes

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
| `/resume` | Résumé rapide : budget consommé, reste disponible, solde prévisionnel |
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

Le bot extrait les transactions, les déduplique, les classe automatiquement, puis envoie un résumé budgétaire à jour.

### Bilan quotidien automatique

Un message `/resume` est envoyé chaque matin à 9h avec :
- Budget consommé hier et ce mois-ci
- Reste disponible
- Top 3 catégories du mois
- Solde prévisionnel en fin de mois

---

## Interface Web

### 📊 Tableau de bord (`/`) 

- **Burndown chart** — consommation du budget jour par jour
- **KPIs** — budget global, consommé, reste disponible
- **Liste des transactions** — triable et filtrable
- **Boutons d'action** :
  - ✏️ **Modifier** — corriger une transaction
  - 🗑️ **Supprimer** — supprimer une transaction (nouveau en v1.2)

### 👮 Onglet Admin (`/admin`) 

*Nouveau en v1.2* — Affiche les derniers échanges avec l'API LLM :
- Prompt envoyé à Claude
- Réponse reçue
- Provider utilisé (Anthropic)
- Durée de traitement
- Horodatage

### 🗑️ Page de suppression (`/delete`) 

*Nouveau en v1.2* — Interface dédiée pour supprimer des transactions :
- Recherche par mot-clé dans les libellés
- Liste des résultats avec détails
- Suppression ciblée avec confirmation

---

## Gestion des transactions

### Ajouter une transaction

1. **Via Telegram** : Envoyer une photo/PDF/texte au bot
2. **Via l'interface web** : Utiliser le formulaire d'ajout manuel

### Modifier une transaction

1. Cliquer sur ✏️ dans la liste des transactions
2. Corriger les champs (date, libellé, montant, catégorie)
3. Valider avec 💾

### Supprimer une transaction (nouveau v1.2)

**Méthode 1 : Depuis le dashboard**
1. Trouver la transaction dans la liste
2. Cliquer sur 🗑️
3. Confirmer la suppression
4. Le bilan se met à jour automatiquement

**Méthode 2 : Via la page `/delete`**
1. Accéder à `http://FSA-PI5.local:5000/delete`
2. Rechercher par mot-clé (ex: "SAMANRO")
3. Cliquer sur "🗑️ Supprimer" pour la transaction concernée
4. Confirmer

**Méthode 3 : Via l'API**
```bash
curl -X DELETE http://FSA-PI5.local:5000/api/transactions/ID_TRANSACTION
```

---

## Détection et suppression des doublons

### Comment ça marche

Bancami utilise un système de déduplication basé sur :
- **transaction_id** : SHA1 de `date|label|amount` (garantit l'unicité)
- **Vérification avant ajout** : le bot vérifie si la transaction existe déjà
- **Script de nettoyage** : `check_doublons.py` pour identifier les doublons

### Supprimer les doublons manuellement

```bash
# Exécuter le script de nettoyage
ssh fsalazar@FSA-PI5.local "python3 /home/fsalazar/02-bancami/check_doublons.py"

# Le script va :
# 1. Identifier les transactions suspectes (même date + montant)
# 2. Afficher la liste
# 3. Proposer de les supprimer (répondre 'y' pour confirmer)
```

---

## Format des dates

### Format attendu

Bancami reconnaît les formats français :
- **JJ/MM/AAAA** (recommandé) — ex: 31/12/2024
- **JJ/MM/AA** — ex: 31/12/24
- **JJ/MM** — ex: 31/12 (année courante supposée)

### Conversion automatique

Toutes les dates sont converties en format ISO **YYYY-MM-DD** :
- "31/12/2024" → "2024-12-31"
- "31/12/24" → "2024-12-31"
- "31/12" → "2024-12-31" (si année = 2024)

### Problèmes courants

Si une date est mal interprétée :
1. **Corriger via l'interface** : cliquer sur ✏️ et modifier la date
2. **Réimporter le document** : le nouveau prompt (v1.2) gère mieux les dates
3. **Contacter le support** : si le problème persiste

---

## Configuration

### Fichier `.env`

```ini
# Provider LLM (anthropic|mistral)
LLM_PROVIDER=anthropic

# Clé API Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-api03-...

# Clé API Mistral (optionnelle)
# MISTRAL_API_KEY=sk-mistral-...

# Token du bot Telegram
TELEGRAM_BOT_TOKEN=ton_token_ici

# Votre user_id Telegram
TELEGRAM_USER_ID=ton_user_id_ici
```

### Fichiers de données

- `transactions.json` — toutes les transactions
- `budgets.json` — budgets par catégorie
- `global_budget.json` — budget global mensuel
- `rules.json` — règles de classification
- `merchants.json` — mémoire des commerçants

---

## Dépannage

### "Les transactions ne s'affichent pas"
- Vérifier que le service web est actif : `sudo systemctl status budget-web`
- Rafraîchir la page avec Ctrl+F5
- Vérifier les logs : `sudo journalctl -u budget-web -n 50`

### "Le bot Telegram ne répond pas"
- Vérifier le service : `sudo systemctl status budget-bot`
- Redémarrer : `sudo systemctl restart budget-bot`
- Vérifier la clé API Anthropic dans `.env`

### "Des doublons apparaissent"
- Exécuter le script de nettoyage : `python3 check_doublons.py`
- Vérifier que les `transaction_id` sont uniques
- Le système de déduplication est basé sur date+label+montant

### "Les dates sont incorrectes"
- Le format attendu est JJ/MM/AAAA
- Vérifier que l'année est sur 4 chiffres
- Corriger manuellement via l'interface (bouton ✏️)

---

## Mise à jour

### v1.2 → v1.1

```bash
# Arrêter les services
sudo systemctl stop budget-web budget-bot

# Mettre à jour le code
# (méthode dépend de votre workflow de déploiement)

# Redémarrer
sudo systemctl start budget-web budget-bot

# Vérifier
sudo systemctl status budget-web budget-bot
```

---

## Annexe Technique

### Architecture

```
┌───────────────────────────────────────────────────────┐
│                    Bancami v1.2                        │
├─────────────────┬─────────────────┬───────────────────┤
│  Bot Telegram    │  Interface Web  │  Données          │
│  (budget-bot)    │  (budget-web)    │  (JSON)           │
└─────────────────┴─────────────────┴───────────────────┘
       ▲                  ▲                  ▲
       │                  │                  │
┌──────┴──────┐    ┌──────┴──────┐    ┌──────┴──────┐
│  Telegram  │    │  Navigateur  │    │  Fichiers  │
│  API        │    │  Web         │    │  JSON       │
└─────────────┘    └─────────────┘    └─────────────┘
```

### Fichiers principaux

```
02-bancami/
├── bot.py                  # Bot Telegram principal
├── web.py                  # Serveur web Flask
├── extractor.py            # Extraction via Claude API
├── classifier.py          # Classification des transactions
├── budget.py              # Gestion des budgets
├── storage.py             # Stockage des transactions
├── config.py              # Configuration et variables d'environnement
├── llm_wrapper.py         # Abstraction LLM (Anthropic/Mistral)
├── 
├── templates/             # Templates web (Jinja2)
│   ├── base.html           # Template de base
│   ├── dashboard.html      # Dashboard principal
│   ├── admin.html          # Onglet admin
│   └── delete.html         # Page de suppression
├── 
├── transactions.json      # Données des transactions
├── budgets.json           # Budgets par catégorie
├── global_budget.json     # Budget global mensuel
├── rules.json             # Règles de classification
├── merchants.json         # Mémoire des commerçants
├── 
├── .env                   # Variables d'environnement
├── requirements.txt       # Dépendances Python
├── bancami-v1.2.md        # Documentation (ce fichier)
└── README.md              # Documentation principale
```

### Dépendances

#### Python (requirements.txt)

```ini
# Bot Telegram
python-telegram-bot==22.7

# API Anthropic Claude
anthropic==0.34.2

# Interface web
Flask==3.1.3

# Variables d'environnement
python-dotenv==1.2.2

# Dépendances transitives
numpy==1.26.4
matplotlib==3.9.2
```

#### Système

- Python 3.13+
- systemd (pour les services)
- curl (pour les requêtes API)
- jq (optionnel, pour le traitement JSON en CLI)

### Configuration système

#### Services systemd

Deux services sont configurés :

1. **budget-web.service** - Interface web
   - Port: 5000
   - Utilisateur: fsalazar
   - Redémarrage automatique

2. **budget-bot.service** - Bot Telegram
   - Utilisateur: fsalazar
   - Redémarrage automatique
   - Limite mémoire: 256Mo

#### Commandes utiles

```bash
# Démarrer les services
sudo systemctl start budget-web budget-bot

# Arrêter les services
sudo systemctl stop budget-web budget-bot

# Redémarrer
sudo systemctl restart budget-web budget-bot

# Voir les logs
sudo journalctl -u budget-web -f
sudo journalctl -u budget-bot -f

# Vérifier le statut
sudo systemctl status budget-web budget-bot
```

### Base de données

Bancami utilise des fichiers JSON plats :

- **transactions.json** : Liste de toutes les transactions
  ```json
  {
    "transactions": [
      {
        "date": "YYYY-MM-DD",
        "label": "LIBELLÉ",
        "amount": 37.14,
        "currency": "EUR",
        "type": "debit|credit",
        "transaction_id": "sha1_hash",
        "category": "🛒 Catégorie",
        "added_at": "ISO_timestamp"
      }
    ]
  }
  ```

- **budgets.json** : Budgets par catégorie
  ```json
  {
    "🛒 Supermarché": 400,
    "🥩 Boucherie": 80,
    "🌿 Bio": 60
  }
  ```

### Algorithmes clés

#### Déduplication

```python
def _generate_transaction_id(date: str, label: str, amount: float) -> str:
    """SHA1 de date|label|amount — clé de déduplication."""
    raw = f"{date}|{label.upper()}|{amount:.2f}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
```

#### Classification

1. Règles statiques (RULES dans classifier.py)
2. Mémoire apprise (merchants.json)
3. Claude API (fallback)

#### Format des dates

```python
# Conversion JJ/MM/AAAA → YYYY-MM-DD
def convert_french_date(french_date: str, current_year: int) -> str:
    """Convertit une date française en ISO."""
    parts = french_date.split('/')
    
    if len(parts) == 3:  # JJ/MM/AAAA ou JJ/MM/AA
        day, month, year_part = parts
        if len(year_part) == 2:  # JJ/MM/AA
            year = 2000 + int(year_part)
        else:  # JJ/MM/AAAA
            year = int(year_part)
    else:  # JJ/MM
        day, month = parts
        year = current_year
    
    return f"{year:04d}-{int(month):02d}-{int(day):02d}"
```

### API REST

#### Endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/` | Dashboard principal |
| GET | `/admin` | Onglet admin (échanges LLM) |
| GET | `/delete` | Interface de suppression |
| GET | `/api/transactions` | Liste des transactions |
| PATCH | `/api/transactions/<id>` | Modifier une transaction |
| DELETE | `/api/transactions/<id>` | Supprimer une transaction |
| GET | `/api/bilan` | Bilan par catégorie |
| GET | `/api/burndown` | Données du burndown chart |
| GET/PUT | `/api/settings/global-budget` | Budget global |
| GET/PUT | `/api/settings/budgets` | Budgets par catégorie |
| GET/PUT/DELETE | `/api/settings/rules` | Règles de classification |

#### Exemple de requête

```bash
# Supprimer une transaction
curl -X DELETE http://localhost:5000/api/transactions/abc123

# Modifier une transaction
curl -X PATCH http://localhost:5000/api/transactions/abc123 \
  -H "Content-Type: application/json" \
  -d '{"category": "🛒 Supermarché"}'

# Lister les transactions
curl http://localhost:5000/api/transactions | jq '.'
```

### Scripts utilitaires

#### check_doublons.py

Identifie et supprime les transactions dupliquées :

```bash
python3 check_doublons.py
```

#### clean_doublons.py

Version automatique sans confirmation :

```bash
python3 clean_doublons.py
```

#### find_duplicates.py

Recherche de doublons (lecture seule) :

```bash
python3 find_duplicates.py < transactions.json
```

### Performances

- **Temps de réponse API** : < 100ms (moyenne)
- **Extraction Claude** : ~2-5s par image
- **Mémoire** : < 256Mo par service
- **Stockage** : ~10Ko par transaction

### Sécurité

- **Authentification Telegram** : Whitelist stricte par user_id
- **Pas de données sensibles** : Seuls les libellés et montants sont stockés
- **Pas d'accès externe** : Services accessibles uniquement en local
- **Sauvegardes** : Fichiers JSON faciles à sauvegarder

### Déploiement

#### Première installation

```bash
# Cloner le dépôt (ou copier les fichiers)
git clone https://github.com/you/budget-bot.git
cd budget-bot

# Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Configurer .env
cp .env.example .env
nano .env  # Remplir les clés API

# Installer les services systemd
sudo cp budget-bot.service budget-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable budget-bot budget-web
sudo systemctl start budget-bot budget-web
```

#### Mise à jour

```bash
# Arrêter les services
sudo systemctl stop budget-web budget-bot

# Mettre à jour le code
# (selon votre workflow: git pull, rsync, scp, etc.)

# Installer les nouvelles dépendances (si besoin)
venv/bin/pip install -r requirements.txt

# Redémarrer
sudo systemctl start budget-web budget-bot

# Vérifier
sudo systemctl status budget-web budget-bot
curl http://localhost:5000/api/transactions
```

### Dépannage avancé

#### Vérifier les logs

```bash
# Logs du bot Telegram
sudo journalctl -u budget-bot -n 100 -f

# Logs du serveur web
sudo journalctl -u budget-web -n 100 -f

# Logs systemd complets
sudo journalctl -xe
```

#### Tester l'API manuellement

```bash
# Tester l'API transactions
curl -v http://localhost:5000/api/transactions

# Tester la santé
curl -v http://localhost:5000/api/health

# Tester une suppression
curl -X DELETE http://localhost:5000/api/transactions/ID_TEST
```

#### Réinitialiser les données

```bash
# Sauvegarder les données existantes
cp transactions.json transactions.json.bak

# Réinitialiser
echo '{"transactions": []}' > transactions.json

# Redémarrer le service web
sudo systemctl restart budget-web
```

#### Problèmes courants

**Problème** : Le bot ne répond pas
**Solution** :
```bash
sudo systemctl restart budget-bot
journalctl -u budget-bot -n 50
```

**Problème** : L'interface ne se charge pas
**Solution** :
```bash
sudo systemctl restart budget-web
curl -v http://localhost:5000
```

**Problème** : Les transactions ne sont pas extraites
**Solution** :
```bash
# Vérifier la clé API Anthropic dans .env
# Tester l'API Claude manuellement
python3 -c "import anthropic; print(anthropic.Anthropic().messages.create(...))"
```

---

## Support

- **Documentation** : Ce fichier et `README.md`
- **Code source** : Disponible sur demande
- **Auteur** : François Salazar
- **Plateforme** : Raspberry Pi 5 (FSA-PI5.local)

---

*Document généré le 10/04/2026 — Bancami v1.2* 💰