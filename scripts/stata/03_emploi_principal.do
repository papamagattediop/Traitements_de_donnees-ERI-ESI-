*==============================================================================*
*  ERI-ESI : bloc emploi principal des individus
*  Version Stata du module scripts/python/03_emploi_principal.py
*
*  Ce script prend la base individuelle fusionnee (roster + emploi) venue du
*  travail amont et construit un bloc de variables sur l'emploi principal au
*  niveau individu. Sa sortie, emploi_principal.dta, alimente l'assemblage
*  final et le fichier QAQC global.
*
*  ATTENTION : ce fichier n'a pas ete execute par son auteure (pas de Stata
*  disponible au moment de l'ecriture). La logique reprend fidelement celle
*  du module Python deja teste et valide sur les vraies donnees (resultats
*  compares avec succes au rapport final ANSD - cf. docs/note_emploi_principal.md).
*  A faire tourner et verifier avant de considerer ce .do comme fiable :
*  comparer emploi_principal.dta (Stata) a emploi_principal.dta (Python) sur
*  quelques variables cles (effectifs par modalite, moyennes ponderees).
*
*  Le fichier est encode en UTF-8 (Stata 14 ou plus).
*  L'execution se fait depuis la racine du depot :
*      do scripts/stata/03_emploi_principal.do
*==============================================================================*

clear all
set more off

*------------------------------------------------------------------------------*
* Le pays et les chemins vivent ici. D'un pays a l'autre, ce bloc de reglages
* suffit presque toujours ; le reste du code ne bouge pas.
*------------------------------------------------------------------------------*
global PAYS          "SEN"
global VAGUE         "2017"
global DOSSIER_OUT   "output/SEN"
global FICHIER_BASE  "base_individus_emploi_fusionnee.dta"

* Bornes de plausibilite et seuils (memes valeurs que CONFIG dans la version Python)
global HEURES_MAX        98
global REVENU_MIN        1000
global REVENU_MAX        5000000
global SEUIL_DUREE_LEGALE 40

display as text "Module emploi principal - pays $PAYS $VAGUE"
display as text "{hline 64}"

*------------------------------------------------------------------------------*
* La base fusionnee arrive du travail amont (fusion roster + emploi).
*------------------------------------------------------------------------------*
use "$DOSSIER_OUT/$FICHIER_BASE", clear
display as text "  base chargee : " _N " lignes"

*------------------------------------------------------------------------------*
* Un journal d'execution garde une trace datee de tout ce qui se passe ici.
*------------------------------------------------------------------------------*
capture mkdir "output"
capture mkdir "$DOSSIER_OUT"
capture log close _all
log using "$DOSSIER_OUT/journal_emploi_principal.log", replace text

*------------------------------------------------------------------------------*
* Avant tout traitement, la presence des variables attendues est verifiee. Si
* l'une manque, un message clair designe laquelle, et l'execution s'arrete la.
* Correspondance verifiee par inspection directe des metadonnees du fichier et
* du questionnaire officiel (docs/QST_QUESTIONNAIRE VOLET EMPLOI...docx) - le
* dictionnaire initial (docs/dictionnaire_variables.csv) etait faux sur 5 de
* ces variables, cf. docs/note_emploi_principal.md pour le detail.
*------------------------------------------------------------------------------*
local attendues "hh1 hh2 m1 weightemploy M4 sitac SE11 AP3 AP2_Niv1 AP10C AP10B AP18A_H AP18A_M AP18B_H AP18B_M AP13A AP13B AP13C AP6A AP6D AP6E AP16_21A AP16_22A AP16_23A AP11A R3"
foreach var of local attendues {
    capture confirm variable `var'
    if _rc {
        display as error "Variable attendue absente du fichier : `var'."
        display as error "Le bloc de correspondance (rename) doit etre adapte pour ce pays."
        log close
        error 111
    }
}
display as text "  validation colonnes : variables requises presentes"

*------------------------------------------------------------------------------*
* Les noms propres au pays deviennent ici des noms internes stables.
*------------------------------------------------------------------------------*
rename (hh1 hh2 m1 weightemploy M4) ///
       (id_grappe id_menage id_ordre poids_emploi age_ref)

gen str20 id_men = string(id_grappe) + "_" + string(id_menage)

