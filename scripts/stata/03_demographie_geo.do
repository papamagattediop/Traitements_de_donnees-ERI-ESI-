*==============================================================================*
*  ERI-ESI : bloc démographie et géographie des individus (Personne 2)
*  Version Stata du module scripts/python/03_demographie_geo.py
*
*  Ce script prend la base individuelle fusionnée (roster + emploi) venue du
*  travail amont et construit un bloc propre de variables démographiques et
*  géographiques au niveau individu. Sa sortie, individus_demo_geo.dta, nourrit
*  la démographie du chef de ménage et l'assemblage final.
*
*  Le fichier est encodé en UTF-8 (Stata 14 ou plus).
*  L'exécution se fait depuis la racine du dépôt :
*      do scripts/stata/03_demographie_geo.do
*==============================================================================*

version 14
clear all
set more off

*------------------------------------------------------------------------------*
* Le pays et les chemins vivent ici. D'un pays à l'autre, ce bloc de réglages
* suffit presque toujours ; le reste du code ne bouge pas.
*------------------------------------------------------------------------------*
global PAYS          "SEN"
global VAGUE         "2017"
global DOSSIER_OUT   "output/SEN"
global FICHIER_BASE  "base_individus_emploi_fusionnee.dta"

display as text "Module démographie/géographie - pays $PAYS $VAGUE"
display as text "{hline 64}"

*------------------------------------------------------------------------------*
* La base fusionnée arrive du travail amont (fusion roster + emploi).
*------------------------------------------------------------------------------*
use "$DOSSIER_OUT/$FICHIER_BASE", clear
display as text "  base chargée : " _N " lignes"

*------------------------------------------------------------------------------*
* Un journal d'exécution garde une trace datée de tout ce qui se passe ici.
*------------------------------------------------------------------------------*
capture mkdir "output"
capture mkdir "$DOSSIER_OUT"
capture log close _all
log using "$DOSSIER_OUT/journal_demo_geo.log", replace text

*------------------------------------------------------------------------------*
* Avant tout traitement, la présence des variables attendues est vérifiée. Si
* l'une manque, un message clair désigne laquelle, et l'exécution s'arrête là,
* plutôt que de laisser survenir plus loin une erreur difficile à lire. C'est ce
* qui permet d'accueillir proprement le fichier d'un autre pays.
*------------------------------------------------------------------------------*
local attendues "hh1 hh2 m1 hhweight hhsize M3 M4 M2 M25 M13 M15 M16a M20a M19a Region MILIEU"
foreach var of local attendues {
    capture confirm variable `var'
    if _rc {
        display as error "Variable attendue absente du fichier : `var'."
        display as error "Le bloc de correspondance (rename) doit être adapté pour ce pays."
        log close
        error 111
    }
}
display as text "  validation colonnes : variables requises présentes"

*------------------------------------------------------------------------------*
* Les noms propres au pays deviennent ici des noms internes stables. C'est le
* seul endroit vraiment sensible au pays : les valeurs, elles, sont harmonisées
* d'un pays ERI-ESI à l'autre, donc la suite du recodage reste valable partout.
*------------------------------------------------------------------------------*
rename (hh1 hh2 m1 hhweight hhsize M3 m3E M4 M2 M25 M13 M15 M16a M20a M19a Region MILIEU) ///
       (id_grappe id_menage id_ordre poids taille_menage sexe sexe_emp age lien_cm ///
        matrimoniale ecole_deja ecole_actuelle niv_actuel niv_atteint niv_secours region milieu)

* Un identifiant de ménage unique naît de la grappe et du numéro de ménage.
gen str20 id_men = string(id_grappe) + "_" + string(id_menage)

*------------------------------------------------------------------------------*
* Sexe. Le sexe du roster est complet, donc il fait foi. Celui du module emploi,
* posé aux quinze ans et plus, sert seulement de témoin : là où les deux se
* contredisent, un drapeau le signale, mais la référence n'est jamais écrasée.
*------------------------------------------------------------------------------*
gen byte flag_sexe_incoherent = (!missing(sexe) & !missing(sexe_emp) & sexe != sexe_emp)
quietly count if flag_sexe_incoherent == 1
display as text "  sexe : `r(N)' désaccord(s) roster/emploi (roster conservé)"

