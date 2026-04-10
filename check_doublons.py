#!/usr/bin/env python3
"""
Script pour trouver et supprimer les transactions dupliquées.
Version améliorée avec détection plus large et option de suppression.
"""

import json
import sys
from collections import defaultdict

def load_transactions(filepath):
    """Charge les transactions depuis le fichier JSON."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('transactions', [])
    except FileNotFoundError:
        print(f"❌ Fichier {filepath} non trouvé")
        sys.exit(1)
    except json.JSONDecodeError:
        print("❌ Fichier JSON invalide")
        sys.exit(1)

def find_duplicates(transactions):
    """
    Trouve les doublons basés sur date+label+amount.
    Retourne un dictionnaire {clé: [liste_de_transactions]}
    """
    # Créer une clé unique pour chaque transaction (sans l'ID)
    def make_key(tx):
        return (tx['date'], tx['label'].strip(), float(tx['amount']), tx.get('type', 'debit'))
    
    groups = defaultdict(list)
    for tx in transactions:
        groups[make_key(tx)].append(tx)
    
    # Retourner seulement les groupes avec plusieurs occurrences
    return {k: v for k, v in groups.items() if len(v) > 1}

def delete_transaction(tx_id, api_url="http://localhost:5000"):
    """Supprime une transaction via l'API."""
    import urllib.request
    import urllib.parse
    
    url = f"{api_url}/api/transactions/{tx_id}"
    req = urllib.request.Request(url, method='DELETE')
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('ok', False)
    except Exception as e:
        print(f"❌ Erreur lors de la suppression: {e}")
        return False

def main():
    filepath = "/home/fsalazar/02-bancami/transactions.json"
    
    print("🔍 Analyse des transactions...")
    transactions = load_transactions(filepath)
    print(f"📊 Nombre total de transactions: {len(transactions)}")
    
    duplicates = find_duplicates(transactions)
    
    if not duplicates:
        print("\n✅ Aucun doublon exact trouvé (même date + label + montant + type)")
        
        # Recherche plus large: mêmes date+montant mais labels similaires
        print("\n🔍 Recherche de transactions suspectes (même date+montant)...")
        
        key_func = lambda t: (t['date'], float(t['amount']))
        date_amount_groups = defaultdict(list)
        for tx in transactions:
            date_amount_groups[key_func(tx)].append(tx)
        
        suspicious = []
        for key, txs in date_amount_groups.items():
            if len(txs) > 1:
                # Vérifier si les labels sont similaires
                labels = [tx['label'].lower() for tx in txs]
                # Si au moins deux labels partagent 80% de caractères communs
                for i, label1 in enumerate(labels):
                    for label2 in labels[i+1:]:
                        common = len(set(label1) & set(label2))
                        total = len(set(label1) | set(label2))
                        if total > 0 and common/total > 0.8:
                            suspicious.append(txs)
                            break
                    
        if suspicious:
            print(f"⚠️  Trouvé {len(suspicious)} groupe(s) de transactions suspectes:")
            for i, txs in enumerate(suspicious, 1):
                print(f"\nGroupe {i}:")
                for tx in txs:
                    print(f"  {tx['date']} | {tx['amount']:7.2f}€ | {tx['label'][:50]}")
                    print(f"  ID: {tx['transaction_id']}")
        else:
            print("✅ Aucune transaction suspecte trouvée")
            
        return
    
    print(f"\n⚠️  Trouvé {len(duplicates)} groupe(s) de transactions dupliquées:")
    
    all_dup_ids = []
    for i, (key, txs) in enumerate(duplicates.items(), 1):
        print(f"\nGroupe {i} ({len(txs)} occurrences):")
        for tx in txs:
            print(f"  - {tx['date']} | {tx['label'][:40]:40} | {tx['amount']:7.2f}€")
            print(f"    ID: {tx['transaction_id']}")
            all_dup_ids.append(tx['transaction_id'])
    
    print(f"\n📋 Total: {len(all_dup_ids)} transactions dupliquées")
    
    # Proposer la suppression
    response = input("\nVoulez-vous supprimer ces doublons ? [y/N] ").strip().lower()
    
    if response == 'y':
        print("🗑️  Suppression en cours...")
        deleted_count = 0
        
        for tx_id in all_dup_ids:
            # Garder la première occurrence, supprimer les autres
            if delete_transaction(tx_id):
                print(f"✅ Supprimé: {tx_id}")
                deleted_count += 1
            else:
                print(f"❌ Échec suppression: {tx_id}")
        
        print(f"\n✅ {deleted_count}/{len(all_dup_ids)} transactions supprimées")
        print("💡 Rafraîchissez l'interface pour voir les changements")

if __name__ == "__main__":
    main()
