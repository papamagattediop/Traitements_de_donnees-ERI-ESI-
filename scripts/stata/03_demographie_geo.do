*==============================================================================*
*  ERI-ESI — Module démographie et géographie des individus
*  do scripts/stata/03_demographie_geo.do
*==============================================================================*

clear all
set more off

global PAYS         "SEN"
global VAGUE        "2017"
global DOSSIER_OUT  "output/SEN"
global FICHIER_BASE "base_individus_emploi_fusionnee.dta"

use "$DOSSIER_OUT/$FICHIER_BASE", clear
display as text "Module démographie/géographie - $PAYS $VAGUE — " _N " obs."

capture log close _all
log using "$DOSSIER_OUT/journal_demo_geo.log", replace text

*--- Vérification des variables requises
foreach var in hh1 hh2 m1 hhweight hhsize M3 M4 M2 M25 M13 M15 M16a M20a M19a Region MILIEU {
    capture confirm variable `var'
    if _rc {
        display as error "Variable manquante : `var'"
        log close
        error 111
    }
}

*--- Renommage vers noms internes stables
rename (hh1 hh2 m1 hhweight hhsize M3 m3E M4 M2 M25 M13 M15 M16a M20a M19a Region MILIEU) ///
       (id_grappe id_menage id_ordre poids taille_menage sexe sexe_emp age lien_cm ///
        matrimoniale ecole_deja ecole_actuelle niv_actuel niv_atteint niv_secours region milieu)

gen str20 id_men = string(id_grappe) + "_" + string(id_menage)

*--- Sexe
gen byte flag_sexe_incoherent = (!missing(sexe) & !missing(sexe_emp) & sexe != sexe_emp)

*--- Âge
replace age = . if age == 99
gen byte flag_age_aberrant = (!missing(age) & (age < 0 | age > 110))
replace age = . if flag_age_aberrant == 1

gen byte groupe_age = .
replace groupe_age = 1 if age >= 0  & age <  5
replace groupe_age = 2 if age >= 5  & age < 10
replace groupe_age = 3 if age >= 10 & age < 15
replace groupe_age = 4 if age >= 15 & age < 25
replace groupe_age = 5 if age >= 25 & age < 35
replace groupe_age = 6 if age >= 35 & age < 50
replace groupe_age = 7 if age >= 50 & age < 65
replace groupe_age = 8 if age >= 65 & age <  .

*--- Lien de parenté avec le CM
gen byte lien_cm_grp = .
replace lien_cm_grp = 1 if lien_cm == 1
replace lien_cm_grp = 2 if lien_cm == 2
replace lien_cm_grp = 3 if lien_cm == 3
replace lien_cm_grp = 4 if inlist(lien_cm, 4, 5, 6, 7)
replace lien_cm_grp = 5 if inlist(lien_cm, 8, 9)

*--- Situation matrimoniale (posée à partir de 12 ans)
gen byte flag_matrimoniale_manquant = (missing(matrimoniale) & age >= 12 & !missing(age))
replace matrimoniale = 0 if age < 12 & !missing(age)
replace matrimoniale = 9 if flag_matrimoniale_manquant == 1

*--- Niveau d'études consolidé
gen niveau_brut = .
replace niveau_brut = niv_actuel  if ecole_actuelle == 1
replace niveau_brut = niv_atteint if ecole_actuelle == 2
replace niveau_brut = niv_secours if ecole_actuelle == 2 & missing(niveau_brut)

gen byte niveau_etudes = .
replace niveau_etudes = 2 if niveau_brut == 0
replace niveau_etudes = 3 if niveau_brut == 1
replace niveau_etudes = 4 if inlist(niveau_brut, 2, 4)
replace niveau_etudes = 5 if inlist(niveau_brut, 3, 5)
replace niveau_etudes = 6 if niveau_brut == 6
replace niveau_etudes = 1 if ecole_deja == 2
replace niveau_etudes = 0 if missing(ecole_deja) & age < 6 & !missing(age)

*--- Branche d'études
gen byte branche_etudes = .
replace branche_etudes = 1 if inlist(niveau_brut, 2, 3)
replace branche_etudes = 2 if inlist(niveau_brut, 4, 5)
replace branche_etudes = 3 if niveau_brut == 6
replace branche_etudes = 0 if inlist(niveau_brut, 0, 1)
replace branche_etudes = 0 if inlist(niveau_etudes, 0, 1)

*--- Géographie (département absent du fichier SEN)
gen departement = .

*--- Libellés
label define lbl_groupe_age 1 "0-4 ans" 2 "5-9 ans" 3 "10-14 ans" 4 "15-24 ans" ///
    5 "25-34 ans" 6 "35-49 ans" 7 "50-64 ans" 8 "65 ans et plus"
label values groupe_age lbl_groupe_age

label define lbl_lien_grp 1 "Chef de ménage" 2 "Conjoint(e)" 3 "Enfant" ///
    4 "Autre parent" 5 "Sans lien / domestique"
label values lien_cm_grp lbl_lien_grp

label define lbl_niveau 0 "Non applicable" 1 "Aucun" 2 "Préscolaire" 3 "Primaire" ///
    4 "Secondaire 1er cycle" 5 "Secondaire 2nd cycle" 6 "Supérieur"
label values niveau_etudes lbl_niveau

label define lbl_branche 0 "Non applicable" 1 "Général" 2 "Technique" 3 "Supérieur"
label values branche_etudes lbl_branche

