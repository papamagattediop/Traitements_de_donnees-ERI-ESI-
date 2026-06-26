# Note methodologique : bloc demographie et geographie (Personne 2)

Ce document accompagne le script `scripts/python/03_demographie_geo.py`. Il
explique les choix de variables et de traitement pour la partie demographie et
geographie des individus.

## Perimetre

Le module produit, au niveau individu, les variables demandees dans le cahier
des charges du Groupe 1 :

- Demographie : sexe, age, niveau d'etudes, branche d'etudes, situation
  matrimoniale, lien de parente avec le chef de menage.
- Geographie : region, departement (selon disponibilite), milieu de residence.

Il ne traite pas l'emploi (Personne 3 et 4) ni l'assemblage de la table menages
ni le fichier QAQC global (Personne 1). Sa sortie, `individus_demo_geo.dta`,
alimente la demographie du chef de menage (Personne 4) et l'assemblage final.

## Choix de variables a noter

Deux corrections par rapport a une lecture rapide des prefixes :

1. La situation matrimoniale est portee par `M25`, pas par `M5`. Dans le
   fichier, `M5` est le lieu de naissance.
2. Le sexe et l'age complets viennent du roster (`M3`, `M4`, sans manquant).
   Les variables `m3E` et `m4` proviennent du module emploi pose aux 15 ans et
   plus, d'ou environ 32 % de manquants. Elles servent uniquement de controle
   croise. Le roster reste la reference.

## Traitement des manquants et des aberrants

- Sexe : reference = roster. Les desaccords avec le module emploi (294 cas) sont
  signales par `flag_sexe_incoherent` sans ecraser la reference.
- Age : codes type NSP mis a manquant, valeurs hors bornes 0 a 110 neutralisees
  et signalees par `flag_age_aberrant`. Sur le fichier Senegal, l'age va de 0 a
  98 sans aberration.
- Situation matrimoniale : `M25` n'est posee qu'a partir de 12 ans. Les
  manquants en dessous sont structurels (code 0, non applicable) et non des
  manquants reels. Au dessus de 12 ans, le manquant residuel (1 cas) est code 9
  et signale.
- Niveau d'etudes : reconstitue a partir de plusieurs variables. Jamais
  scolarise donne le niveau aucun ; scolarise actuellement donne le niveau
  actuel ; sorti de l'ecole donne le niveau atteint ; enfant en dessous de l'age
  scolaire donne non applicable. L'echelle est simplifiee pour rester comparable
  entre pays.

## Departement

Le fichier Senegal fourni ne contient pas le departement. Les variables
geographiques presentes sont la region, le milieu et la strate de residence. La
colonne `departement` est donc creee vide, pour garder un schema de sortie
stable d'un pays a l'autre, et l'absence est documentee dans le journal et dans
le fichier de controle. Pour un pays disposant du departement, il suffit de
renseigner `vars["departement"]` dans la configuration.

## Portabilite

Pour appliquer le module a un autre pays ERI-ESI, seul le dictionnaire `CONFIG`
en tete de script est a adapter : code pays, chemins, correspondance des noms de
variables, presence du departement. Les libelles des modalites sont lus dans les
metadonnees du fichier, donc ils suivent le pays automatiquement.
