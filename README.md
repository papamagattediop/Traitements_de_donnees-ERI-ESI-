# Traitements de données ERI-ESI (Groupe 1)

Pipeline reproductible et scalable pour extraire, traiter et stocker les
informations individus et ménages de l'enquête ERI-ESI. L'enquête étant
harmonisée à l'échelle sous-régionale, le code est pensé pour passer d'un pays à
l'autre en modifiant surtout la configuration, sans réécriture lourde.

En sortie, le pipeline produit deux tables consolidées, une pour les individus
et une pour les ménages, accompagnées d'un fichier de contrôle qualité (QAQC).

## Structure du dépôt

```
├── input/<PAYS>/        Données brutes (.dta), non versionnées
├── output/<PAYS>/       Tables produites par le pipeline (.dta), non versionnées
├── scripts/
│   ├── stata/           Pipeline principal (extraction, fusion, modules thématiques)
│   └── python/          QAQC et version Python des modules
├── docs/                Dictionnaire de variables, notes méthodologiques
└── README.md
```

Les dossiers `input/` et `output/` ne sont pas versionnés : ils ne contiennent
que des données, gardées hors du dépôt par le fichier `.gitignore`. Seuls le
code et la documentation sont suivis par git.

## Données d'entrée

Le pipeline part de la base individuelle fusionnée (roster des individus fusionné
avec le module emploi). Cette base n'est pas versionnée. Avant tout lancement,
elle doit se trouver à cet emplacement précis, sinon les scripts ne la
trouveront pas :

```
output/SEN/base_individus_emploi_fusionnee.dta
```

Pour un autre pays, `SEN` est remplacé par le code du pays, et la base va dans
`output/<PAYS>/`.

Téléchargement de la base fusionnée (non versionnée) : https://drive.google.com/drive/folders/1f3wIK8B8W3k-j-19QOH8jEW0MeIwFrRZ?usp=sharing

Le partage Drive doit être réglé sur « toute personne disposant du lien peut
consulter », pour que les correcteurs et les autres membres y accèdent. Si le
fichier est partagé au format compressé (`.zip`), il faut le décompresser avant
de placer le `.dta` dans `output/SEN/`.

## Organisation du pipeline

Le traitement suit cinq étapes, réparties entre les membres du groupe :

1. Extraction et fusion. Lecture des fichiers bruts depuis `input/<PAYS>/` et
   construction de la base individuelle fusionnée.
2. Démographie et géographie des individus. Sexe, âge, niveau et branche
   d'études, situation matrimoniale, lien de parenté avec le CM, région, milieu.
3. Emploi principal. Statut, secteur (ISIC Rev.4), revenu, heures, formalité,
   type d'emploi, raison d'inactivité.
4. Emploi secondaire, chômage et table ménages. Emplois secondaires, chômeurs,
   puis assemblage de la table ménages (démographie du CM, géographie, dépenses,
   actifs, habitat).
5. QAQC et assemblage final. Estimations primaires de contrôle et consolidation
   des deux tables de sortie.

Le pipeline principal est écrit en Stata. Le QAQC est en Python. Les modules
démographie/géographie et emploi principal sont fournis dans les deux langages,
au choix.

## Module démographie et géographie des individus

Ce module construit le bloc démographique et géographique au niveau individu. Il
prend la base fusionnée en entrée et produit une table propre qui alimente
ensuite la démographie du chef de ménage et l'assemblage final.

Deux versions équivalentes sont disponibles, qui produisent des sorties
identiques (mêmes recodages, mêmes traitements, mêmes tables) :

- `scripts/python/03_demographie_geo.py`
- `scripts/stata/03_demographie_geo.do`

Variables produites : sexe, âge et groupe d'âge, lien de parenté avec le CM
(détaillé et regroupé), situation matrimoniale, niveau d'études consolidé,
branche d'études, région, département (selon disponibilité), milieu et strate de
résidence, ainsi que des drapeaux de qualité.

Sorties écrites dans `output/<PAYS>/` :

- `individus_demo_geo.dta` : table individus démo/géo, avec libellés.
- `qc_demo_geo.csv` : contrôles de cohérence du bloc.
- `estimations_demo_geo.csv` : estimations primaires pondérées.

### Traitement des manquants et des aberrants

- Sexe. La source de référence est le roster, complet. Le sexe du module emploi,
  posé aux quinze ans et plus (environ 32 pour cent de manquants), sert seulement
  de témoin : les désaccords sont signalés par un drapeau sans écraser la
  référence.
- Âge. Les codes « ne sait pas » et les âges hors des bornes plausibles sont mis
  à manquant et signalés par un drapeau.
