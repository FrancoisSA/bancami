#!/bin/bash
# Script pour trouver et supprimer les transactions dupliquées

# Chemin vers le fichier transactions.json
TRANSACTIONS_FILE="/home/fsalazar/02-bancami/transactions.json"

# Vérifier que le fichier existe
if [ ! -f "$TRANSACTIONS_FILE" ]; then
    echo "❌ Fichier $TRANSACTIONS_FILE non trouvé"
    exit 1
fi

# Compter le nombre total de transactions
TOTAL=$(jq '.transactions | length' "$TRANSACTIONS_FILE")
echo "📊 Nombre total de transactions: $TOTAL"

# Trouver les doublons (même date + label + montant)
echo -e "\n🔍 Recherche de doublons..."

# Créer un fichier temporaire pour les IDs uniques
TMP_FILE=$(mktemp)

# Trouver et afficher les doublons
jq -r '.transactions[] | "\(.date)|\(.label)|\(.amount)|\(.transaction_id)"' "$TRANSACTIONS_FILE" | \
  sort | \
  uniq -d -w 1000 | \  # -w 1000 pour comparer toute la ligne sauf l'ID
  while IFS='|' read -r date  amount id; do
      echo "⚠️  Doublon trouvé: $date | $label | ${amount}€ | ID: $id"
      echo "$id" >> "$TMP_FILE"
  done

# Compter les doublons
DUP_COUNT=$(wc -l < "$TMP_FILE" 2>/dev/null || echo "0")

if [ "$DUP_COUNT" -eq "0" ]; then
    echo "✅ Aucun doublon trouvé dans le fichier."
    echo "Si vous voyez des doublons dans l'interface, ils peuvent venir:"
    echo "  1. D'un problème d'affichage (rafraîchissez la page)"
    echo "  2. De transactions avec des IDs différents mais des données similaires"
    echo "  3. Du bot Telegram qui réimporté des données"
else
    echo -e "\n⚠️  $DUP_COUNT transaction(s) dupliquée(s) trouvée(s)"
    echo "IDs des transactions dupliquées:"
    cat "$TMP_FILE"
    
    read -p "Voulez-vous supprimer ces doublons ? [y/N] " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Suppression des doublons..."
        
        # Supprimer chaque doublon via l'API
        while read -r tx_id; do
            echo "Suppression de $tx_id..."
            curl -s -X DELETE "http://localhost:5000/api/transactions/$tx_id" | jq '.ok'
        done < "$TMP_FILE"
        
        echo "✅ Suppression terminée. Rafraîchissez l'interface."
    fi
fi

# Nettoyer
rm -f "$TMP_FILE"
