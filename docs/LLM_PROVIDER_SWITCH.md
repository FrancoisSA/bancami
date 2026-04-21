# Plan de Migration LLM : Anthropic ↔ Mistral

## Objectif
Permettre de basculer entre Anthropic et Mistral pour le traitement LLM via configuration.

## Architecture Proposée

### 1. Configuration (`config.py`)
```python
# Ajouter dans config.py
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")  # "anthropic" ou "mistral"
MISTRAL_API_KEY: str | None = os.getenv("MISTRAL_API_KEY")
```

### 2. Wrapper LLM (`llm_wrapper.py` - Nouveau)
```python
"""
Wrapper unifié pour les providers LLM.
Permet de basculer entre Anthropic et Mistral sans modifier le code métier.
"""

from importlib import import_module
import config
from typing import Any


def get_llm_client() -> Any:
    """Retourne un client LLM configuré selon LLM_PROVIDER."""
    if config.LLM_PROVIDER == "anthropic":
        anthropic = import_module("anthropic")
        return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    
    elif config.LLM_PROVIDER == "mistral":
        if not config.MISTRAL_API_KEY:
            raise ValueError("MISTRAL_API_KEY requis pour le provider mistral")
        # Implémentation Mistral à ajouter
        # mistral = import_module("mistralai")
        # return mistral.Mistral(api_key=config.MISTRAL_API_KEY)
        pass
    
    else:
        raise ValueError(f"Provider LLM inconnu: {config.LLM_PROVIDER}")


def extract_text_from_image(client: Any, image_data: bytes) -> str:
    """Interface unifiée pour l'extraction de texte."""
    if config.LLM_PROVIDER == "anthropic":
        from classifier import anthropic_extract_text
        return anthropic_extract_text(client, image_data)
    
    elif config.LLM_PROVIDER == "mistral":
        # Implémentation Mistral à ajouter
        pass
```

### 3. Modifications Requises

#### `bot.py`
```python
# Remplacer
import anthropic
client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

# Par
from llm_wrapper import get_llm_client, extract_text_from_image
client = get_llm_client()
```

#### `extractor.py`
```python
# Remplacer les appels directs à anthropic par des appels à llm_wrapper
```

### 4. Configuration Utilisateur

#### `.env`
```ini
# Provider LLM (anthropic|mistral)
LLM_PROVIDER=anthropic

# Clé API Anthropic (requise si anthropic)
ANTHROPIC_API_KEY=sk-ant-...

# Clé API Mistral (requise si mistral)
MISTRAL_API_KEY=
```

#### `.env.example`
```ini
# Provider LLM (anthropic|mistral)
LLM_PROVIDER=anthropic

# Clé API Anthropic
ANTHROPIC_API_KEY=votre_cle_ici

# Clé API Mistral (optionnelle)
MISTRAL_API_KEY=votre_cle_mistral_ici
```

### 5. Documentation Utilisateur

Ajouter dans `README.md` :

```markdown
## Configuration du Provider LLM

Bancami supporte deux providers LLM pour le traitement des images et texte :

- **Anthropic** (défaut) - Utilise Claude
- **Mistral** (optionnel) - Alternative open-source

### Configuration

1. Éditez votre fichier `.env`
2. Choisissez votre provider :
   ```ini
   LLM_PROVIDER=anthropic  # ou "mistral"
   ```
3. Fournissez la clé API correspondante :
   - Pour Anthropic : `ANTHROPIC_API_KEY=sk-ant-...`
   - Pour Mistral : `MISTRAL_API_KEY=...`

### Migration

Pour basculer de provider :
1. Arrêtez le bot : `sudo systemctl stop budget-bot`
2. Modifiez `.env`
3. Redémarrez : `sudo systemctl start budget-bot`

⚠️ Assurez-vous que le provider cible est supporté par votre version de Bancami.
```

## Checklist d'Implémentation

- [ ] Créer `llm_wrapper.py`
- [ ] Modifier `config.py`
- [ ] Adapter `bot.py`
- [ ] Adapter `extractor.py`
- [ ] Mettre à jour `.env.example`
- [ ] Documenter dans README.md
- [ ] Tester avec Anthropic
- [ ] Implémenter support Mistral
- [ ] Tester avec Mistral
- [ ] Mettre à jour la documentation utilisateur

## Notes Techniques

1. **Compatibilité** : Le wrapper doit maintenir la même interface quel que soit le provider
2. **Gestion d'erreur** : Messages clairs si clé API manquante
3. **Performance** : Les deux providers doivent avoir des temps de réponse comparables
4. **Fallback** : Envisager un mécanisme de fallback si un provider est indisponible

## Implémentation Future

- Ajouter support pour d'autres providers (OpenAI, Groq, etc.)
- Implémenter un système de fallback automatique
- Ajouter des métriques de performance par provider
- Permettre la configuration via l'interface web
