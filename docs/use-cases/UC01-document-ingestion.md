# UC01 — Ingestion de document financier

**Acteur principal** : Ingestion Agent  
**Déclencheur** : Arrivée d'un email avec pièce jointe dans la boîte Gmail du cabinet

## Préconditions
- Gmail MCP connecté et authentifié
- QBO MCP connecté et authentifié
- SharedState initialisé

## Flux principal
1. L'Ingestion Agent interroge Gmail MCP pour les emails non traités
2. Il détecte une pièce jointe (PDF, CSV, image)
3. Il classifie le document : facture fournisseur, relevé bancaire, reçu, autre
4. Il extrait les métadonnées clés : date, montant, devise, fournisseur/client, numéro de document
5. Il crée ou met à jour l'entrée correspondante dans QBO via QBO MCP
6. Il écrit le delta dans SharedState (`documents_ingested`, `routing_signal`)
7. Le Supervisor reçoit le signal et route vers le Reconciliation Agent

## Flux alternatif — document non reconnu
- À l'étape 3, si la classification échoue (confiance < seuil)
- L'agent écrit `routing_signal: "unrecognized"` dans SharedState
- Le Supervisor déclenche une escalade N4 (transfert humain)

## Postconditions
- Document classifié et enregistré dans QBO
- SharedState mis à jour avec les métadonnées du document
- Routing signal émis vers l'étape suivante
