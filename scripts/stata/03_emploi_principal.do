*==============================================================================*
*  ERI-ESI — Module emploi principal des individus
*  do scripts/stata/03_emploi_principal.do
*==============================================================================*

clear all
set more off

global PAYS               "SEN"
global VAGUE              "2017"
global DOSSIER_OUT        "output/SEN"
global FICHIER_BASE       "base_individus_emploi_fusionnee.dta"
global HEURES_MAX         98
global REVENU_MIN         1000
global REVENU_MAX         5000000
global SEUIL_DUREE_LEGALE 40

use "$DOSSIER_OUT/$FICHIER_BASE", clear
display as text "Module emploi principal - $PAYS $VAGUE — " _N " obs."

capture log close _all
log using "$DOSSIER_OUT/journal_emploi_principal.log", replace text

*--- Verification des variables requises
local attendues "hh1 hh2 m1 weightemploy M4 sitac SE11 AP3 AP2_Niv1 AP10C AP10B AP18A_H AP18A_M AP18B_H AP18B_M AP13A AP13B AP13C AP6A AP6D AP6E AP16_21A AP16_22A AP16_23A AP11A R3"
foreach var of local attendues {
    capture confirm variable `var'
    if _rc {
        display as error "Variable manquante : `var'"
        log close
        error 111
    }
}

*--- Renommage vers noms internes stables
rename (hh1 hh2 m1 weightemploy M4) (id_grappe id_menage id_ordre poids_emploi age_ref)
gen str20 id_men = string(id_grappe) + "_" + string(id_menage)

gen byte eligible_module_emploi = cond(!missing(poids_emploi), 1, 2)

*--- Situation d'activite
gen situation_activite = sitac

gen byte situation_activite_grp = .
replace situation_activite_grp = 1 if situation_activite == 1
replace situation_activite_grp = 2 if situation_activite == 2
replace situation_activite_grp = 3 if inlist(situation_activite, 31, 32, 33)
replace situation_activite_grp = 4 if situation_activite == 4

*--- Raison d'inactivite (SE11, non SE9 qui est la disponibilite)
gen raison_inactivite = SE11

*--- Statut et type d'emploi
gen statut_emploi = AP3

gen byte type_emploi = .
replace type_emploi = 1 if inlist(statut_emploi, 1, 2, 3, 4, 5, 6, 10)
replace type_emploi = 2 if inlist(statut_emploi, 7, 8, 9)

gen byte flag_travail_enfant_10_14 = (age_ref >= 10 & age_ref <= 14 & !missing(statut_emploi))

*--- Branche d'activite (AP2_Niv1, non AP4 qui est le secteur institutionnel)
gen secteur_isic_principal = AP2_Niv1

gen byte secteur_isic_principal_4cat = .
replace secteur_isic_principal_4cat = 1 if secteur_isic_principal == 1
replace secteur_isic_principal_4cat = 2 if inlist(secteur_isic_principal, 2, 3, 4, 5, 6)
replace secteur_isic_principal_4cat = 3 if secteur_isic_principal == 7
replace secteur_isic_principal_4cat = 4 if secteur_isic_principal >= 8 & secteur_isic_principal <= 21

*--- Heures de travail (AP10C, non AP6A qui est le regime fiscal)
gen byte flag_heures_aberrantes = (!missing(AP10C) & AP10C > $HEURES_MAX)
gen heures_semaine_principal    = AP10C
replace heures_semaine_principal = . if flag_heures_aberrantes == 1

gen double duree_quotidienne = (AP18B_H + AP18B_M/60) - (AP18A_H + AP18A_M/60)
replace duree_quotidienne    = duree_quotidienne + 24 if duree_quotidienne < 0
gen double heures_calculees  = duree_quotidienne * AP10B
gen byte flag_ecart_heures   = (!missing(heures_semaine_principal) & !missing(heures_calculees) ///
    & abs(heures_semaine_principal - heures_calculees) > 10)
replace flag_ecart_heures = 0 if missing(flag_ecart_heures)
drop duree_quotidienne heures_calculees

*--- Sous-emploi lie a la duree
gen byte sous_emploi_duree = .
replace sous_emploi_duree  = 2 if !missing(heures_semaine_principal)
replace sous_emploi_duree  = 1 if !missing(heures_semaine_principal) ///
    & heures_semaine_principal < $SEUIL_DUREE_LEGALE ///
    & inlist(AP11A, 2, 3) & R3 == 1

