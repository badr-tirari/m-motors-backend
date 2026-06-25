# M-Motors — Backend (API)

Refonte digitale M-Motors (achat / location longue durée avec option d'achat).
Backend FastAPI — Bachelor Développeur d'application Python, bloc "Développer une solution digitale".

Backlog complet : projet Jira **MMOT** — https://tiraribadr.atlassian.net/jira/software/projects/MMOT/boards/68/backlog

## Stack

- **Python 3.11** / FastAPI
- **PostgreSQL** (Azure Database for PostgreSQL en production — voir US-14)
- SQLAlchemy 2.0 (ORM)
- Passlib/bcrypt (hash des mots de passe)
- Pytest + httpx (tests)

## Démarrage local

```bash
python -m venv .venv
source .venv/bin/activate          # .venv\Scripts\activate sous Windows
pip install -r requirements.txt
cp .env.example .env                # adapter DATABASE_URL si besoin
uvicorn app.main:app --reload
```

API disponible sur http://localhost:8000 — doc interactive sur `/docs`.

## Tests

```bash
pytest -v
```

Les tests unitaires utilisent une base SQLite en mémoire (isolée, rapide), indépendante de la base PostgreSQL de dev/prod.

## Stratégie Git

Modèle **Git Flow simplifié** :

- `main` — code stable, déployable
- `develop` — branche d'intégration des fonctionnalités
- `feature/US-XX-nom-court` — une branche par user story du backlog Jira (MMOT-7 à MMOT-22)

Chaque feature est développée isolément, testée, puis mergée dans `develop` via merge commit (`--no-ff`) pour garder une trace explicite de chaque user story dans l'historique. `develop` est mergée dans `main` lors des livraisons de sprint.

### User stories livrées dans ce dépôt

| Branche | Story Jira | Description |
|---|---|---|
| `feature/US-01-register` | [MMOT-7](https://tiraribadr.atlassian.net/browse/MMOT-7) | Créer un compte client |

## Démarche de développement d'une user story

1. Lecture des critères d'acceptation sur le ticket Jira
2. Création de la branche `feature/US-XX-...` depuis `develop`
3. Implémentation : modèle ORM → schéma Pydantic → endpoint → tests unitaires
4. Exécution de la suite de tests (`pytest`)
5. Merge dans `develop` (`--no-ff`), ticket Jira passé en "Terminé" une fois déployé
6. Revue de code (auto-revue documentée dans les messages de commit)