- Situation matrimoniale. La question n'étant posée qu'à partir de douze ans, les
  manquants en dessous sont codés « non applicable » (manquant structurel, pas
  réel). Un manquant résiduel au delà est marqué explicitement.
- Niveau d'études. Reconstruit à partir de plusieurs questions selon la situation
  scolaire, puis simplifié en catégories comparables entre pays.

### Points à connaître sur les variables

- Le fichier Sénégal ne contient pas le département. La colonne `departement`
  est créée vide, pour garder un schéma de sortie identique d'un pays à l'autre,
  et l'absence est documentée dans le journal et le fichier de contrôle. Un pays
  disposant du département n'a qu'à le renseigner dans la configuration.

## Module emploi principal

Ce module construit le bloc emploi principal au niveau individu : situation
d'activité et raison d'inactivité, statut dans l'emploi et type d'emploi
(salarié/indépendant), secteur/branche d'activité (ISIC Rev.4), heures de
travail et sous-emploi lié à la durée, revenu mensuel consolidé, et deux
indicateurs de formalité distincts (unité et emploi), selon les définitions
officielles du rapport final ANSD.

Deux versions équivalentes sont disponibles :

- `scripts/python/03_emploi_principal.py`
- `scripts/stata/03_emploi_principal.do`

Sorties écrites dans `output/<PAYS>/` :

- `emploi_principal.dta` : table emploi principal, avec libellés.
- `qc_emploi_principal.csv` : contrôles de cohérence du bloc.
- `estimations_emploi_principal.csv` : estimations pondérées, comparées aux
  chiffres déjà publiés par l'ANSD.
- `codebook_emploi_principal.csv` : une ligne par variable/modalité, effectif
  et part pondérée.
- `journal_emploi_principal.log` : trace horodatée de l'exécution.

Un script de tests automatiques (`scripts/python/tests_emploi_principal.py`)
vérifie une série d'invariants après traitement, et un script séparé
(`scripts/python/03_emploi_principal_graphiques.py`, optionnel) produit des
graphiques d'analyse exploratoire dans `output/<PAYS>/graphiques_emploi_principal/`.

### Points à connaître sur les variables

Cinq des huit variables initialement listées dans
`docs/dictionnaire_variables.csv` se sont révélées mal identifiées après
vérification directe sur les métadonnées du fichier et le questionnaire
officiel (détail complet dans `docs/note_emploi_principal.md`). Le dictionnaire
central a été corrigé en conséquence.

Deux cas particuliers sont traités explicitement plutôt que d'être laissés
implicites : l'éligibilité au module emploi (administré à partir de 10 ans,
alors que la situation d'activité synthétique n'est calculée par l'ANSD qu'à
partir de 15 ans) et le travail des enfants (10-14 ans avec un statut d'emploi
renseigné, phénomène réel et non une anomalie).

## Utilisation

Prérequis communs : la base fusionnée doit être placée dans `output/<PAYS>/`
comme indiqué plus haut. Les commandes se lancent depuis la racine du dépôt.

Version Python :

```bash
pip install -r requirements.txt
python scripts/python/03_demographie_geo.py
python scripts/python/03_emploi_principal.py
python scripts/python/tests_emploi_principal.py       # optionnel : tests automatiques
python scripts/python/03_emploi_principal_graphiques.py  # optionnel : graphiques
```

Version Stata (Stata 14 ou plus, fichier encodé en UTF-8) :

```stata
do scripts/stata/03_demographie_geo.do
do scripts/stata/03_emploi_principal.do
```

## Changement de pays

L'enquête est harmonisée, donc les valeurs des variables sont les mêmes d'un pays
à l'autre. Seuls les noms de variables et les chemins peuvent différer. Pour
adapter un module, il suffit de modifier son bloc de configuration en tête de
fichier : code pays, chemins, correspondance des noms de variables, présence du
département. Les libellés des modalités sont lus dans les métadonnées du fichier,
donc ils suivent le pays automatiquement.

## Documentation

- `docs/dictionnaire_variables_demo_geo.csv` : description de chaque variable de
  sortie du bloc démo/géo, sa source et son traitement.
- `docs/note_demographie_geo.md` : note méthodologique du bloc démo/géo.
- `docs/dictionnaire_variables_emploi_principal.csv` : description de chaque
  variable de sortie du bloc emploi principal, sa source et son traitement.
- `docs/note_emploi_principal.md` : note méthodologique du bloc emploi
  principal, avec le détail des corrections apportées au dictionnaire initial.
- `docs/standards_modules.md` : standard commun aux modules déjà livrés
  (journal, codebook, tests, dictionnaire propre, note méthodologique), à
  suivre pour les modules restants.
