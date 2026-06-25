# ERI-ESI 2017, Pipeline de traitement de données

Pipeline reproductible et scalable pour extraire, traiter et consolider les données de l'Enquête Régionale Intégrée sur l'Emploi et le Secteur Informel (ERI-ESI), volet Emploi, Sénégal, 2017.

> Projet ENSAE, cours Traitement de données, Groupe 1

## Structure du projet

```
.
├── input/<PAYS>/        Données brutes (.dta), non versionnées
├── output/<PAYS>/       Tables produites par le pipeline (.dta), non versionnées
├── scripts/
│   ├── stata/           Pipeline principal (extraction, fusion, modules thématiques)
│   └── python/          Fichier QAQC (estimations de contrôle)
├── docs/                Dictionnaire de variables, notes
└── README.md
```

## Démarrage rapide

Dans Stata :

```stata
cd "scripts/stata"
do 01_fusion.do
```

Génère `output/SEN/base_individus_emploi_fusionnee.dta`, la base de travail commune sur laquelle chaque module thématique vient ajouter ses variables dérivées.

## Pipeline

| Étape | Fichier | Rôle |
|---|---|---|
| 1 | `scripts/stata/config.do` | Paramètres du pays actif (pays, chemins, clés de fusion) |
| 2 | `scripts/stata/01_fusion.do` | Fusion individus ↔ emploi |
| 3 | `scripts/stata/03_*.do` | Modules thématiques (un par membre du groupe) |
| 4 | `scripts/python/04_qaqc.py` | Contrôle qualité et estimations primaires |

## Adapter à un autre pays

Toute la configuration spécifique à un pays est centralisée dans `scripts/stata/config.do`. Changer `PAYS` et, si besoin, les noms de clés (`CLES_INDIVIDUS`/`CLES_EMPLOI`) suffit, sans modifier le reste du pipeline.

## Répartition des tâches

Voir [`repartition.html`](repartition.html) pour le détail des rôles et livrables de chaque membre du groupe.

## Livrables attendus

- Pipeline de traitement (code)
- Deux tables consolidées : individus et ménages
- Fichier QAQC (estimations primaires de contrôle)
- Résumé final (PDF)
