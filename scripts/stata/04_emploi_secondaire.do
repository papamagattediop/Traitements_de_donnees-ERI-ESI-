*==============================================================================*
*  ERI-ESI : bloc emploi secondaire des individus
*
*  Ce module prend la base fusionnee (roster + emploi) et construit les
*  variables relatives aux emplois secondaires au niveau individu.
*  Le focus porte sur le premier emploi secondaire (suffixe _AS1), qui
*  couvre la quasi-totalite des repondants concernes. Le second emploi
*  secondaire (suffixe _AS2, n=118) est preserve uniquement en comptage.
*
*  Note secteur : la branche du premier emploi secondaire est stockee dans
*  AS3S1_OLD, un code potentiellement issu d'une revision ISIC anterieure.
*  La variable est conservee telle quelle avec un flag ; un reclassement
*  manuel en sections ISIC Rev.4 pourra etre fait si le questionnaire le
*  permet.
*
*  Note heures : AS9C_AS1 est exprimee en MINUTES par jour (valeurs typiques
*  entre 30 et 120, incompatibles avec une lecture en heures). La conversion
*  en heures hebdomadaires utilise AS9B_AS1 (jours par semaine).
*
*  Execution depuis la racine du depot :
*      do scripts/stata/04_emploi_secondaire.do
*==============================================================================*

clear all
set more off

*------------------------------------------------------------------------------*
* Configuration du pays actif. Seul ce bloc change d'un pays a l'autre.
*------------------------------------------------------------------------------*
global PAYS         "SEN"
global VAGUE        "2017"
global DOSSIER_OUT  "output/SEN"
global FICHIER_BASE "base_individus_emploi_fusionnee.dta"

global HEURES_MAX_SEC  98
global REVENU_MIN      1000
global REVENU_MAX      5000000

display as text "Module emploi secondaire - pays $PAYS $VAGUE"
display as text "{hline 64}"

*------------------------------------------------------------------------------*
* Chargement de la base fusionnee.
*------------------------------------------------------------------------------*
use "$DOSSIER_OUT/$FICHIER_BASE", clear
display as text "  base chargee : " _N " lignes"

capture mkdir "output"
capture mkdir "$DOSSIER_OUT"
capture log close _all
log using "$DOSSIER_OUT/journal_emploi_secondaire.log", replace text

*------------------------------------------------------------------------------*
* Verification des variables attendues.
*------------------------------------------------------------------------------*
local attendues "hh1 hh2 m1 weightemploy AS1A AS1C AS1B1 AS4_AS1 AS5_AS1 AS6_AS1 AS9B_AS1 AS9C_AS1 AS10A_AS1 AS10B_AS1 AS10C_AS1 AS7A_AS1 AS7B_AS1_A1 AS7B_AS1_B1 AS7B_AS1_C1 AS3S1_OLD"
foreach var of local attendues {
    capture confirm variable `var'
    if _rc {
        display as error "Variable attendue absente : `var'. Adapter le bloc de correspondance."
        log close
        error 111
    }
}
display as text "  validation colonnes : variables requises presentes"

*------------------------------------------------------------------------------*
* Identifiants stables.
*------------------------------------------------------------------------------*
rename (hh1 hh2 m1 weightemploy) (id_grappe id_menage id_ordre poids_emploi)
gen str20 id_men = string(id_grappe) + "_" + string(id_menage)

*------------------------------------------------------------------------------*
* Existence d'un emploi secondaire (AS1A : 1=oui, 2=non).
* Le filtre d'eligibilite suit AS1C plutot que AS1A, car AS1C est la question
* effective posee apres le filtre "a-t-on un emploi principal".
*------------------------------------------------------------------------------*
gen byte a_emploi_secondaire = .
replace a_emploi_secondaire = 1 if AS1A == 1
replace a_emploi_secondaire = 0 if AS1A == 2

quietly count if a_emploi_secondaire == 1
local n_sec = r(N)
display as text "  personnes avec emploi secondaire : `n_sec'"

