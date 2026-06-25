* Configuration du pipeline ERI-ESI
* Pour adapter a un autre pays : changer PAYS et, si besoin, les noms de
* variables cles ci-dessous, sans toucher au reste des .do files.

global PAYS "SEN"

global RACINE ".."
global INPUT  "${RACINE}/../input/${PAYS}"
global OUTPUT "${RACINE}/../output/${PAYS}"

global FICHIER_INDIVIDUS "individus_TP.dta"
global FICHIER_EMPLOI    "emploi_Tp.dta"

* Cles de fusion (cote individus / cote emploi)
global CLES_INDIVIDUS "hh1 hh2 M1"
global CLES_EMPLOI    "hh1 hh2 m1"

capture mkdir "${OUTPUT}"