*------------------------------------------------------------------------------*
* Âge. Un code 99 veut dire « ne sait pas » : la valeur manquante prend sa
* place. Les âges hors du possible (au delà de 110 ans) s'effacent aussi, et un
* drapeau garde la mémoire du geste.
*------------------------------------------------------------------------------*
replace age = . if age == 99
gen byte flag_age_aberrant = (!missing(age) & (age < 0 | age > 110))
replace age = . if flag_age_aberrant == 1

* Un groupe d'âge en huit tranches accompagne l'âge exact.
gen byte groupe_age = .
replace groupe_age = 1 if age >= 0  & age < 5
replace groupe_age = 2 if age >= 5  & age < 10
replace groupe_age = 3 if age >= 10 & age < 15
replace groupe_age = 4 if age >= 15 & age < 25
replace groupe_age = 5 if age >= 25 & age < 35
replace groupe_age = 6 if age >= 35 & age < 50
replace groupe_age = 7 if age >= 50 & age < 65
replace groupe_age = 8 if age >= 65 & age < .
quietly count if flag_age_aberrant == 1
display as text "  âge : `r(N)' aberrant(s) neutralisé(s)"

*------------------------------------------------------------------------------*
* Lien avec le chef de ménage. Le lien détaillé reste tel quel ; un regroupement
* plus lisible en cinq postes l'accompagne.
*------------------------------------------------------------------------------*
gen byte lien_cm_grp = .
replace lien_cm_grp = 1 if lien_cm == 1
replace lien_cm_grp = 2 if lien_cm == 2
replace lien_cm_grp = 3 if lien_cm == 3
replace lien_cm_grp = 4 if inlist(lien_cm, 4, 5, 6, 7)
replace lien_cm_grp = 5 if inlist(lien_cm, 8, 9)

*------------------------------------------------------------------------------*
* Situation matrimoniale. La question ne concerne que les douze ans et plus.
* En dessous, la modalité « non applicable » remplace le vide : ce n'est pas un
* manquant réel, seulement une question sans objet. Au dessus, un manquant qui
* subsiste est marqué explicitement.
*------------------------------------------------------------------------------*
gen byte flag_matrimoniale_manquant = (missing(matrimoniale) & age >= 12 & !missing(age))
replace matrimoniale = 0 if age < 12 & !missing(age)
replace matrimoniale = 9 if flag_matrimoniale_manquant == 1
quietly count if matrimoniale == 0
local n_namat = r(N)
quietly count if flag_matrimoniale_manquant == 1
display as text "  matrimoniale : `n_namat' non applicable (<12 ans), `r(N)' manquant(s) réel(s)"

*------------------------------------------------------------------------------*
* Niveau d'études. Le niveau se reconstruit à partir de plusieurs questions,
* selon la situation scolaire de la personne : celui qui étudie encore donne son
* niveau actuel, celui qui a quitté l'école donne le niveau atteint, avec un
* recours à l'année précédente si besoin. L'échelle est ensuite simplifiée pour
* rester comparable d'un pays à l'autre.
*------------------------------------------------------------------------------*
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
* Celui qui n'a jamais fréquenté l'école reçoit le niveau « aucun ».
replace niveau_etudes = 1 if ecole_deja == 2
* Le tout jeune enfant, avant l'âge scolaire, reçoit « non applicable ».
replace niveau_etudes = 0 if missing(ecole_deja) & age < 6 & !missing(age)

*------------------------------------------------------------------------------*
* Branche d'études. Générale ou technique, elle se lit dans le même code
* d'origine, car les modalités distinguent déjà ces deux filières au secondaire.
*------------------------------------------------------------------------------*
gen byte branche_etudes = .
replace branche_etudes = 1 if inlist(niveau_brut, 2, 3)
replace branche_etudes = 2 if inlist(niveau_brut, 4, 5)
replace branche_etudes = 3 if niveau_brut == 6
replace branche_etudes = 0 if inlist(niveau_brut, 0, 1)
* Les non applicables d'éducation s'alignent sur le niveau.
replace branche_etudes = 0 if inlist(niveau_etudes, 0, 1)

