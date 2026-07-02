*==============================================================================*
*  ERI-ESI — Module emploi secondaire
*  do scripts/stata/04_emploi_secondaire.do
*==============================================================================*

clear all
set more off

global PAYS        "SEN"
global DOSSIER_OUT "output/SEN"
global FICHIER_BASE "base_individus_emploi_fusionnee.dta"
global HEURES_MAX  98
global REVENU_MIN  1000
global REVENU_MAX  5000000

use "$DOSSIER_OUT/$FICHIER_BASE", clear

capture log close _all
log using "$DOSSIER_OUT/journal_emploi_secondaire.log", replace text

* Verification des variables requises
foreach var in hh1 hh2 m1 weightemploy AS1A AS1B1 AS4_AS1 AS5_AS1 ///
               AS9B_AS1 AS9C_AS1 AS10A_AS1 AS10B_AS1 AS10C_AS1 ///
               AS7B_AS1_A1 AS7B_AS1_B1 AS7B_AS1_C1 AS3S1_OLD {
    capture confirm variable `var'
    if _rc {
        display as error "Variable manquante : `var'"
        log close
        error 111
    }
}

rename (hh1 hh2 m1 weightemploy) (id_grappe id_menage id_ordre poids_emploi)
gen str20 id_men = string(id_grappe) + "_" + string(id_menage)

*--- Existence et nombre d'emplois secondaires
gen byte a_emploi_secondaire = (AS1A == 1) if !missing(AS1A)
gen byte nb_emplois_sec      = AS1B1
gen byte nb_emplois_sec_grp  = cond(AS1B1 == 1, 1, cond(AS1B1 >= 2 & !missing(AS1B1), 2, .))

*--- Statut et type d'emploi secondaire (meme codage AP3)
gen statut_emploi_sec = AS4_AS1
gen byte type_emploi_sec = .
replace  type_emploi_sec = 1 if inlist(AS4_AS1, 1,2,3,4,5,6,10)
replace  type_emploi_sec = 2 if inlist(AS4_AS1, 7,8,9)

*--- Secteur (AS3S1_OLD : potentiellement ancien codage ISIC — a verifier)
gen secteur_isic_sec_brut          = AS3S1_OLD
gen byte flag_secteur_ancien_codage = !missing(AS3S1_OLD)

*--- Heures hebdomadaires : AS9C en minutes/jour, AS9B en jours/semaine
gen double heures_semaine_sec = (AS9C_AS1 / 60) * AS9B_AS1
gen byte flag_heures_sec_abt  = (!missing(heures_semaine_sec) & heures_semaine_sec > $HEURES_MAX)
replace  heures_semaine_sec   = . if flag_heures_sec_abt == 1

*--- Revenu mensuel consolide (meme routage que module emploi principal)
gen double tranche = .
replace tranche =  17500 if AS10C_AS1 == 1
replace tranche =  67500 if AS10C_AS1 == 2
replace tranche = 125000 if AS10C_AS1 == 3
replace tranche = 175000 if AS10C_AS1 == 4
replace tranche = 225000 if AS10C_AS1 == 5
replace tranche = 275000 if AS10C_AS1 == 6
replace tranche = 325000 if AS10C_AS1 == 7
replace tranche = 375000 if AS10C_AS1 == 8
replace tranche = 425000 if AS10C_AS1 == 9
replace tranche = 475000 if AS10C_AS1 == 10
replace tranche = 525000 if AS10C_AS1 == 11
replace tranche = 575000 if AS10C_AS1 == 12
replace tranche = 625000 if AS10C_AS1 == 13
replace tranche = 675000 if AS10C_AS1 == 14
replace tranche = 725000 if AS10C_AS1 == 15
replace tranche = 775000 if AS10C_AS1 == 16
replace tranche = 825000 if AS10C_AS1 == 17
replace tranche = 875000 if AS10C_AS1 == 18
replace tranche = 950000 if AS10C_AS1 == 19
replace tranche =1125000 if AS10C_AS1 == 20
replace tranche =1375000 if AS10C_AS1 == 21
replace tranche =1750000 if AS10C_AS1 == 22
replace tranche =2250000 if AS10C_AS1 == 23
replace tranche =2750000 if AS10C_AS1 == 24
replace tranche =3000000 if AS10C_AS1 == 25

gen double revenu_sec_mensuel = .
replace revenu_sec_mensuel = AS10B_AS1         if AS10A_AS1 == 1
replace revenu_sec_mensuel = AS10B_AS1 / 12    if AS10A_AS1 == 2
replace revenu_sec_mensuel = tranche           if AS10A_AS1 == 3
replace revenu_sec_mensuel = tranche / 12      if AS10A_AS1 == 4
drop tranche

gen byte flag_revenu_sec_abt = (!missing(revenu_sec_mensuel) ///
    & (revenu_sec_mensuel < $REVENU_MIN | revenu_sec_mensuel > $REVENU_MAX))
replace revenu_sec_mensuel = . if flag_revenu_sec_abt == 1

