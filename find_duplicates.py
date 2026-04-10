#!/usr/bin/env python3
"""
Script pour trouver et afficher les transactions dupliquées.
"""

import json
import sys
from collections import defaultdict

def find_duplicates(transactions):
    """Trouve les doublons basés sur date+label+amount."""
    # Créer une clé unique pour chaque transaction (sans l'ID)
    key_func = lambda t: (t['date'], t['label'], t['amount'], t['type'])
    
    # Grouper par clé
    groups = defaultdict(list)
    for tx in transactions:
        groups[key_func(tx)].append(tx)
    
    # Retourner seulement les groupes avec plusieurs occurrences
    return {k: v for k, v in groups.items() if len(v) > 1}

def main():
    try:
        data = json.load(sys.stdin)
        transactions = data.get('transactions', [])
        
        duplicates = find_duplicates(transactions)
        
        if not duplicates:
            print("✅ Aucune transaction dupliquée trouvée.")
            return
        
        print(f"⚠️  Trouvé {len(duplicates)} groupe(s) de transactions dupliquées:\n")
        
        for i, (key, txs) in enumerate(duplicates.items(), 1):
            print(f"Groupe {i} ({len(txs)} occurrences):")
            for tx in txs:
                print(f"  - {tx['date']} | {tx['label'][:40]:40} | {tx['amount']:7.2f}€ | ID: {tx['transaction_id']}")
            print()
            
    except json.JSONDecodeError:
        print("❌ Erreur: Fichier JSON invalide")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
