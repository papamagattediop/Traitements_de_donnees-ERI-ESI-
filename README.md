# ERI-ESI 2017 -- Pipeline de traitement des données (Groupe 1)

Pipeline reproductible de traitement des données de l'Enquête Régionale Intégrée
sur l'Emploi et le Secteur Informel (ERI-ESI 2017), volet Sénégal. Le code est
conçu pour être généralisable aux autres pays de l'UEMOA via un bloc de
configuration centralisé.

**Rapport de synthèse :** [`rapport_synthese.pdf`](rapport_synthese.pdf)  
**Dépôt GitHub :** [papamagattediop/Traitements\_de\_donnees-ERI-ESI-](https://github.com/papamagattediop/Traitements_de_donnees-ERI-ESI-)  
**Année académique :** 2025-2026

---

## Structure du dépôt

```
.
├── scripts/
│   ├── stata/                          Pipeline principal
│   │   ├── config.do                   Configuration pays (chemins, clés de fusion)
│   │   ├── 01_fusion.do                Fusion roster + module emploi
│   │   ├── 03_demographie_geo.do       Démographie et géographie individus
│   │   ├── 03_emploi_principal.do      Emploi principal
│   │   ├── 04_emploi_secondaire.do     Emploi secondaire
│   │   ├── 05_menages.do               Table ménages
│   │   └── 06_consolidation.do         Assemblage final
│   └── python/                         Modules Python (versions alternatives)
│       ├── 03_demographie_geo.py
│       └── 03_emploi_principal.py
├── docs/
│   ├── dictionnaire_variables.csv      Correspondance variables sources/produites
│   ├── rapport_synthese.tex            Source LaTeX du rapport
│   └── [questionnaires et notes]
├── rapport_synthese.pdf                Rapport de synthèse (Groupe 1)
├── repartition.html                    Tableau de bord de répartition des tâches
├── input/<PAYS>/                       Données brutes (.dta) -- non versionnées
├── output/<PAYS>/                      Tables produites -- non versionnées
├── .gitignore
└── README.md
```

> Les dossiers `input/` et `output/` ne sont pas versionnés. Seuls le code
> et la documentation sont suivis par git.

---

## Données d'entrée

Deux fichiers `.dta` constituent les entrées du pipeline :

| Fichier | Contenu | Observations | Variables |
|---|---|---|---|
| `individus_TP.dta` | Roster des membres du ménage | 120 693 | 53 |
| `emploi_Tp.dta` | Module emploi individuel | 120 689 | 492 |

Les fichiers bruts sont disponibles via ce lien (non versionnés) :  
[Google Drive -- Données ERI-ESI SEN](https://drive.google.com/drive/folders/1f3wIK8B8W3k-j-19QOH8jEW0MeIwFrRZ?usp=sharing)

Avant tout lancement, placer les fichiers bruts dans `input/SEN/` et créer le
dossier `output/SEN/`.

---

## Pipeline

Le traitement s'exécute en six scripts Stata, depuis la racine du dépôt :

| Ordre | Script | Entrée | Sortie |
|---|---|---|---|
| 1 | `01_fusion.do` | Fichiers bruts | `base_individus_emploi_fusionnee.dta` |
| 2 | `03_demographie_geo.do` | Base fusionnée | `individus_demo_geo.dta` |
| 3 | `03_emploi_principal.do` | Base fusionnée | `emploi_principal.dta` |
| 4 | `04_emploi_secondaire.do` | Base fusionnée | `emploi_secondaire.dta` |
| 5 | `05_menages.do` | `individus_demo_geo.dta` | `menages.dta` |
| 6 | `06_consolidation.do` | Sorties modules 2 à 5 | `individus_consolide.dta`, `menages_consolide.dta` |

Chaque script produit également un fichier de contrôles de cohérence
(`qc_*.csv`) et un fichier d'estimations pondérées (`estimations_*.csv`)
dans `output/<PAYS>/`.

---

## Exécution

Prérequis : Stata 14 ou plus. Lancer depuis la racine du dépôt.

```stata
do scripts/stata/01_fusion.do
do scripts/stata/03_demographie_geo.do
do scripts/stata/03_emploi_principal.do
do scripts/stata/04_emploi_secondaire.do
do scripts/stata/05_menages.do
do scripts/stata/06_consolidation.do
```

---

## Changement de pays

Modifier uniquement le bloc de configuration en tête de chaque script :
code pays (`PAYS`), noms de fichiers et noms de variables si la nomenclature
du questionnaire diffère. La logique de traitement ne change pas.

---

## Documentation

| Fichier | Contenu |
|---|---|
| `docs/dictionnaire_variables.csv` | Correspondance variables sources et variables produites |
| `docs/rapport_synthese.tex` | Source LaTeX du rapport de synthèse |
| `rapport_synthese.pdf` | Rapport de synthèse compilé |
