# UC03 — Cycle HITL complet (approbation mobile)

**Acteur principal** : Supervisor + comptable superviseur (humain)  
**Déclencheur** : `hitl_pending: true` détecté dans SharedState

## Préconditions
- SharedState contient le détail de l'exception (`reconciliation_gaps` ou équivalent)
- Gmail MCP connecté
- Webhook Flask en écoute (ngrok actif en dev)
- SqliteSaver configuré comme checkpointer

## Flux principal
1. Le Supervisor appelle `interrupt()` — thread LangGraph suspendu, état persisté via SqliteSaver
2. Le Supervisor construit un email structuré : contexte client, détail du gap, montant, suggestion
3. L'email contient 3 liens d'action : **Approuver** / **Modifier** / **Bloquer**
4. Gmail MCP envoie l'email au comptable superviseur
5. Le comptable reçoit l'email sur son iPhone et clique un lien
6. Le clic déclenche une requête HTTP GET vers le webhook Flask (`/webhook?thread_id=xxx&decision=approve`)
7. Le webhook écrit la décision dans SharedState (`hitl_decision`, `hitl_pending: false`)
8. LangGraph reprend le thread suspendu au point exact d'interruption
9. Le Supervisor route selon la décision : exécute, modifie, ou bloque l'action

## Flux alternatif — timeout 4 heures
- Le timeout handler injecte `hitl_decision: "timeout"` dans SharedState
- Le Supervisor escalade automatiquement en N4

## Flux alternatif — décision "Modifier"
- Le webhook capture le commentaire et l'écrit dans SharedState (`hitl_comment`)
- Le Supervisor re-route vers le Reconciliation Agent avec le commentaire comme contrainte

## Postconditions
- Décision humaine tracée dans SharedState
- Thread LangGraph repris ou clos proprement
- Action exécutée, modifiée ou bloquée selon la décision
