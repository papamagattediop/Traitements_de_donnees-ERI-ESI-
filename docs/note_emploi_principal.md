# Note methodologique : bloc emploi principal (Personne 3)

Ce document accompagne `scripts/python/03_emploi_principal.py` (traitement)
et `scripts/python/03_emploi_principal_graphiques.py` (analyse exploratoire)
. Il explique les choix de variables et de traitement pour le bloc
emploi principal des individus.

## Perimetre

Le module produit, au niveau individu, les variables demandees dans notre
cahier des charges :

- Situation d'activite et raison d'inactivite
- Statut dans l'emploi principal et type d'emploi (salarie/independant)
- Secteur/branche d'activite (ISIC Rev.4)
- Revenu de l'emploi principal
- Heures de travail de l'emploi principal (et sous-emploi lie a la duree)
- Formalite de l'emploi et de l'unite (deux indicateurs distincts)

Il ne traite pas l'emploi secondaire ni le chomage , ni la
demographie/geographie, ni l'assemblage final ou le fichier
QAQC global . Sa sortie, `emploi_principal.dta`, alimente
l'assemblage final.

## Corrections par rapport au dictionnaire initial

Le fichier `docs/dictionnaire_variables.csv`, etabli tot dans le projet par
lecture des prefixes, s'est revele incorrect sur 5 des 8 variables
attribuees a ce bloc. Chaque correction a ete verifiee a la fois sur les
metadonnees du fichier (`.dta`) et sur le questionnaire papier
(`docs/QST_QUESTIONNAIRE VOLET EMPLOI_ERI-ESI 28122016.docx`) :

| Concept | Dictionnaire initial | Variable reelle |
|---|---|---|
| Heures de travail | AP6A | **AP10C** (AP6A est le regime fiscal, bloc formalite) |
| Formalite emploi/unite | AP7 | **AP6A/AP6D/AP6E** (unite) et **AP16_21A/22A/23A** (emploi) - AP7 est le lieu de travail |
| Revenu emploi principal | AP8A1 | **AP13A/B/C** (AP8A1 est l'anciennete dans l'emploi, en mois) |
| Secteur ISIC Rev.4 | AP4 | **AP2_Niv1** (AP4 est le secteur institutionnel : public/prive/menage) |
| Raison d'inactivite | SE9 | **SE11** (SE9 est la disponibilite a travailler) |

`AP3` (statut emploi) et `sitac` (situation d'activite) etaient corrects des
le depart. Le dictionnaire corrige propre a ce module se trouve dans
`docs/dictionnaire_variables_emploi_principal.csv`, sur le modele de celui
de la Personne 2 - le fichier partage n'a pas ete modifie directement.

## Definitions officielles utilisees (rapport  ANSD)

Plutot que d'inventer des criteres de formalite, on reprend les definitions
operationnelles publiees par l'ANSD/AFRISTAT :

- **Formalite de l'unite** (secteur informel) : parmi les unites marchandes
  (`AP6E`), est informelle une unite qui ne remplit pas au moins un des deux
  criteres suivants - enregistrement fiscal (`AP6A`) et tenue d'une
  comptabilite formelle (`AP6D`). Les unites non marchandes sont hors champ
  de cette classification (non applicable, pas "formelles" par defaut).
- **Formalite de l'emploi** : un salarie est en emploi informel s'il lui
  manque au moins un des trois avantages suivants - cotisations de
  protection sociale payees par l'employeur, conges annuels payes, conges
  maladie remuneres (`AP16_21A`, `AP16_22A`, `AP16_23A`). Ce bloc n'est
  administre qu'aux salaries (structurellement absent pour les
  independants).