* Eligibilite au module emploi (10 ans et plus) : basee sur la presence du
* poids emploi, plutot que de laisser deviner pourquoi une ligne est vide.
gen byte eligible_module_emploi = !missing(poids_emploi)
replace eligible_module_emploi = 2 if eligible_module_emploi == 0
quietly count if eligible_module_emploi == 1
display as text "  eligibles au module emploi (10 ans et plus) : `r(N)' / " _N

*------------------------------------------------------------------------------*
* Situation d'activite (sitac), deja calculee par l'ANSD. Regroupement en 4
* postes : 1 actif occupe, 2 chomeur BIT, 3 main d'oeuvre potentielle (fusion
* des sous-codes 31/32/33), 4 inactif hors main d'oeuvre.
*------------------------------------------------------------------------------*
gen situation_activite = sitac
label variable situation_activite "Situation d'activite (code source)"

gen byte situation_activite_grp = .
replace situation_activite_grp = 1 if situation_activite == 1
replace situation_activite_grp = 2 if situation_activite == 2
replace situation_activite_grp = 3 if inlist(situation_activite, 31, 32, 33)
replace situation_activite_grp = 4 if situation_activite == 4
label variable situation_activite_grp "Situation d'activite (regroupee)"

quietly count if missing(situation_activite)
display as text "  situation d'activite : `r(N)' manquant structurel (moins de 15 ans)"

*------------------------------------------------------------------------------*
* Raison d'inactivite (SE11). Le dictionnaire initial indiquait a tort SE9,
* qui est en realite la disponibilite. SE11 est structurellement renseignee
* chez les inactifs (situation_activite == 4).
*------------------------------------------------------------------------------*
gen raison_inactivite = SE11
label variable raison_inactivite "Raison d'inactivite"

quietly count if situation_activite == 4
local n_inactifs = r(N)
quietly count if situation_activite == 4 & !missing(raison_inactivite)
display as text "  raison d'inactivite : renseignee pour `r(N)' / `n_inactifs' inactifs"

*------------------------------------------------------------------------------*
* Statut dans l'emploi principal (AP3, categorie socioprofessionnelle),
* confirme correct des le depart. Type d'emploi derive du regroupement fait
* par le questionnaire lui-meme (bloc "Salarie" vs "Employeur/Independant").
*------------------------------------------------------------------------------*
gen statut_emploi = AP3
label variable statut_emploi "Statut dans l'emploi principal (categorie socioprofessionnelle)"

gen byte type_emploi = .
replace type_emploi = 1 if inlist(statut_emploi, 1, 2, 3, 4, 5, 6, 10)
replace type_emploi = 2 if inlist(statut_emploi, 7, 8, 9)
label variable type_emploi "Type d'emploi (salarie/independant)"

quietly count if missing(statut_emploi)
display as text "  statut emploi : `r(N)' manquant structurel (non occupe)"

* Travail des enfants (10-14 ans) : sitac exclut les moins de 15 ans par
* convention ANSD, mais AP3 peut etre renseigne pour des 10-14 ans qui
* travaillent reellement. Ce n'est pas une anomalie a corriger : un flag
* dedie le signale explicitement plutot que de le laisser se fondre dans les
* donnees ou d'etre lu a tort comme une erreur (cf. note methodologique).
gen byte flag_travail_enfant_10_14 = (age_ref >= 10 & age_ref <= 14 & !missing(statut_emploi))
quietly count if flag_travail_enfant_10_14 == 1
display as text "  travail des enfants (10-14 ans avec statut emploi renseigne) : `r(N)' cas"

*------------------------------------------------------------------------------*
* Branche/secteur d'activite (AP2_Niv1). Le dictionnaire initial pointait a
* tort vers AP4 (secteur institutionnel, concept different). AP2_Niv1 est
* deja au niveau section ISIC Rev.4 (21 postes), aucune agregation necessaire.
* Regroupement en 4 familles Primaire/Industrie/Commerce/Service, identique a
* celui du rapport final ANSD (tableau 5.18).
*------------------------------------------------------------------------------*
gen secteur_isic_principal = AP2_Niv1
label variable secteur_isic_principal "Secteur/branche d'activite (ISIC Rev.4, 21 sections)"

