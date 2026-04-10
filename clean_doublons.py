#!/usr/bin/env python3
"""
Script pour supprimer automatiquement les transactions dupliquées.
"""

import json
from collections import defaultdict
import urllib.request

def load_transactions():
    with open('/home/fsalazar/02-bancami/transactions.json', 'r') as f:
        return json.load(f).get('transactions', [])

def delete_transaction(tx_id):
    url = f"http://localhost:5000/api/transactions/{tx_id}"
    req = urllib.request.Request(url, method='DELETE')
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8')).get('ok', False)
    except Exception as e:
        print(f"Erreur suppression {tx_id}: {e}")
        return False

def main():
    print("🔍 Recherche et suppression des doublons...")
    transactions = load_transactions()
    print(f"📊 {len(transactions)} transactions chargées")
    
    # Grouper par date+montant
    key_func = lambda t: (t['date'], float(t['amount']))
    groups = defaultdict(list)
    for tx in transactions:
        groups[key_func(tx)].append(tx)
    
    # Trouver les groupes avec plusieurs transactions
    duplicates = [txs for txs in groups.values() if len(txs) > 1]
    
    if not duplicates:
        print("✅ Aucun doublon trouvé")
        return
    
    print(f"⚠️  {len(duplicates)} groupe(s) de doublons trouvé(s)")
    
    deleted = 0
    for txs in duplicates:
        # Garder la première transaction, supprimer les autres
        for tx in txs[1:]:
            if delete_transaction(tx['transaction_id']):
                print(f"✅ Supprimé: {tx['date']} | {tx['label'][:30]} | {tx['amount']}€")
                deleted += 1
            else:
                print(f"❌ Échec: {tx['transaction_id']}")
    
    print(f"\n✅ Terminée: {deleted} transaction(s) supprimée(s)")

if __name__ == "__main__":
    main()