quietly count if !missing(niveau_etudes)
display as text "  éducation : niveau renseigné pour `r(N)' individus"

*------------------------------------------------------------------------------*
* Géographie. Région et milieu de résidence viennent directement de la base.
* Le département, lui, n'existe pas dans le fichier Sénégal : la colonne est
* créée vide pour garder un schéma identique d'un pays à l'autre. Un pays qui
* dispose du département n'a qu'à le renommer dans le bloc de réglages plus haut.
*------------------------------------------------------------------------------*
gen departement = .
display as text "  géographie : région et milieu recodés, département absent (non collecté ici)"

*------------------------------------------------------------------------------*
* Libellés. Les modalités portent les accents, pour une lecture directe dans
* Stata. Les variables reprises du fichier gardent leurs étiquettes d'origine ;
* seules les variables construites reçoivent de nouvelles étiquettes.
*------------------------------------------------------------------------------*
label define lbl_groupe_age 1 "0-4 ans" 2 "5-9 ans" 3 "10-14 ans" 4 "15-24 ans" ///
    5 "25-34 ans" 6 "35-49 ans" 7 "50-64 ans" 8 "65 ans et plus"
label values groupe_age lbl_groupe_age

label define lbl_lien_grp 1 "Chef de ménage" 2 "Conjoint(e)" 3 "Enfant" ///
    4 "Autre parent" 5 "Sans lien de parenté / domestique"
label values lien_cm_grp lbl_lien_grp

label define lbl_niveau 0 "Non applicable (trop jeune)" 1 "Aucun (jamais scolarisé)" ///
    2 "Préscolaire" 3 "Primaire" 4 "Secondaire premier cycle" ///
    5 "Secondaire second cycle" 6 "Supérieur"
label values niveau_etudes lbl_niveau

label define lbl_branche 0 "Non applicable" 1 "Enseignement général" ///
    2 "Enseignement technique" 3 "Supérieur"
label values branche_etudes lbl_branche

label define lbl_oui_non 0 "Non" 1 "Oui"
label values flag_sexe_incoherent lbl_oui_non
label values flag_age_aberrant lbl_oui_non
label values flag_matrimoniale_manquant lbl_oui_non