- **Sous-emploi lie a la duree du travail** : personne en emploi qui
  travaille involontairement moins que la duree legale (40h/semaine),
  disponible pour travailler plus. Le troisieme critere officiel
  ("recherche d'un travail supplementaire") n'a pas ete localise dans le
  perimetre inspecte ; la definition ANSD utilise "et/ou" entre ce critere
  et la disponibilite, donc l'omission reste une application valide mais
  simplifiee (taux obtenu : 3,1%, sous le taux implicite du rapport ANSD
  d'environ 9-10%, ecart documente plutot que force a correspondre).

Ces définitions ont ete verifiées à la relecture des estimations pondérées
face aux chiffres deja publies (repartition sectorielle a moins de 0,2 point
d'ecart, chomage BIT et emplois vulnerables tres proches - cf.
`estimations_emploi_principal.csv`).

## Traitement des manquants

Trois categories de manquants:

1. **Manquant structurel** (hors sous-population) : par exemple tout le
   bloc AP est vide pour les non-occupes. Reste `NaN`, jamais impute.
2. **Manquant reel** (dans la sous-population eligible, valeur absente) :
   par exemple un revenu non renseigne alors que la personne est occupee.
   Signale par un flag dedie (`flag_revenu_non_renseigne`,
   `flag_ecart_heures`...), jamais impute non plus - une distinction
   discutee explicitement avec le reste du groupe : imputer aurait du sens
   pour des variables posees a tous les eligibles (comme le fait le module
   demographie/geographie pour le sexe/age, en signalant sans ecraser),
   mais serait faux ici ou l'essentiel du manquant est structurel.
3. **Valeur aberrante** : neutralisee (mise a `NaN`) et signalee par un
   flag (`flag_heures_aberrantes`, `flag_revenu_aberrant`), jamais laissee
   telle quelle ni corrigee silencieusement.

### Cas particulier : eligibilite au module emploi

Le questionnaire emploi est administre a partir de 10 ans, mais `sitac`
(situation d'activite synthetique) n'est calcule par l'ANSD qu'a partir de
15 ans. Consequence : environ 32% des lignes de la base fusionnee
(essentiellement des enfants de moins de 10 ans) n'ont aucune donnee sur
tout le bloc, y compris le poids `weightemploy`. Le flag
`eligible_module_emploi` rend cela explicite plutot que de laisser deviner
pourquoi une ligne est entierement vide.

### Cas particulier : travail des enfants (10-14 ans)

932 individus ages de 10 a 14 ans ont un statut d'emploi (`AP3`) renseigne
bien que `sitac` les exclue systematiquement des "actifs occupes" (puisque
non calcule avant 15 ans). Ce n'est pas une incoherence a corriger : c'est
un phenomene reel (travail des enfants), isole explicitement par
`flag_travail_enfant_10_14` plutot que d'etre laisse se fondre dans les
donnees ou lu a tort comme une erreur de traitement. Le controle de
coherence distingue ce cas de la vraie anomalie potentielle (statut
renseigne chez un adulte non-occupe), qui est verifiee nulle.

## Limites connues

- **Controle croise des heures** : le calcul debut/fin de journee (`AP18`)
  ne retire pas de pause dejeuner, ce qui gonfle artificiellement l'ecart
  avec les heures declarees (`AP10C`) pour environ 57% des occupes avec
  heures renseignees. La variable principale reste la valeur declaree ;
  le calcul croise n'est qu'un signal de qualite secondaire.
- **Revenu par tranche** : quand seule une tranche est declaree (`AP13C`),
  le point milieu est utilise (borne basse retenue pour la derniere
  tranche ouverte, `>=3000` milliers FCFA). Ceci cree des paliers
  artificiels visibles sur l'histogramme du revenu plutot qu'une
  distribution lisse - limite connue de toute imputation par tranche.
- **Taux de salarisation** : notre estimation (33,4%) est plus basse que
  le chiffre publie par l'ANSD (38,6%), qui porte specifiquement sur le
  secteur non agricole ; notre calcul inclut le secteur primaire, ou
  l'auto-emploi domine largement, ce qui tire le taux vers le bas. Pas une
  erreur, une difference de base de calcul.

## Portabilite

Pour appliquer le module a un autre pays ERI-ESI, le dictionnaire `CONFIG`
en tete de script est a adapter : code pays, chemins, correspondance des
noms de variables, bornes de plausibilite, points milieu des tranches de
revenu (propres au bareme national). Le regroupement en 21 sections ISIC
(`secteur_isic_principal`) suit deja une norme internationale et ne
necessite en principe aucun ajustement ; seule la correspondance
variable-brute doit etre revalidee, l'experience de ce module montrant
qu'une lecture rapide des prefixes ne suffit pas - une verification directe
sur les metadonnees et le questionnaire est indispensable avant tout
recodage.