gen byte secteur_isic_principal_4cat = .
replace secteur_isic_principal_4cat = 1 if secteur_isic_principal == 1
replace secteur_isic_principal_4cat = 2 if inlist(secteur_isic_principal, 2, 3, 4, 5, 6)
replace secteur_isic_principal_4cat = 3 if secteur_isic_principal == 7
replace secteur_isic_principal_4cat = 4 if secteur_isic_principal >= 8 & secteur_isic_principal <= 21
label variable secteur_isic_principal_4cat "Secteur d'activite (4 familles)"

quietly count if missing(secteur_isic_principal)
display as text "  branche d'activite : `r(N)' manquant structurel (non occupe)"

*------------------------------------------------------------------------------*
* Heures de travail (AP10C, confirme heures/semaine par le questionnaire). Le
* dictionnaire initial pointait a tort vers AP6A (regime fiscal). Nettoyage :
* valeurs au-dela de la borne de plausibilite neutralisees et signalees.
*------------------------------------------------------------------------------*
gen byte flag_heures_aberrantes = (!missing(AP10C) & AP10C > $HEURES_MAX)
gen heures_semaine_principal = AP10C
replace heures_semaine_principal = . if flag_heures_aberrantes == 1
label variable heures_semaine_principal "Heures travaillees par semaine (emploi principal)"
label variable flag_heures_aberrantes "Heures aberrantes neutralisees (>98h/semaine)"

* Controle de coherence : duree quotidienne recalculee a partir des heures de
* debut/fin de journee (gestion du passage minuit), x jours travailles dans la
* semaine, comparee a la valeur declaree. Ecart eleve documente comme
* probablement du a l'absence de pause dejeuner dans ce calcul de controle -
* la variable principale reste la valeur declaree (cf. note methodologique).
gen double duree_quotidienne = (AP18B_H + AP18B_M/60) - (AP18A_H + AP18A_M/60)
replace duree_quotidienne = duree_quotidienne + 24 if duree_quotidienne < 0
gen double heures_calculees = duree_quotidienne * AP10B
gen byte flag_ecart_heures = (!missing(heures_semaine_principal) & !missing(heures_calculees) ///
    & abs(heures_semaine_principal - heures_calculees) > 10)
replace flag_ecart_heures = 0 if missing(flag_ecart_heures)
label variable flag_ecart_heures "Ecart >10h entre heures declarees et calculees"
drop duree_quotidienne heures_calculees

quietly count if missing(heures_semaine_principal)
display as text "  heures de travail : `r(N)' manquant (structurel + aberrant neutralise)"

*------------------------------------------------------------------------------*
* Sous-emploi lie a la duree du travail, definition officielle ANSD (chap.
* 1.5) : heures < duree legale + raison involontaire (AP11A: horaire fixe par
* la loi/l'employeur ou mauvaise conjoncture) + disponible pour travailler
* plus (R3). Le critere officiel "recherche d'un complement" n'a pas ete
* localise dans le perimetre inspecte ; l'omission est documentee (taux
* obtenu en Python : 3,1%, sous le taux implicite du rapport ANSD).
*------------------------------------------------------------------------------*
gen byte sous_emploi_duree = .
replace sous_emploi_duree = 2 if !missing(heures_semaine_principal)
replace sous_emploi_duree = 1 if !missing(heures_semaine_principal) ///
    & heures_semaine_principal < $SEUIL_DUREE_LEGALE ///
    & inlist(AP11A, 2, 3) & R3 == 1
label variable sous_emploi_duree "Sous-emploi lie a la duree du travail"

*------------------------------------------------------------------------------*
* Revenu de l'emploi principal, consolide selon le routage AP13a (le
* dictionnaire initial pointait a tort vers AP8A1, l'anciennete dans
* l'emploi) :
*   AP13a=1 : AP13b deja mensuel direct
*   AP13a=2 : AP13b annuel direct -> divise par 12
*   AP13a=3 : AP13c tranche mensuelle -> point milieu de la tranche
*   AP13a=4 : AP13c tranche annuelle -> point milieu / 12
*   AP13a=5 ou 6 (refus / ne sait pas) : non renseigne, jamais impute
*------------------------------------------------------------------------------*
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
* Derniere tranche ouverte (>=3000) : borne basse retenue, sous-estime
* volontairement plutot que de deviner un plafond.
replace tranche_milieu = 3000   if AP13C == 25
replace tranche_milieu = tranche_milieu * 1000

