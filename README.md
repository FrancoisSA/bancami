# Budget Bot — Suivi budgétaire via Telegram

Bot Telegram personnel qui extrait automatiquement les transactions depuis des captures d'écran bancaires via Claude Vision, les classe par catégorie, et génère un burndown chart mensuel.

## Pré-requis

- Raspberry Pi 5, Raspberry Pi OS Bookworm 64-bit (ARM64)
- Connexion internet
- Un compte Telegram et un bot créé via @BotFather
- Une clé API Anthropic

---

## Installation sur Raspberry Pi OS Bookworm

### 1. Créer le bot Telegram

1. Ouvrir Telegram et chercher **@BotFather**
2. Envoyer `/newbot`, suivre les instructions → noter le **token** (format `1234567890:ABCdef…`)
3. Pour obtenir ton **user_id** Telegram, envoyer un message à **@userinfobot**

### 2. Mettre à jour le système

```bash
sudo apt update && sudo apt upgrade -y
```

### 3. Installer les dépendances système

```bash
sudo apt install -y \
    python3-venv \
    python3-pip \
    libopenblas-dev \
    libatlas-base-dev
```

> `libopenblas-dev` et `libatlas-base-dev` sont requis par numpy/matplotlib sur ARM64.

### 4. Cloner / copier les fichiers du projet

```bash
mkdir -p /home/pi/budget-bot
# Copier tous les fichiers du projet dans ce dossier
cd /home/pi/budget-bot
```

### 5. Créer le virtualenv et installer les dépendances

```bash
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
```

### 6. Configurer le `.env`

```bash
cp .env.example .env
nano .env
```

Remplir les valeurs :

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdef…
ANTHROPIC_API_KEY=sk-ant-…
TELEGRAM_USER_ID=123456789
```

### 7. Tester manuellement

```bash
venv/bin/python bot.py
```

Envoyer `/start` depuis Telegram → le bot doit répondre.  
Arrêter avec `Ctrl+C` une fois le test terminé.

### 8. Installer le service systemd

```bash
# Adapter WorkingDirectory dans le fichier si besoin
sudo cp budget-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable budget-bot
sudo systemctl start budget-bot
```

### 9. Vérifier que le bot tourne

```bash
# Statut du service
systemctl status budget-bot

# Logs en direct
journalctl -u budget-bot -f

# Logs applicatifs (avec rotation)
tail -f /home/pi/budget-bot/budget-bot.log
```

---

## Utilisation

| Action | Résultat |
|---|---|
| Envoyer une photo | Extraction + classification automatique |
| `/bilan` | Bilan texte du mois courant par catégorie |
| `/graphique` | Burndown chart PNG |
| `/transactions [N]` | N dernières transactions (défaut : 10) |
| `/budget` | Budgets mensuels par catégorie |
| `/reset_mois` | Remet les transactions du mois à zéro |
| `/sante` | Uptime, disque, température CPU |

---

## Personnalisation

### Modifier les budgets

Éditer `budget.py` → dictionnaire `MONTHLY_BUDGETS`.

### Ajouter des règles de classification

Éditer `classifier.py` → dictionnaire `RULES`.  
Format : `"MOT_CLÉ_EN_MAJUSCULES": "🏷️ Catégorie"`.

---

## Structure des fichiers

```
budget-bot/
├── bot.py                  # Point d'entrée principal
├── extractor.py            # Extraction via Claude Vision
├── storage.py              # Stockage JSON atomique
├── classifier.py           # Classification par catégorie
├── budget.py               # Définition des budgets
├── charts.py               # Burndown chart matplotlib
├── config.py               # Chargement des variables d'env
├── transactions.json        # Base de données (auto-créée)
├── merchants.json           # Mémoire commerçants (auto-créée)
├── budget-bot.log          # Logs rotatifs (auto-créé)
├── .env                    # Variables sensibles (NE PAS commiter)
├── .env.example            # Modèle .env
├── requirements.txt
└── budget-bot.service      # Service systemd
```
