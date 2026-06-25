# ERI-ESI 2017, Pipeline de traitement de données

Pipeline reproductible et scalable pour extraire, traiter et consolider les données de l'Enquête Régionale Intégrée sur l'Emploi et le Secteur Informel (ERI-ESI), volet Emploi, Sénégal, 2017.

> Projet ENSAE, cours Traitement de données, Groupe 1

## Structure du projet

```
.
├── input/<PAYS>/        Données brutes (.dta)
├── output/<PAYS>/       Tables produites par le pipeline
├── scripts/             Pipeline Python
├── docs/                Dictionnaire de variables, notes
└── README.md
```

## Démarrage rapide

```bash
cd scripts
python 02_merge.py SEN
```

Génère `output/SEN/base_individus_emploi_fusionnee.csv`, la base de travail commune sur laquelle chaque module thématique vient ajouter ses variables dérivées.

## Pipeline

| Étape | Script | Rôle |
|---|---|---|
| 1 | `01_extract.py` | Lecture des fichiers `.dta` |
| 2 | `02_merge.py` | Fusion individus ↔ emploi |
| 3 | `03_*.py` | Modules thématiques (un par membre du groupe) |
| 4 | `04_qaqc.py` | Contrôle qualité et estimations primaires |

## Adapter à un autre pays

Toute la configuration spécifique à un pays est centralisée dans `scripts/config.py`. Ajouter un bloc dans `PAYS_CONFIG` suffit, sans modifier le reste du pipeline.

## Répartition des tâches

Voir [`repartition.html`](repartition.html) pour le détail des rôles et livrables de chaque membre du groupe.

## Livrables attendus

- Pipeline de traitement (code)
- Deux tables consolidées : individus et ménages
- Fichier QAQC (estimations primaires de contrôle)
- Résumé final (PDF)