gen double revenu_principal_mensuel_fcfa = .
replace revenu_principal_mensuel_fcfa = AP13B          if AP13A == 1
replace revenu_principal_mensuel_fcfa = AP13B / 12      if AP13A == 2
replace revenu_principal_mensuel_fcfa = tranche_milieu  if AP13A == 3
replace revenu_principal_mensuel_fcfa = tranche_milieu / 12 if AP13A == 4
drop tranche_milieu

gen byte flag_revenu_non_renseigne = inlist(AP13A, 5, 6)
label variable flag_revenu_non_renseigne "Revenu non renseigne (refus/NSP)"

gen byte flag_revenu_aberrant = (!missing(revenu_principal_mensuel_fcfa) ///
    & (revenu_principal_mensuel_fcfa < $REVENU_MIN | revenu_principal_mensuel_fcfa > $REVENU_MAX))
replace revenu_principal_mensuel_fcfa = . if flag_revenu_aberrant == 1
label variable revenu_principal_mensuel_fcfa "Revenu mensuel consolide de l'emploi principal (FCFA)"
label variable flag_revenu_aberrant "Revenu aberrant neutralise"

gen byte revenu_source = AP13A
label variable revenu_source "Source/mode de declaration du revenu"

quietly count if missing(revenu_principal_mensuel_fcfa)
display as text "  revenu : `r(N)' manquant (structurel + refus/NSP + aberrant neutralise)"

*------------------------------------------------------------------------------*
* Formalite de l'unite (secteur informel ANSD, chap. 1.5) : parmi les unites
* marchandes (AP6E dans {1,2}), informelle si non-enregistrement fiscal
* (AP6A == 3) ou non-comptabilite formelle (AP6D dans {1,3}). Codes reels
* verifies dans les metadonnees (differents de l'ordre du questionnaire
* papier). Non applicable pour les unites non marchandes (AP6E == 3).
*------------------------------------------------------------------------------*
gen byte formalite_unite = .
replace formalite_unite = 2 if inlist(AP6E, 1, 2) & (AP6A == 3 | inlist(AP6D, 1, 3))
replace formalite_unite = 1 if inlist(AP6E, 1, 2) & !missing(AP6A) & AP6A != 3 & AP6D == 2
label variable formalite_unite "Formalite de l'unite de production (secteur informel ANSD)"

*------------------------------------------------------------------------------*
* Formalite de l'emploi (chap. 1.5) : un salarie est en emploi informel s'il
* manque au moins un des trois avantages employeur (cotisations de
* protection sociale, conges annuels payes, conges maladie remuneres).
* Administre aux salaries uniquement (structurellement absent pour les
* independants).
*------------------------------------------------------------------------------*
gen byte trois_criteres_ok = (!missing(AP16_21A) & !missing(AP16_22A) & !missing(AP16_23A))
gen byte formalite_emploi = .
replace formalite_emploi = 2 if trois_criteres_ok == 1 & !(AP16_21A == 1 & AP16_22A == 1 & AP16_23A == 1)
replace formalite_emploi = 1 if trois_criteres_ok == 1 & AP16_21A == 1 & AP16_22A == 1 & AP16_23A == 1
label variable formalite_emploi "Formalite de l'emploi (avantages employeur, salaries uniquement)"
drop trois_criteres_ok

quietly count if formalite_unite == 2
local qc_unite_inf = r(N)
quietly count if formalite_emploi == 2
local qc_emploi_inf = r(N)
display as text "  formalite unite : `qc_unite_inf' informel(s) | formalite emploi : `qc_emploi_inf' informel(s)"

*------------------------------------------------------------------------------*
* Libelles des variables categorielles construites par ce module (codes
* numeriques, jamais de texte brut - meme convention que le module
* demographie/geographie). Les variables gardees avec leur code source
* (situation_activite, statut_emploi, secteur_isic_principal, raison_inactivite)
* conservent leurs etiquettes d'origine, deja presentes dans le fichier.
*------------------------------------------------------------------------------*
label define lbl_situation_grp 1 "Actif occupe" 2 "Chomeur BIT" ///
    3 "Main-d'oeuvre potentielle" 4 "Inactif (hors main d'oeuvre)"