*--- Revenu principal consolide (AP13A/B/C, non AP8A1 qui est l'anciennete)
gen double tranche_milieu = .
replace tranche_milieu =   17.5 if AP13C == 1
replace tranche_milieu =   67.5 if AP13C == 2
replace tranche_milieu =  125   if AP13C == 3
replace tranche_milieu =  175   if AP13C == 4
replace tranche_milieu =  225   if AP13C == 5
replace tranche_milieu =  275   if AP13C == 6
replace tranche_milieu =  325   if AP13C == 7
replace tranche_milieu =  375   if AP13C == 8
replace tranche_milieu =  425   if AP13C == 9
replace tranche_milieu =  475   if AP13C == 10
replace tranche_milieu =  525   if AP13C == 11
replace tranche_milieu =  575   if AP13C == 12
replace tranche_milieu =  625   if AP13C == 13
replace tranche_milieu =  675   if AP13C == 14
replace tranche_milieu =  725   if AP13C == 15
replace tranche_milieu =  775   if AP13C == 16
replace tranche_milieu =  825   if AP13C == 17
replace tranche_milieu =  875   if AP13C == 18
replace tranche_milieu =  950   if AP13C == 19
replace tranche_milieu = 1125   if AP13C == 20
replace tranche_milieu = 1375   if AP13C == 21
replace tranche_milieu = 1750   if AP13C == 22
replace tranche_milieu = 2250   if AP13C == 23
replace tranche_milieu = 2750   if AP13C == 24
replace tranche_milieu = 3000   if AP13C == 25
replace tranche_milieu = tranche_milieu * 1000

gen double revenu_principal_mensuel_fcfa = .
replace revenu_principal_mensuel_fcfa = AP13B             if AP13A == 1
replace revenu_principal_mensuel_fcfa = AP13B / 12        if AP13A == 2
replace revenu_principal_mensuel_fcfa = tranche_milieu    if AP13A == 3
replace revenu_principal_mensuel_fcfa = tranche_milieu/12 if AP13A == 4
drop tranche_milieu

gen byte revenu_source          = AP13A
gen byte flag_revenu_non_renseigne = inlist(AP13A, 5, 6)
gen byte flag_revenu_aberrant   = (!missing(revenu_principal_mensuel_fcfa) ///
    & (revenu_principal_mensuel_fcfa < $REVENU_MIN | revenu_principal_mensuel_fcfa > $REVENU_MAX))
replace revenu_principal_mensuel_fcfa = . if flag_revenu_aberrant == 1

*--- Formalite unite (AP6A/AP6D/AP6E, non AP7 qui est le lieu de travail)
gen byte formalite_unite = .
replace formalite_unite  = 2 if inlist(AP6E, 1, 2) & (AP6A == 3 | inlist(AP6D, 1, 3))
replace formalite_unite  = 1 if inlist(AP6E, 1, 2) & !missing(AP6A) & AP6A != 3 & AP6D == 2

*--- Formalite emploi (avantages employeur, salaries uniquement)
gen byte trois_criteres_ok = (!missing(AP16_21A) & !missing(AP16_22A) & !missing(AP16_23A))
gen byte formalite_emploi  = .
replace formalite_emploi   = 2 if trois_criteres_ok == 1 & !(AP16_21A == 1 & AP16_22A == 1 & AP16_23A == 1)
replace formalite_emploi   = 1 if trois_criteres_ok == 1 & AP16_21A == 1 & AP16_22A == 1 & AP16_23A == 1
drop trois_criteres_ok

*--- Libelles
label define lbl_sit_grp 1 "Actif occupe" 2 "Chomeur BIT" ///
    3 "Main-d'oeuvre potentielle" 4 "Inactif (hors main d'oeuvre)"
label values situation_activite_grp lbl_sit_grp

label define lbl_type 1 "Salarie" 2 "Independant"
label values type_emploi lbl_type

label define lbl_sect4 1 "Primaire" 2 "Industrie" 3 "Commerce" 4 "Service"
label values secteur_isic_principal_4cat lbl_sect4

label define lbl_formalite 1 "Formel" 2 "Informel"
label values formalite_unite lbl_formalite
label values formalite_emploi lbl_formalite

label define lbl_oui_non_elig 1 "Oui" 2 "Non"
label values eligible_module_emploi lbl_oui_non_elig
label values sous_emploi_duree lbl_oui_non_elig

label define lbl_rev_src 1 "Direct mensuel" 2 "Direct annuel (converti)" ///
    3 "Tranche mensuelle" 4 "Tranche annuelle (convertie)" 5 "Refuse" 6 "Ne sait pas"
label values revenu_source lbl_rev_src

label define lbl_bin 0 "Non" 1 "Oui"
label values flag_travail_enfant_10_14 flag_heures_aberrantes ///
             flag_ecart_heures flag_revenu_non_renseigne flag_revenu_aberrant lbl_bin

label variable id_grappe                   "Grappe"
label variable id_menage                   "Numero de menage"
label variable id_ordre                    "Numero d'ordre"
label variable id_men                      "Identifiant menage"
label variable poids_emploi                "Poids de sondage (emploi)"
label variable eligible_module_emploi      "Eligible au module emploi (10 ans et plus)"
label variable situation_activite          "Situation d'activite (code source)"
label variable situation_activite_grp      "Situation d'activite (regroupee)"
label variable raison_inactivite           "Raison d'inactivite"
label variable statut_emploi               "Statut dans l'emploi principal"
label variable type_emploi                 "Type d'emploi (salarie/independant)"
label variable flag_travail_enfant_10_14   "Travail des enfants (10-14 ans)"
label variable secteur_isic_principal      "Secteur d'activite (ISIC Rev.4, 21 sections)"
label variable secteur_isic_principal_4cat "Secteur d'activite (4 familles)"
label variable heures_semaine_principal    "Heures travaillees par semaine"
label variable sous_emploi_duree           "Sous-emploi lie a la duree"
label variable flag_heures_aberrantes      "Heures aberrantes neutralisees (>98h)"
label variable flag_ecart_heures           "Ecart >10h entre heures declarees et calculees"
label variable revenu_principal_mensuel_fcfa "Revenu mensuel consolide (FCFA)"
label variable revenu_source               "Mode de declaration du revenu"
label variable flag_revenu_non_renseigne   "Revenu non renseigne (refus/NSP)"
label variable flag_revenu_aberrant        "Revenu aberrant neutralise"
label variable formalite_unite             "Formalite de l'unite de production"
label variable formalite_emploi            "Formalite de l'emploi (salaries uniquement)"

*--- Controles de coherence
quietly count if situation_activite == 1 & missing(statut_emploi)
local qc1 = r(N)
quietly count if situation_activite != 1 & !missing(statut_emploi) & flag_travail_enfant_10_14 == 0
local qc2 = r(N)
quietly count if flag_travail_enfant_10_14 == 1
local qc3 = r(N)
quietly count if situation_activite == 1 & missing(secteur_isic_principal)
local qc4 = r(N)
quietly count if flag_heures_aberrantes == 1
local qc5 = r(N)
quietly count if flag_ecart_heures == 1
local qc6 = r(N)
quietly count if flag_revenu_non_renseigne == 1
local qc7 = r(N)
quietly count if flag_revenu_aberrant == 1
local qc8 = r(N)
quietly count if situation_activite != 4 & !missing(raison_inactivite)
local qc9 = r(N)
quietly count if situation_activite == 1 & missing(formalite_unite)
local qc10 = r(N)

file open qc using "$DOSSIER_OUT/qc_emploi_principal.csv", write replace
file write qc "controle,nombre,detail" _n
file write qc "occupes sans statut_emploi," (`qc1') ",doit etre nul ou tres faible" _n
file write qc "statut_emploi chez non-occupes adultes," (`qc2') ",doit valoir 0" _n
file write qc "travail enfants 10-14 ans (hors champ sitac)," (`qc3') ",pas une anomalie" _n
file write qc "occupes sans secteur_isic," (`qc4') ",a verifier" _n
file write qc "heures aberrantes neutralisees (>98h)," (`qc5') ",neutralisees" _n
file write qc "ecart >10h heures declarees vs calculees," (`qc6') ",absence de pause probable" _n
file write qc "revenu non renseigne (refus/NSP)," (`qc7') ",non impute" _n
file write qc "revenu aberrant neutralise," (`qc8') ",hors bornes plausibilite" _n
file write qc "raison inactivite renseignee hors inactifs," (`qc9') ",inclut main-oeuvre potentielle" _n
file write qc "occupes sans formalite_unite," (`qc10') ",inclut unites non marchandes" _n
file close qc

*--- Estimations ponderees
tempvar chomeur main_oeuvre independant salarie sect1 sect2 sect3 sect4 informel_emp heures48
gen `chomeur'     = (situation_activite == 2)
gen `main_oeuvre' = inlist(situation_activite, 1, 2)
gen `independant' = (situation_activite == 1 & type_emploi == 2)
gen `salarie'     = (situation_activite == 1 & type_emploi == 1)
gen `sect1'       = (situation_activite == 1 & secteur_isic_principal_4cat == 1)
gen `sect2'       = (situation_activite == 1 & secteur_isic_principal_4cat == 2)
gen `sect3'       = (situation_activite == 1 & secteur_isic_principal_4cat == 3)
gen `sect4'       = (situation_activite == 1 & secteur_isic_principal_4cat == 4)
gen `informel_emp' = (formalite_emploi == 2)
gen `heures48'    = (situation_activite == 1 & heures_semaine_principal > 48 & !missing(heures_semaine_principal))

quietly summarize `chomeur'    [aw=poids_emploi] if `main_oeuvre'==1, meanonly
local e_chom  = r(mean)*100
quietly summarize `independant' [aw=poids_emploi] if situation_activite==1, meanonly
local e_indep = r(mean)*100
quietly summarize `salarie'    [aw=poids_emploi] if situation_activite==1, meanonly
local e_sal   = r(mean)*100
quietly summarize `sect1'      [aw=poids_emploi] if situation_activite==1, meanonly
local e_s1    = r(mean)*100
quietly summarize `sect2'      [aw=poids_emploi] if situation_activite==1, meanonly
local e_s2    = r(mean)*100
quietly summarize `sect3'      [aw=poids_emploi] if situation_activite==1, meanonly
local e_s3    = r(mean)*100
quietly summarize `sect4'      [aw=poids_emploi] if situation_activite==1, meanonly
local e_s4    = r(mean)*100
quietly summarize `informel_emp' [aw=poids_emploi] if !missing(formalite_emploi), meanonly
local e_inf   = r(mean)*100
quietly summarize `heures48'   [aw=poids_emploi] if situation_activite==1 & !missing(heures_semaine_principal), meanonly
local e_h48   = r(mean)*100
quietly summarize revenu_principal_mensuel_fcfa [aw=poids_emploi] if situation_activite==1, meanonly
local e_rev   = r(mean)
quietly summarize heures_semaine_principal [aw=poids_emploi] if situation_activite==1, meanonly
local e_heures = r(mean)

file open est using "$DOSSIER_OUT/estimations_emploi_principal.csv", write replace
file write est "indicateur,valeur,reference_ansd" _n
file write est "Taux de chomage BIT (%),"                     %5.2f (`e_chom')  ",2.9" _n
file write est "Taux independants parmi occupes (%),"         %5.2f (`e_indep') ",66.1" _n
file write est "Taux de salarisation (%),"                    %5.2f (`e_sal')   ",38.6" _n
file write est "Secteur Primaire parmi occupes (%),"          %5.2f (`e_s1')    ",24.7" _n
file write est "Secteur Industrie parmi occupes (%),"         %5.2f (`e_s2')    ",19.0" _n
file write est "Secteur Commerce parmi occupes (%),"          %5.2f (`e_s3')    ",27.6" _n
file write est "Secteur Service parmi occupes (%),"           %5.2f (`e_s4')    ",28.7" _n
file write est "Taux d'emploi informel (%),"                  %5.2f (`e_inf')   ",95.4" _n
file write est "Taux >48h/semaine parmi occupes (%),"         %5.2f (`e_h48')   ",42.3" _n
file write est "Revenu mensuel moyen emploi principal (FCFA)," %9.2f (`e_rev')  ",125485" _n
file write est "Heures moyennes travaillees par semaine,"     %5.2f (`e_heures') ",." _n
file close est

*--- Sauvegarde
keep id_grappe id_menage id_ordre id_men poids_emploi eligible_module_emploi ///
     situation_activite situation_activite_grp raison_inactivite ///
     statut_emploi type_emploi flag_travail_enfant_10_14 ///
     secteur_isic_principal secteur_isic_principal_4cat ///
     heures_semaine_principal sous_emploi_duree flag_heures_aberrantes flag_ecart_heures ///
     revenu_principal_mensuel_fcfa revenu_source flag_revenu_non_renseigne flag_revenu_aberrant ///
     formalite_unite formalite_emploi

order id_grappe id_menage id_ordre id_men poids_emploi eligible_module_emploi ///
     situation_activite situation_activite_grp raison_inactivite ///
     statut_emploi type_emploi flag_travail_enfant_10_14 ///
     secteur_isic_principal secteur_isic_principal_4cat ///
     heures_semaine_principal sous_emploi_duree flag_heures_aberrantes flag_ecart_heures ///
     revenu_principal_mensuel_fcfa revenu_source flag_revenu_non_renseigne flag_revenu_aberrant ///
     formalite_unite formalite_emploi

compress
save "$DOSSIER_OUT/emploi_principal.dta", replace

display as text "emploi_principal.dta : " _N " lignes — " "$DOSSIER_OUT"
capture log close