label define lbl_oui_non 0 "Non" 1 "Oui"
label values flag_sexe_incoherent flag_age_aberrant flag_matrimoniale_manquant lbl_oui_non

local matlbl : value label matrimoniale
if "`matlbl'" == "" {
    label define lbl_mat 0 "Non applicable (<12 ans)" 9 "Manquant"
    label values matrimoniale lbl_mat
}
else {
    label define `matlbl' 0 "Non applicable (<12 ans)" 9 "Manquant", modify
}

label variable id_grappe     "Grappe"
label variable id_menage     "Numéro de ménage"
label variable id_ordre      "Numéro d'ordre"
label variable id_men        "Identifiant ménage"
label variable poids         "Poids de sondage"
label variable taille_menage "Taille du ménage"
label variable sexe          "Sexe"
label variable age           "Âge (années)"
label variable groupe_age    "Groupe d'âge"
label variable lien_cm       "Lien de parenté avec le CM (détaillé)"
label variable lien_cm_grp   "Lien de parenté avec le CM (regroupé)"
label variable matrimoniale  "Situation matrimoniale"
label variable niveau_etudes "Niveau d'études consolidé"
label variable branche_etudes "Branche d'études"
label variable region        "Région"
label variable departement   "Département"
label variable milieu        "Milieu de résidence"
label variable milieu_etendu "Strate de résidence"
label variable flag_sexe_incoherent       "Désaccord sexe roster vs emploi"
label variable flag_age_aberrant          "Âge aberrant neutralisé"
label variable flag_matrimoniale_manquant "Situation matrimoniale manquante (12 ans et plus)"

*--- Contrôles de cohérence
tempvar nbcm prem
bysort id_men: egen `nbcm' = total(lien_cm == 1)
bysort id_men: gen  `prem' = (_n == 1)
quietly count if `prem' == 1 & `nbcm' != 1
local qc1 = r(N)
drop `nbcm' `prem'

quietly count if lien_cm == 1 & age < 12 & !missing(age)
local qc2 = r(N)
quietly count if inlist(matrimoniale, 2, 3) & age < 12 & !missing(age)
local qc3 = r(N)
quietly count if niveau_etudes == 6 & age < 18 & !missing(age)
local qc4 = r(N)
quietly count if missing(sexe)
local qc5 = r(N)
quietly count if missing(age)
local qc6 = r(N)
quietly count if flag_sexe_incoherent == 1
local qc7 = r(N)

file open qc using "$DOSSIER_OUT/qc_demo_geo.csv", write replace
file write qc "controle,nombre,detail" _n
file write qc "menages sans CM unique,"             (`qc1') ",doit valoir 0" _n
file write qc "CM de moins de 12 ans,"              (`qc2') ",a verifier" _n
file write qc "personnes mariees de moins de 12 ans," (`qc3') ",doit valoir 0" _n
file write qc "superieur declare avant 18 ans,"     (`qc4') ",a verifier" _n
file write qc "manquants sexe,"                     (`qc5') ",variable attendue complete" _n
file write qc "manquants age,"                      (`qc6') ",variable attendue complete" _n
file write qc "desaccords sexe roster vs emploi,"   (`qc7') ",roster conserve" _n
file close qc

*--- Estimations pondérées
tempvar fem u15 o65 urb mar noedu
gen `fem'   = (sexe == 2)
gen `u15'   = (age <  15 & !missing(age))
gen `o65'   = (age >= 65 & !missing(age))
gen `urb'   = (milieu == 1)
gen `mar'   = inlist(matrimoniale, 2, 3)
gen `noedu' = (niveau_etudes == 1)

foreach v in fem u15 o65 urb mar noedu {
    quietly summarize ``v'' [aw=poids], meanonly
    local e_`v' = r(mean)*100
}
quietly summarize age [aw=poids], meanonly
local e_age = r(mean)

file open est using "$DOSSIER_OUT/estimations_demo_geo.csv", write replace
file write est "indicateur,valeur" _n
file write est "Part de femmes (%),"                    %5.2f (`e_fem')  _n
file write est "Part de moins de 15 ans (%),"           %5.2f (`e_u15')  _n
file write est "Part de 65 ans et plus (%),"            %5.2f (`e_o65')  _n
file write est "Part en milieu urbain (%),"             %5.2f (`e_urb')  _n
file write est "Part de mariés 12 ans et plus (%),"     %5.2f (`e_mar')  _n
file write est "Part sans aucun niveau scolaire (%),"   %5.2f (`e_noedu') _n
file write est "Âge moyen (ans),"                       %5.1f (`e_age')  _n
file close est

*--- Sauvegarde
keep  id_grappe id_menage id_ordre id_men poids taille_menage ///
      sexe age groupe_age lien_cm lien_cm_grp matrimoniale ///
      niveau_etudes branche_etudes region departement milieu milieu_etendu ///
      flag_sexe_incoherent flag_age_aberrant flag_matrimoniale_manquant

order id_grappe id_menage id_ordre id_men poids taille_menage ///
      sexe age groupe_age lien_cm lien_cm_grp matrimoniale ///
      niveau_etudes branche_etudes region departement milieu milieu_etendu ///
      flag_sexe_incoherent flag_age_aberrant flag_matrimoniale_manquant

compress
save "$DOSSIER_OUT/individus_demo_geo.dta", replace

display as text "individus_demo_geo.dta : " _N " lignes — " "$DOSSIER_OUT"
capture log close