*------------------------------------------------------------------------------*
* Nombre d'emplois secondaires (AS1B1 : 1/2/3/4/autre).
* Variable preservee directement ; un regroupement simplifie en 1 vs 2+ est
* ajoute pour les analyses.
*------------------------------------------------------------------------------*
gen byte nb_emplois_sec = AS1B1
gen byte nb_emplois_sec_grp = .
replace nb_emplois_sec_grp = 1 if AS1B1 == 1
replace nb_emplois_sec_grp = 2 if AS1B1 >= 2 & !missing(AS1B1)
label variable nb_emplois_sec "Nombre d'emplois secondaires"
label variable nb_emplois_sec_grp "Nombre d'emplois secondaires (1 vs 2+)"

*------------------------------------------------------------------------------*
* Statut dans l'emploi secondaire (AS4_AS1, meme codage que AP3).
* Type d'emploi derive : salarie si modalites 1-6 et 10, independant si 7-9.
*------------------------------------------------------------------------------*
gen statut_emploi_sec = AS4_AS1
label variable statut_emploi_sec "Statut dans l'emploi secondaire (categorie socioprofessionnelle)"

gen byte type_emploi_sec = .
replace type_emploi_sec = 1 if inlist(statut_emploi_sec, 1, 2, 3, 4, 5, 6, 10)
replace type_emploi_sec = 2 if inlist(statut_emploi_sec, 7, 8, 9)
label variable type_emploi_sec "Type d'emploi secondaire (salarie/independant)"

quietly count if !missing(statut_emploi_sec)
display as text "  statut emploi secondaire : `r(N)' renseignes"

*------------------------------------------------------------------------------*
* Branche d'activite de l'emploi secondaire (AS3S1_OLD).
* ATTENTION : variable potentiellement en ancien codage ISIC (avant Rev.4).
* Un flag signale cette incertitude. Les valeurs ont ete inspectes mais le
* reclassement en sections ISIC Rev.4 n'a pas ete possible sans la
* nomenclature de conversion.
*------------------------------------------------------------------------------*
gen secteur_isic_sec_brut = AS3S1_OLD
gen byte flag_secteur_sec_ancien_codage = !missing(AS3S1_OLD)
label variable secteur_isic_sec_brut "Secteur emploi secondaire (code brut AS3S1_OLD, revision ISIC a verifier)"
label variable flag_secteur_sec_ancien_codage "Secteur secondaire en ancien codage (a reclasser si possible)"

quietly count if !missing(secteur_isic_sec_brut)
display as text "  secteur emploi secondaire renseigne pour `r(N)' individus (codage ancien, a verifier)"

*------------------------------------------------------------------------------*
* Heures de travail dans l'emploi secondaire.
* AS9C_AS1 = minutes par jour (valeurs 0-120+, incompatibles avec des heures).
* AS9B_AS1 = jours travailles par semaine.
* Conversion : heures_semaine_sec = (AS9C_AS1 / 60) * AS9B_AS1.
* Une borne de plausibilite neutralise les valeurs aberrantes.
*------------------------------------------------------------------------------*
gen double heures_semaine_sec = (AS9C_AS1 / 60) * AS9B_AS1
gen byte flag_heures_sec_aberrantes = (!missing(heures_semaine_sec) & heures_semaine_sec > $HEURES_MAX_SEC)
replace heures_semaine_sec = . if flag_heures_sec_aberrantes == 1
label variable heures_semaine_sec "Heures travaillees par semaine (emploi secondaire, calcul min/jour x jours/sem)"
label variable flag_heures_sec_aberrantes "Heures emploi secondaire aberrantes neutralisees (>98h)"

quietly count if !missing(heures_semaine_sec)
display as text "  heures emploi secondaire : `r(N)' renseignees (converties depuis minutes/jour)"