label values situation_activite_grp lbl_situation_grp

label define lbl_type_emploi 1 "Salarie" 2 "Independant"
label values type_emploi lbl_type_emploi

label define lbl_secteur_4cat 1 "Primaire" 2 "Industrie" 3 "Commerce" 4 "Service"
label values secteur_isic_principal_4cat lbl_secteur_4cat

label define lbl_formalite 1 "Formel" 2 "Informel"
label values formalite_unite lbl_formalite
label values formalite_emploi lbl_formalite

label define lbl_oui_non_elig 1 "Oui" 2 "Non"
label values eligible_module_emploi lbl_oui_non_elig
label values sous_emploi_duree lbl_oui_non_elig

label define lbl_revenu_source 1 "Direct mensuel" 2 "Direct annuel (converti)" ///
    3 "Tranche mensuelle" 4 "Tranche annuelle (convertie)" ///
    5 "Refuse de dire" 6 "Ne sait pas"
label values revenu_source lbl_revenu_source

label define lbl_binaire 0 "Non" 1 "Oui"
label values flag_travail_enfant_10_14 lbl_binaire
label values flag_heures_aberrantes lbl_binaire
label values flag_ecart_heures lbl_binaire
label values flag_revenu_non_renseigne lbl_binaire
label values flag_revenu_aberrant lbl_binaire

label variable id_grappe "Grappe"
label variable id_menage "Numero de menage"
label variable id_ordre  "Numero d'ordre"
label variable id_men    "Identifiant menage"
label variable poids_emploi "Poids de sondage (emploi)"
label variable eligible_module_emploi "Eligible au module emploi (10 ans et plus)"
label variable flag_travail_enfant_10_14 "Travail des enfants (10-14 ans avec statut emploi renseigne)"

