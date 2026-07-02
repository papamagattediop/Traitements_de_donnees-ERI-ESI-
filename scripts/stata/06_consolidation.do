*==============================================================================*
*  ERI-ESI — Consolidation finale : tables individus et menages
*  do scripts/stata/06_consolidation.do
*==============================================================================*

clear all
set more off

global PAYS        "SEN"
global VAGUE       "2017"
global DOSSIER_OUT "output/SEN"

capture log close _all
log using "$DOSSIER_OUT/journal_consolidation.log", replace text

display as text "Consolidation finale - $PAYS $VAGUE"

*--- Verification des fichiers sources
foreach f in individus_demo_geo emploi_principal emploi_secondaire menages {
    capture confirm file "$DOSSIER_OUT/`f'.dta"
    if _rc {
        display as error "Fichier manquant : `f'.dta"
        log close
        error 601
    }
}

*==============================================================================*
*  TABLE INDIVIDUS
*==============================================================================*

use "$DOSSIER_OUT/individus_demo_geo.dta", clear

*--- Fusion avec emploi principal (tous les individus conserves)
merge 1:1 id_grappe id_menage id_ordre using "$DOSSIER_OUT/emploi_principal.dta", ///
    keepusing(poids_emploi eligible_module_emploi situation_activite situation_activite_grp ///
              raison_inactivite statut_emploi type_emploi flag_travail_enfant_10_14 ///
              secteur_isic_principal secteur_isic_principal_4cat ///
              heures_semaine_principal sous_emploi_duree flag_heures_aberrantes flag_ecart_heures ///
              revenu_principal_mensuel_fcfa revenu_source flag_revenu_non_renseigne flag_revenu_aberrant ///
              formalite_unite formalite_emploi) ///
    nogenerate

quietly count if eligible_module_emploi == 2
display as text "  Individus hors module emploi (<10 ans ou non apparies) : `r(N)'"

*--- Fusion avec emploi secondaire
merge 1:1 id_grappe id_menage id_ordre using "$DOSSIER_OUT/emploi_secondaire.dta", ///
    keepusing(a_emploi_secondaire nb_emplois_sec nb_emplois_sec_grp ///
              statut_emploi_sec type_emploi_sec ///
              secteur_isic_sec_brut flag_secteur_ancien_codage ///
              heures_semaine_sec flag_heures_sec_abt ///
              revenu_sec_mensuel flag_revenu_sec_abt ///
              formalite_emploi_sec) ///
    nogenerate

*--- Controles post-fusion
quietly count if missing(id_grappe)
local qc1 = r(N)
quietly count if eligible_module_emploi == 1 & missing(situation_activite)
local qc2 = r(N)
quietly count if situation_activite == 1 & a_emploi_secondaire == . & eligible_module_emploi == 1
local qc3 = r(N)

file open qc using "$DOSSIER_OUT/qc_consolidation_individus.csv", write replace
file write qc "controle,nombre,detail" _n
file write qc "individus sans identifiant grappe," (`qc1') ",doit valoir 0" _n
file write qc "eligibles module emploi sans situation_activite," (`qc2') ",doit valoir 0" _n
file write qc "occupes sans information emploi secondaire," (`qc3') ",a verifier" _n
file close qc

compress
save "$DOSSIER_OUT/individus_consolide.dta", replace
display as text "  individus_consolide.dta : " _N " lignes"

*==============================================================================*
*  TABLE MENAGES
*==============================================================================*

use "$DOSSIER_OUT/menages.dta", clear

*--- Indicateurs d'emploi agreges au niveau menage (depuis individus_consolide)
preserve
    use "$DOSSIER_OUT/individus_consolide.dta", clear

    gen byte est_occupe    = (situation_activite == 1)
    gen byte est_salarie   = (situation_activite == 1 & type_emploi == 1)
    gen byte est_informel  = (formalite_unite == 2 | formalite_emploi == 2)

    bysort id_men: egen nb_occupes   = total(est_occupe)
    bysort id_men: egen nb_salaries  = total(est_salarie)
    bysort id_men: egen nb_informels = total(est_informel)

    gen byte a_actif_occupe = (nb_occupes > 0)
    gen ratio_dependance    = cond(nb_occupes > 0, (nb_membres - nb_occupes) / nb_occupes, .)

    keep id_men nb_occupes nb_salaries nb_informels a_actif_occupe ratio_dependance
    duplicates drop id_men, force

    save "$DOSSIER_OUT/_tmp_emploi_menage.dta", replace
restore

merge 1:1 id_men using "$DOSSIER_OUT/_tmp_emploi_menage.dta", nogenerate
erase "$DOSSIER_OUT/_tmp_emploi_menage.dta"

*--- Libelles
label variable nb_occupes        "Nombre de membres occupes"
label variable nb_salaries        "Nombre de membres salaries"
label variable nb_informels       "Nombre de membres en emploi informel"
label variable a_actif_occupe     "Menage avec au moins un actif occupe"
label variable ratio_dependance   "Ratio de dependance demographique"

*--- Controles post-fusion
quietly count if missing(id_men)
local qc1 = r(N)
quietly count if nb_membres < nb_occupes & !missing(nb_occupes)
local qc2 = r(N)
quietly count if a_actif_occupe == 1 & nb_occupes == 0
local qc3 = r(N)

file open qc using "$DOSSIER_OUT/qc_consolidation_menages.csv", write replace
file write qc "controle,nombre,detail" _n
file write qc "menages sans identifiant," (`qc1') ",doit valoir 0" _n
file write qc "occupes > membres du menage," (`qc2') ",incoherence a verifier" _n
file write qc "a_actif_occupe=1 mais nb_occupes=0," (`qc3') ",doit valoir 0" _n
file close qc

compress
save "$DOSSIER_OUT/menages_consolide.dta", replace
display as text "  menages_consolide.dta : " _N " menages"

*--- Estimations finales croisees
quietly summarize nb_membres [aw=poids], meanonly
local e_tail  = r(mean)
quietly summarize ratio_dependance [aw=poids] if !missing(ratio_dependance), meanonly
local e_dep   = r(mean)
quietly summarize (a_actif_occupe==1) [aw=poids], meanonly
local e_act   = r(mean)*100
quietly summarize (sexe_cm==2) [aw=poids], meanonly
local e_femcm = r(mean)*100

file open est using "$DOSSIER_OUT/estimations_consolidation.csv", write replace
file write est "indicateur,valeur" _n
file write est "Taille moyenne du menage,"                     %5.2f (`e_tail')  _n
file write est "Ratio de dependance moyen,"                    %5.2f (`e_dep')   _n
file write est "Part menages avec actif occupe (%),"           %5.2f (`e_act')   _n
file write est "Part menages diriges par une femme (%),"       %5.2f (`e_femcm') _n
file close est

display as text "Consolidation terminee — $DOSSIER_OUT"
capture log close