*--- Formalite emploi secondaire (salaries uniquement)
gen byte formalite_emploi_sec = .
replace  formalite_emploi_sec = 1 if !missing(AS7B_AS1_A1) & !missing(AS7B_AS1_B1) ///
    & !missing(AS7B_AS1_C1) & AS7B_AS1_A1==1 & AS7B_AS1_B1==1 & AS7B_AS1_C1==1
replace  formalite_emploi_sec = 2 if !missing(AS7B_AS1_A1) & !missing(AS7B_AS1_B1) ///
    & !missing(AS7B_AS1_C1) & formalite_emploi_sec == .

*--- Libelles
label define lbl_oui_non 0 "Non" 1 "Oui"
label define lbl_nb_sec  1 "1 emploi sec." 2 "2 emplois sec. et plus"
label define lbl_type    1 "Salarie" 2 "Independant"
label define lbl_form    1 "Formel" 2 "Informel"
label values a_emploi_secondaire lbl_oui_non
label values nb_emplois_sec_grp  lbl_nb_sec
label values type_emploi_sec     lbl_type
label values formalite_emploi_sec lbl_form
label values flag_secteur_ancien_codage flag_heures_sec_abt flag_revenu_sec_abt lbl_oui_non

label variable a_emploi_secondaire      "Existence d'un emploi secondaire"
label variable nb_emplois_sec           "Nombre d'emplois secondaires"
label variable nb_emplois_sec_grp       "Nombre d'emplois secondaires (1 vs 2+)"
label variable statut_emploi_sec        "Statut dans l'emploi secondaire"
label variable type_emploi_sec          "Type d'emploi secondaire (salarie/independant)"
label variable secteur_isic_sec_brut    "Secteur emploi secondaire (codage AS3S1_OLD, a verifier)"
label variable flag_secteur_ancien_codage "Secteur secondaire potentiellement en ancien codage ISIC"
label variable heures_semaine_sec       "Heures par semaine emploi secondaire"
label variable flag_heures_sec_abt      "Heures emploi secondaire aberrantes (>98h)"
label variable revenu_sec_mensuel       "Revenu mensuel emploi secondaire (FCFA)"
label variable flag_revenu_sec_abt      "Revenu emploi secondaire aberrant"
label variable formalite_emploi_sec     "Formalite emploi secondaire (salaries)"

*--- Controles de coherence
quietly count if a_emploi_secondaire==1 & missing(statut_emploi_sec)
local qc1 = r(N)
quietly count if a_emploi_secondaire==0 & !missing(statut_emploi_sec)
local qc2 = r(N)
quietly count if flag_heures_sec_abt==1
local qc3 = r(N)
quietly count if flag_revenu_sec_abt==1
local qc4 = r(N)

file open qc using "$DOSSIER_OUT/qc_emploi_secondaire.csv", write replace
file write qc "controle,nombre,detail" _n
file write qc "emploi_sec=1 mais statut manquant," (`qc1') ",a verifier" _n
file write qc "emploi_sec=0 mais statut renseigne," (`qc2') ",incoherence filtre" _n
file write qc "heures aberrantes neutralisees," (`qc3') ",>98h/semaine" _n
file write qc "revenu aberrant neutralise," (`qc4') ",hors bornes plausibilite" _n
file close qc

*--- Estimations ponderees
quietly summarize a_emploi_secondaire [aw=poids_emploi] if !missing(a_emploi_secondaire), meanonly
local e_sec = r(mean)*100
quietly summarize revenu_sec_mensuel   [aw=poids_emploi] if a_emploi_secondaire==1, meanonly
local e_rev = r(mean)
quietly summarize heures_semaine_sec   [aw=poids_emploi] if a_emploi_secondaire==1, meanonly
local e_h   = r(mean)

file open est using "$DOSSIER_OUT/estimations_emploi_secondaire.csv", write replace
file write est "indicateur,valeur" _n
file write est "Taux avec emploi secondaire (%),"               %5.2f (`e_sec') _n
file write est "Revenu mensuel moyen emploi secondaire (FCFA)," %9.2f (`e_rev') _n
file write est "Heures moyennes par semaine emploi secondaire,"  %5.2f (`e_h')  _n
file close est

*--- Sauvegarde
keep id_grappe id_menage id_ordre id_men poids_emploi ///
     a_emploi_secondaire nb_emplois_sec nb_emplois_sec_grp ///
     statut_emploi_sec type_emploi_sec ///
     secteur_isic_sec_brut flag_secteur_ancien_codage ///
     heures_semaine_sec flag_heures_sec_abt ///
     revenu_sec_mensuel flag_revenu_sec_abt ///
     formalite_emploi_sec

order id_grappe id_menage id_ordre id_men poids_emploi ///
     a_emploi_secondaire nb_emplois_sec nb_emplois_sec_grp ///
     statut_emploi_sec type_emploi_sec ///
     secteur_isic_sec_brut flag_secteur_ancien_codage ///
     heures_semaine_sec flag_heures_sec_abt ///
     revenu_sec_mensuel flag_revenu_sec_abt ///
     formalite_emploi_sec

compress
save "$DOSSIER_OUT/emploi_secondaire.dta", replace

display as text "emploi_secondaire.dta : " _N " lignes — " "$DOSSIER_OUT"
capture log close