*------------------------------------------------------------------------------*
* Controles de coherence. Distingue la vraie anomalie potentielle (adulte
* non-occupe avec statut renseigne) du travail des enfants (cas legitime,
* cf. flag_travail_enfant_10_14). Le resultat part dans un fichier lisible.
*------------------------------------------------------------------------------*
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
file write qc "occupes sans statut_emploi renseigne," (`qc1') ",doit etre nul ou tres faible" _n
file write qc "statut_emploi renseigne chez des non-occupes ADULTES (hors travail enfants)," (`qc2') ",doit valoir 0" _n
file write qc "travail des enfants (10-14 ans hors champ de sitac mais AP3 renseigne)," (`qc3') ",pas une anomalie" _n
file write qc "occupes sans secteur_isic_principal renseigne," (`qc4') ",a verifier" _n
file write qc "heures aberrantes neutralisees (>98h/semaine)," (`qc5') ",neutralisees, individus conserves" _n
file write qc "ecart >10h entre heures declarees et calculees," (`qc6') ",probablement absence de pause dejeuner" _n
file write qc "revenu non renseigne (refus/NSP)," (`qc7') ",non impute" _n
file write qc "revenu aberrant neutralise," (`qc8') ",hors bornes de plausibilite" _n
file write qc "raison d'inactivite renseignee pour des non-inactifs," (`qc9') ",cf. main d'oeuvre potentielle" _n
file write qc "occupes sans formalite_unite (unites non marchandes ou non renseigne)," (`qc10') ",inclut les unites non marchandes" _n
file close qc

*------------------------------------------------------------------------------*
* Estimations ponderees (poids_emploi = weightemploy), comparees quand
* possible aux chiffres deja publies dans le rapport final ANSD.
*------------------------------------------------------------------------------*
tempvar chomeur main_oeuvre independant salarie sect1 sect2 sect3 sect4 informel_emp heures48
gen `chomeur'    = (situation_activite == 2)
gen `main_oeuvre' = inlist(situation_activite, 1, 2)
gen `independant' = (situation_activite == 1 & type_emploi == 2)
gen `salarie'     = (situation_activite == 1 & type_emploi == 1)
gen `sect1' = (situation_activite == 1 & secteur_isic_principal_4cat == 1)
gen `sect2' = (situation_activite == 1 & secteur_isic_principal_4cat == 2)
gen `sect3' = (situation_activite == 1 & secteur_isic_principal_4cat == 3)
gen `sect4' = (situation_activite == 1 & secteur_isic_principal_4cat == 4)
gen `informel_emp' = (formalite_emploi == 2)
gen `heures48' = (situation_activite == 1 & heures_semaine_principal > 48 & !missing(heures_semaine_principal))

quietly summarize `chomeur' [aw = poids_emploi] if `main_oeuvre' == 1, meanonly
local e_chom = r(mean) * 100
quietly summarize `independant' [aw = poids_emploi] if situation_activite == 1, meanonly
local e_indep = r(mean) * 100
quietly summarize `salarie' [aw = poids_emploi] if situation_activite == 1, meanonly
local e_sal = r(mean) * 100
quietly summarize `sect1' [aw = poids_emploi] if situation_activite == 1, meanonly
local e_s1 = r(mean) * 100
quietly summarize `sect2' [aw = poids_emploi] if situation_activite == 1, meanonly
local e_s2 = r(mean) * 100
quietly summarize `sect3' [aw = poids_emploi] if situation_activite == 1, meanonly
local e_s3 = r(mean) * 100
quietly summarize `sect4' [aw = poids_emploi] if situation_activite == 1, meanonly
local e_s4 = r(mean) * 100
quietly summarize `informel_emp' [aw = poids_emploi] if !missing(formalite_emploi), meanonly
local e_inf = r(mean) * 100
quietly summarize `heures48' [aw = poids_emploi] if situation_activite == 1 & !missing(heures_semaine_principal), meanonly
local e_h48 = r(mean) * 100
quietly summarize revenu_principal_mensuel_fcfa [aw = poids_emploi] if situation_activite == 1, meanonly
local e_rev = r(mean)
quietly summarize heures_semaine_principal [aw = poids_emploi] if situation_activite == 1, meanonly
local e_heures = r(mean)

file open est using "$DOSSIER_OUT/estimations_emploi_principal.csv", write replace
file write est "indicateur,valeur,reference_ansd" _n
file write est "Taux de chomage BIT (%)," %5.2f (`e_chom') ",2.9" _n
file write est "Taux d'emplois vulnerables - independant (%)," %5.2f (`e_indep') ",66.1" _n
file write est "Taux de salarisation (%)," %5.2f (`e_sal') ",38.6" _n
file write est "Secteur Primaire parmi occupes (%)," %5.2f (`e_s1') ",24.7" _n
file write est "Secteur Industrie parmi occupes (%)," %5.2f (`e_s2') ",19.0" _n
file write est "Secteur Commerce parmi occupes (%)," %5.2f (`e_s3') ",27.6" _n
file write est "Secteur Service parmi occupes (%)," %5.2f (`e_s4') ",28.7" _n
file write est "Taux d'emploi informel (%)," %5.2f (`e_inf') ",95.4" _n
file write est "Taux >48h/semaine parmi occupes (%)," %5.2f (`e_h48') ",42.3" _n
file write est "Revenu mensuel moyen emploi principal (FCFA)," %9.2f (`e_rev') ",125485" _n
file write est "Heures moyennes travaillees par semaine," %5.2f (`e_heures') ",." _n
file close est

*------------------------------------------------------------------------------*
* Table finale. Seules les variables construites restent, dans un ordre
* lisible, puis la table part sur le disque.
*------------------------------------------------------------------------------*
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

display as text "{hline 64}"
display as text "Table emploi principal ecrite : $DOSSIER_OUT/emploi_principal.dta (" _N " lignes)"
display as text "Controles       -> $DOSSIER_OUT/qc_emploi_principal.csv"
display as text "Estimations     -> $DOSSIER_OUT/estimations_emploi_principal.csv"
display as text "Journal         -> $DOSSIER_OUT/journal_emploi_principal.log"
display as text "Termine."

capture log close

*==============================================================================*
* Fin du module. NON TESTE - a faire tourner en Stata avant de committer,
* et a comparer a emploi_principal.dta (version Python) sur quelques
* variables cles avant de considerer ce fichier comme fiable.
*==============================================================================*
