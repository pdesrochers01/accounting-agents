# UC02 — Réconciliation et détection de gap

**Acteur principal** : Reconciliation Agent  
**Déclencheur** : Signal de routing reçu depuis le Supervisor après UC01

## Préconditions
- SharedState contient au moins un document ingéré (`documents_ingested` non vide)
- QBO MCP accessible (transactions et comptes)

## Flux principal
1. Le Reconciliation Agent lit les transactions en attente depuis QBO MCP
2. Il charge le relevé bancaire de référence depuis SharedState
3. Il exécute le matching transaction par transaction (montant, date ±3 jours, fournisseur)
4. Il calcule les gaps : transactions non matchées, montants discordants
5. Si tous les gaps sont sous le seuil N1 (<$500 CAD) : écrit le résultat dans SharedState et termine
6. Si un gap dépasse le seuil N3 (>$2 000 CAD) : écrit `hitl_pending: true` et le détail dans SharedState
7. Le Supervisor détecte `hitl_pending` et déclenche UC03

## Flux alternatif — aucune transaction à réconcilier
- À l'étape 1, si QBO ne retourne aucune transaction en attente
- L'agent écrit `routing_signal: "nothing_to_reconcile"` dans SharedState
- Le Supervisor termine le cycle proprement

## Postconditions
- Gaps documentés dans SharedState (`reconciliation_gaps`)
- Routing signal émis : cycle terminé (N1) ou HITL déclenché (N3)