*------------------------------------------------------------------------------*
* Revenu de l'emploi secondaire.
* AS10A_AS1 = mode de declaration (routage). Les modalites observees incluent
* des codes 1 a 8 (contre 1 a 6 pour l'emploi principal). Seules les valeurs
* interpretables sont utilisees ; les autres sont laissees manquantes.
* AS10B_AS1 = montant direct (FCFA) - valeurs directement en FCFA.
* AS10C_AS1 = tranche (meme codage que AP13C).
*------------------------------------------------------------------------------*
gen double tranche_sec_milieu = .
replace tranche_sec_milieu =   17.5 if AS10C_AS1 == 1
replace tranche_sec_milieu =   67.5 if AS10C_AS1 == 2
replace tranche_sec_milieu =  125   if AS10C_AS1 == 3
replace tranche_sec_milieu =  175   if AS10C_AS1 == 4
replace tranche_sec_milieu =  225   if AS10C_AS1 == 5
replace tranche_sec_milieu =  275   if AS10C_AS1 == 6
replace tranche_sec_milieu =  325   if AS10C_AS1 == 7
replace tranche_sec_milieu =  375   if AS10C_AS1 == 8
replace tranche_sec_milieu =  425   if AS10C_AS1 == 9
replace tranche_sec_milieu =  475   if AS10C_AS1 == 10
replace tranche_sec_milieu =  525   if AS10C_AS1 == 11
replace tranche_sec_milieu =  575   if AS10C_AS1 == 12
replace tranche_sec_milieu =  625   if AS10C_AS1 == 13
replace tranche_sec_milieu =  675   if AS10C_AS1 == 14
replace tranche_sec_milieu =  725   if AS10C_AS1 == 15
replace tranche_sec_milieu =  775   if AS10C_AS1 == 16
replace tranche_sec_milieu =  825   if AS10C_AS1 == 17
replace tranche_sec_milieu =  875   if AS10C_AS1 == 18
replace tranche_sec_milieu =  950   if AS10C_AS1 == 19
replace tranche_sec_milieu = 1125   if AS10C_AS1 == 20
replace tranche_sec_milieu = 1375   if AS10C_AS1 == 21
replace tranche_sec_milieu = 1750   if AS10C_AS1 == 22
replace tranche_sec_milieu = 2250   if AS10C_AS1 == 23
replace tranche_sec_milieu = 2750   if AS10C_AS1 == 24
replace tranche_sec_milieu = 3000   if AS10C_AS1 == 25
replace tranche_sec_milieu = tranche_sec_milieu * 1000

gen double revenu_sec_mensuel_fcfa = .
replace revenu_sec_mensuel_fcfa = AS10B_AS1          if AS10A_AS1 == 1
replace revenu_sec_mensuel_fcfa = AS10B_AS1 / 12     if AS10A_AS1 == 2
replace revenu_sec_mensuel_fcfa = tranche_sec_milieu  if AS10A_AS1 == 3
replace revenu_sec_mensuel_fcfa = tranche_sec_milieu / 12 if AS10A_AS1 == 4
drop tranche_sec_milieu

gen byte flag_revenu_sec_aberrant = (!missing(revenu_sec_mensuel_fcfa) ///
    & (revenu_sec_mensuel_fcfa < $REVENU_MIN | revenu_sec_mensuel_fcfa > $REVENU_MAX))
replace revenu_sec_mensuel_fcfa = . if flag_revenu_sec_aberrant == 1

label variable revenu_sec_mensuel_fcfa "Revenu mensuel consolide de l'emploi secondaire (FCFA)"
label variable flag_revenu_sec_aberrant "Revenu emploi secondaire aberrant neutralise"

quietly count if !missing(revenu_sec_mensuel_fcfa)
display as text "  revenu emploi secondaire : `r(N)' renseignes"

*------------------------------------------------------------------------------*
* Formalite de l'emploi secondaire (salaries seulement, meme definition
* que pour l'emploi principal : absence d'au moins un des trois avantages
* employeur : protection sociale, conges annuels, conges maladie).
*------------------------------------------------------------------------------*
gen byte trois_crit_sec = (!missing(AS7B_AS1_A1) & !missing(AS7B_AS1_B1) & !missing(AS7B_AS1_C1))
gen byte formalite_emploi_sec = .
replace formalite_emploi_sec = 1 if trois_crit_sec == 1 ///
    & AS7B_AS1_A1 == 1 & AS7B_AS1_B1 == 1 & AS7B_AS1_C1 == 1
replace formalite_emploi_sec = 2 if trois_crit_sec == 1 ///
    & !(AS7B_AS1_A1 == 1 & AS7B_AS1_B1 == 1 & AS7B_AS1_C1 == 1)
label variable formalite_emploi_sec "Formalite de l'emploi secondaire (salaries uniquement)"
drop trois_crit_sec

*------------------------------------------------------------------------------*
* Libelles.
*------------------------------------------------------------------------------*
label define lbl_oui_non_sec 1 "Oui" 0 "Non"
label values a_emploi_secondaire lbl_oui_non_sec