* La situation matrimoniale garde son étiquette d'origine, enrichie des deux
* nouvelles modalités. Le nom de l'étiquette est récupéré pour rester portable.
local matlbl : value label matrimoniale
if "`matlbl'" == "" {
    label define lbl_matrimoniale 0 "Non applicable (moins de 12 ans)" 9 "Manquant", replace
    label values matrimoniale lbl_matrimoniale
}
else {
    label define `matlbl' 0 "Non applicable (moins de 12 ans)" 9 "Manquant", modify
}

label variable id_grappe      "Grappe"
label variable id_menage      "Numéro de ménage"
label variable id_ordre       "Numéro d'ordre"
label variable id_men         "Identifiant ménage"
label variable poids          "Poids de sondage"
label variable taille_menage  "Taille du ménage"
label variable sexe           "Sexe"
label variable age            "Âge (années)"
label variable groupe_age     "Groupe d'âge"
label variable lien_cm        "Lien de parenté avec le CM (détaillé)"
label variable lien_cm_grp    "Lien de parenté avec le CM (regroupé)"
label variable matrimoniale   "Situation matrimoniale"
label variable niveau_etudes  "Niveau d'études consolidé"
label variable branche_etudes "Branche d'études"
label variable region         "Région"
label variable departement    "Département"
label variable milieu         "Milieu de résidence"
label variable milieu_etendu  "Strate de résidence"
label variable flag_sexe_incoherent        "Désaccord sexe roster vs emploi"
label variable flag_age_aberrant           "Âge aberrant neutralisé"
label variable flag_matrimoniale_manquant  "Situation matrimoniale manquante (12 ans et plus)"

*------------------------------------------------------------------------------*
* Contrôles de cohérence. Quelques vérifications simples veillent sur le bloc
* démo/géo et alimentent le fichier QAQC global sans s'y substituer. Le résultat
* part dans un petit fichier lisible.
*------------------------------------------------------------------------------*
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
local q_sexe = r(N)
quietly count if missing(age)
local q_age = r(N)
quietly count if missing(region)
local q_reg = r(N)
quietly count if missing(milieu)
local q_mil = r(N)
quietly count if missing(lien_cm)
local q_lien = r(N)
quietly count if flag_sexe_incoherent == 1
local q_des = r(N)

file open qc using "$DOSSIER_OUT/qc_demo_geo.csv", write replace
file write qc "controle,nombre,detail" _n
file write qc "menages avec un nombre de CM different de 1," (`qc1') ",doit valoir 0" _n
file write qc "CM de moins de 12 ans," (`qc2') ",a verifier" _n
file write qc "personnes mariees de moins de 12 ans," (`qc3') ",doit valoir 0" _n
file write qc "niveau superieur declare avant 18 ans," (`qc4') ",a verifier" _n
file write qc "manquants sur sexe," (`q_sexe') ",variable attendue complete" _n
file write qc "manquants sur age," (`q_age') ",variable attendue complete" _n
file write qc "manquants sur region," (`q_reg') ",variable attendue complete" _n
file write qc "manquants sur milieu," (`q_mil') ",variable attendue complete" _n
file write qc "manquants sur lien_cm," (`q_lien') ",variable attendue complete" _n
file write qc "desaccords sexe roster vs emploi," (`q_des') ",roster conserve comme reference" _n
file close qc

*------------------------------------------------------------------------------*
* Estimations primaires. Quelques parts pondérées offrent un premier regard sur
* la qualité, une fois le traitement fait. Les distributions devraient rester
* plausibles.
*------------------------------------------------------------------------------*
tempvar fem u15 o65 urb mar noedu
gen `fem'   = (sexe == 2)
gen `u15'   = (age < 15  & !missing(age))
gen `o65'   = (age >= 65 & !missing(age))
gen `urb'   = (milieu == 1)
gen `mar'   = inlist(matrimoniale, 2, 3)
gen `noedu' = (niveau_etudes == 1)

quietly summarize `fem'   [aw = poids], meanonly
local e_fem = r(mean) * 100
quietly summarize `u15'   [aw = poids], meanonly
local e_u15 = r(mean) * 100
quietly summarize `o65'   [aw = poids], meanonly
local e_o65 = r(mean) * 100
quietly summarize `urb'   [aw = poids], meanonly
local e_urb = r(mean) * 100
quietly summarize `mar'   [aw = poids], meanonly
local e_mar = r(mean) * 100
quietly summarize `noedu' [aw = poids], meanonly
local e_noe = r(mean) * 100
quietly summarize age     [aw = poids], meanonly
local e_agem = r(mean)

file open est using "$DOSSIER_OUT/estimations_demo_geo.csv", write replace
file write est "indicateur,valeur" _n
file write est "Part de femmes (%)," %5.2f (`e_fem') _n
file write est "Part de moins de 15 ans (%)," %5.2f (`e_u15') _n
file write est "Part de 65 ans et plus (%)," %5.2f (`e_o65') _n
file write est "Part en milieu urbain (%)," %5.2f (`e_urb') _n
file write est "Part de maries 12 ans et plus (%)," %5.2f (`e_mar') _n
file write est "Part sans aucun niveau scolaire (%)," %5.2f (`e_noe') _n
file write est "Age moyen (ans)," %5.1f (`e_agem') _n
file close est

*------------------------------------------------------------------------------*
* Table finale. Seules les variables du bloc démo/géo restent, dans un ordre
* lisible, puis la table part sur le disque.
*------------------------------------------------------------------------------*
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

display as text "{hline 64}"
display as text "Table individus écrite : $DOSSIER_OUT/individus_demo_geo.dta (" _N " lignes)"
display as text "Contrôles       -> $DOSSIER_OUT/qc_demo_geo.csv"
display as text "Estimations     -> $DOSSIER_OUT/estimations_demo_geo.csv"
display as text "Journal         -> $DOSSIER_OUT/journal_demo_geo.log"
display as text "Terminé."

capture log close

*==============================================================================*
* Fin du module.
*==============================================================================*
