*==============================================================================*
*  ERI-ESI — Table ménages consolidée
*  do scripts/stata/05_menages.do
*
*  Source : individus_demo_geo.dta (module 03)
*  Le CM fournit les variables démographiques du ménage.
*  Note : variables dépenses/actifs/habitat absentes du volet emploi SEN.
*==============================================================================*

clear all
set more off

global DOSSIER_OUT "output/SEN"

use "$DOSSIER_OUT/individus_demo_geo.dta", clear

capture log close _all
log using "$DOSSIER_OUT/journal_menages.log", replace text

*--- Verification : un seul CM par menage
bysort id_men: egen nb_cm = total(lien_cm == 1)
quietly count if nb_cm != 1
local qc_cm = r(N)
drop nb_cm

*--- Structure du menage (calculee avant de reduire au CM)
bysort id_men: gen nb_membres  = _N
gen byte est_homme  = (sexe == 1)
gen byte est_femme  = (sexe == 2)
gen byte est_u15    = (age <  15 & !missing(age))
gen byte est_15plus = (age >= 15 & !missing(age))
bysort id_men: egen nb_hommes  = total(est_homme)
bysort id_men: egen nb_femmes  = total(est_femme)
bysort id_men: egen nb_u15     = total(est_u15)
bysort id_men: egen nb_15plus  = total(est_15plus)
drop est_homme est_femme est_u15 est_15plus

*--- Reduction a une ligne par menage (CM)
keep if lien_cm == 1

*--- Renommage des variables CM
rename sexe           sexe_cm
rename age            age_cm
rename groupe_age     groupe_age_cm
rename niveau_etudes  niveau_etudes_cm
rename branche_etudes branche_etudes_cm

capture confirm variable matrimoniale
if !_rc rename matrimoniale situation_matrimoniale_cm
else    gen byte situation_matrimoniale_cm = .

*--- Libelles
label variable id_grappe              "Grappe"
label variable id_menage              "Numero de menage"
label variable id_men                 "Identifiant menage"
label variable poids                  "Poids menage"
label variable taille_menage          "Taille du menage"
label variable sexe_cm                "Sexe du CM"
label variable age_cm                 "Age du CM"
label variable groupe_age_cm          "Groupe d'age du CM"
label variable niveau_etudes_cm       "Niveau d'etudes du CM"
label variable branche_etudes_cm      "Branche d'etudes du CM"
label variable situation_matrimoniale_cm "Situation matrimoniale du CM"
label variable region                 "Region du menage"
label variable milieu                 "Milieu de residence"
label variable milieu_etendu          "Strate de residence"
label variable departement            "Departement"
label variable nb_membres             "Nombre de membres"
label variable nb_hommes              "Nombre d'hommes"
label variable nb_femmes              "Nombre de femmes"
label variable nb_u15                 "Membres de moins de 15 ans"
label variable nb_15plus              "Membres de 15 ans et plus"

*--- Controles de coherence
quietly count if missing(sexe_cm)
local qc1 = r(N)
quietly count if missing(age_cm)
local qc2 = r(N)
quietly count if age_cm < 15 & !missing(age_cm)
local qc3 = r(N)
quietly count if taille_menage != nb_membres & !missing(nb_membres)
local qc4 = r(N)

file open qc using "$DOSSIER_OUT/qc_menages.csv", write replace
file write qc "controle,nombre,detail" _n
file write qc "menages sans CM unique," (`qc_cm') ",doit valoir 0" _n
file write qc "manquants sexe_cm,"     (`qc1')   ",variable attendue complete" _n
file write qc "manquants age_cm,"      (`qc2')   ",variable attendue complete" _n
file write qc "CM de moins de 15 ans," (`qc3')   ",a verifier" _n
file write qc "taille_menage != nb_membres calcule," (`qc4') ",incoherence a verifier" _n
file close qc

*--- Estimations ponderees
quietly summarize taille_menage [aw=poids], meanonly
local e_tail = r(mean)
quietly summarize (sexe_cm==2) [aw=poids], meanonly
local e_fem  = r(mean)*100
quietly summarize age_cm [aw=poids], meanonly
local e_age  = r(mean)

file open est using "$DOSSIER_OUT/estimations_menages.csv", write replace
file write est "indicateur,valeur" _n
file write est "Taille moyenne du menage,"                  %5.2f (`e_tail') _n
file write est "Part menages diriges par une femme (%),"    %5.2f (`e_fem')  _n
file write est "Age moyen du CM (ans),"                     %5.1f (`e_age')  _n
file close est

*--- Sauvegarde
keep id_grappe id_menage id_men poids taille_menage ///
     sexe_cm age_cm groupe_age_cm situation_matrimoniale_cm ///
     niveau_etudes_cm branche_etudes_cm ///
     region departement milieu milieu_etendu ///
     nb_membres nb_hommes nb_femmes nb_u15 nb_15plus

order id_grappe id_menage id_men poids taille_menage ///
     sexe_cm age_cm groupe_age_cm situation_matrimoniale_cm ///
     niveau_etudes_cm branche_etudes_cm ///
     region departement milieu milieu_etendu ///
     nb_membres nb_hommes nb_femmes nb_u15 nb_15plus

compress
save "$DOSSIER_OUT/menages.dta", replace

display as text "menages.dta : " _N " menages — " "$DOSSIER_OUT"
capture log close