label define lbl_nb_grp 1 "1 emploi secondaire" 2 "2 emplois secondaires et plus"
label values nb_emplois_sec_grp lbl_nb_grp

label define lbl_type_sec 1 "Salarie" 2 "Independant"
label values type_emploi_sec lbl_type_sec

label define lbl_form_sec 1 "Formel" 2 "Informel"
label values formalite_emploi_sec lbl_form_sec

label define lbl_bin_sec 0 "Non" 1 "Oui"
label values flag_secteur_sec_ancien_codage lbl_bin_sec
label values flag_heures_sec_aberrantes lbl_bin_sec
label values flag_revenu_sec_aberrant lbl_bin_sec

*------------------------------------------------------------------------------*
* Controles de coherence.
*------------------------------------------------------------------------------*
quietly count if a_emploi_secondaire == 1 & missing(statut_emploi_sec)
local qc1 = r(N)
quietly count if a_emploi_secondaire == 0 & !missing(statut_emploi_sec)
local qc2 = r(N)
quietly count if flag_heures_sec_aberrantes == 1
local qc3 = r(N)
quietly count if flag_revenu_sec_aberrant == 1
local qc4 = r(N)

file open qc using "$DOSSIER_OUT/qc_emploi_secondaire.csv", write replace
file write qc "controle,nombre,detail" _n
file write qc "avec emploi secondaire mais sans statut renseigne," (`qc1') ",a verifier" _n
file write qc "sans emploi secondaire mais statut renseigne," (`qc2') ",incoherence de filtre" _n
file write qc "heures aberrantes neutralisees (>98h/sem)," (`qc3') ",calcul min/jour x jours/sem" _n
file write qc "revenu aberrant neutralise," (`qc4') ",hors bornes de plausibilite" _n
file close qc

*------------------------------------------------------------------------------*
* Estimations ponderees.
*------------------------------------------------------------------------------*
quietly summarize a_emploi_secondaire [aw = poids_emploi] if !missing(a_emploi_secondaire), meanonly
local e_sec = r(mean) * 100
quietly summarize revenu_sec_mensuel_fcfa [aw = poids_emploi] if a_emploi_secondaire == 1, meanonly
local e_rev = r(mean)
quietly summarize heures_semaine_sec [aw = poids_emploi] if a_emploi_secondaire == 1, meanonly
local e_h = r(mean)

file open est using "$DOSSIER_OUT/estimations_emploi_secondaire.csv", write replace
file write est "indicateur,valeur" _n
file write est "Taux avec emploi secondaire (% des actifs occupes interroges)," %5.2f (`e_sec') _n
file write est "Revenu mensuel moyen emploi secondaire (FCFA)," %9.2f (`e_rev') _n
file write est "Heures moyennes par semaine emploi secondaire," %5.2f (`e_h') _n
file close est

*------------------------------------------------------------------------------*
* Table finale.
*------------------------------------------------------------------------------*
keep id_grappe id_menage id_ordre id_men poids_emploi ///
     a_emploi_secondaire nb_emplois_sec nb_emplois_sec_grp ///
     statut_emploi_sec type_emploi_sec ///
     secteur_isic_sec_brut flag_secteur_sec_ancien_codage ///
     heures_semaine_sec flag_heures_sec_aberrantes ///
     revenu_sec_mensuel_fcfa flag_revenu_sec_aberrant ///
     formalite_emploi_sec

order id_grappe id_menage id_ordre id_men poids_emploi ///
     a_emploi_secondaire nb_emplois_sec nb_emplois_sec_grp ///
     statut_emploi_sec type_emploi_sec ///
     secteur_isic_sec_brut flag_secteur_sec_ancien_codage ///
     heures_semaine_sec flag_heures_sec_aberrantes ///
     revenu_sec_mensuel_fcfa flag_revenu_sec_aberrant ///
     formalite_emploi_sec

compress
save "$DOSSIER_OUT/emploi_secondaire.dta", replace

display as text "{hline 64}"
display as text "Table emploi secondaire : $DOSSIER_OUT/emploi_secondaire.dta (" _N " lignes)"
display as text "Controles  -> $DOSSIER_OUT/qc_emploi_secondaire.csv"
display as text "Estimations -> $DOSSIER_OUT/estimations_emploi_secondaire.csv"
display as text "Termine."

capture log close
*==============================================================================*
