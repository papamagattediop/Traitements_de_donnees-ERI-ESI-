*==============================================================================*
*  ERI-ESI : table ménages consolidée
*
*  Ce module construit la table ménages à partir de la table individus
*  démographie/géographie (output du module 03). Le chef de ménage (lien_cm==1)
*  fournit les variables démographiques. La géographie et les caractéristiques
*  du ménage (taille, poids) sont agrégées au niveau ménage.
*
*  Note : les variables de dépenses, d'actifs et d'habitat ne figurent pas
*  dans les fichiers fournis pour le Sénégal (volet emploi uniquement).
*  La table ménages se limite donc aux variables disponibles. Si un pays
*  fournit un fichier ménage séparé, il suffit de le fusionner ici.
*
*  Execution depuis la racine du dépôt :
*      do scripts/stata/05_menages.do
*==============================================================================*

clear all
set more off

*------------------------------------------------------------------------------*
* Configuration du pays actif.
*------------------------------------------------------------------------------*
global PAYS         "SEN"
global VAGUE        "2017"
global DOSSIER_OUT  "output/SEN"

display as text "Module table ménages - pays $PAYS $VAGUE"
display as text "{hline 64}"

capture log close _all
log using "$DOSSIER_OUT/journal_menages.log", replace text

*------------------------------------------------------------------------------*
* La table ménages se construit à partir de individus_demo_geo.dta (produit
* par le module 03). Le chef de ménage est identifié par lien_cm == 1.
*------------------------------------------------------------------------------*
use "$DOSSIER_OUT/individus_demo_geo.dta", clear
display as text "  individus_demo_geo.dta chargé : " _N " lignes"

*------------------------------------------------------------------------------*
* Vérification : chaque ménage doit avoir exactement un CM.
*------------------------------------------------------------------------------*
bysort id_men: egen nb_cm = total(lien_cm == 1)
quietly count if nb_cm != 1
local qc_cm = r(N)
if `qc_cm' > 0 {
    display as error "ATTENTION : `qc_cm' individus dans des ménages sans CM unique."
}
drop nb_cm

*------------------------------------------------------------------------------*
* Bloc CM : démographie du chef de ménage.
* On extrait la ligne du CM pour chaque ménage, en gardant les variables
* démographiques qui le caractérisent.
*------------------------------------------------------------------------------*
preserve
keep if lien_cm == 1

keep id_grappe id_menage id_men ///
     sexe age groupe_age situation_matrimoniale_cm niveau_etudes ///
     branche_etudes region departement milieu milieu_etendu ///
     poids taille_menage

* Renommage pour signaler que ces variables décrivent le CM, pas l'individu.
rename sexe               sexe_cm
rename age                age_cm
rename groupe_age         groupe_age_cm
rename niveau_etudes      niveau_etudes_cm
rename branche_etudes     branche_etudes_cm

* La situation matrimoniale du CM vient du module démo (colonne matrimoniale).
capture rename matrimoniale situation_matrimoniale_cm
if _rc {
    gen byte situation_matrimoniale_cm = .
    display as text "  AVERTISSEMENT : variable matrimoniale absente, colonne vide créée."
}

label variable sexe_cm              "Sexe du CM"
label variable age_cm               "Âge du CM"
label variable groupe_age_cm        "Groupe d'âge du CM"
label variable niveau_etudes_cm     "Niveau d'études du CM"
label variable branche_etudes_cm    "Branche d'études du CM"
label variable situation_matrimoniale_cm "Situation matrimoniale du CM"
label variable region               "Région du ménage"
label variable milieu               "Milieu de résidence du ménage"
label variable milieu_etendu        "Strate de résidence du ménage"
label variable departement          "Département du ménage"
label variable taille_menage        "Taille du ménage"
label variable poids                "Poids du ménage"

tempfile cm_demo
save `cm_demo'
restore

*------------------------------------------------------------------------------*
* Bloc structure du ménage : composition par sexe, par groupe d'âge,
* nombre d'actifs de 15 ans et plus.
*------------------------------------------------------------------------------*
bysort id_men: gen nb_membres = _N

gen byte est_homme = (sexe == 1)
gen byte est_femme = (sexe == 2)
gen byte est_moins15 = (age < 15 & !missing(age))
gen byte est_15plus  = (age >= 15 & !missing(age))

bysort id_men: egen nb_hommes   = total(est_homme)
bysort id_men: egen nb_femmes   = total(est_femme)
bysort id_men: egen nb_moins15  = total(est_moins15)
bysort id_men: egen nb_15plus   = total(est_15plus)

gen byte ratio_dependance_calcule = (nb_moins15 / nb_membres * 100) if nb_membres > 0

* Une ligne par ménage suffit pour la table structure.
bysort id_men: keep if _n == 1

keep id_grappe id_menage id_men nb_membres nb_hommes nb_femmes nb_moins15 nb_15plus ratio_dependance_calcule

label variable nb_membres              "Nombre de membres du ménage"
label variable nb_hommes               "Nombre d'hommes dans le ménage"
label variable nb_femmes               "Nombre de femmes dans le ménage"
label variable nb_moins15              "Nombre de membres de moins de 15 ans"
label variable nb_15plus               "Nombre de membres de 15 ans et plus"
label variable ratio_dependance_calcule "Ratio de dépendance démographique (%)"

tempfile structure_men
save `structure_men'

*------------------------------------------------------------------------------*
* Assemblage de la table ménages : CM + structure.
*------------------------------------------------------------------------------*
use `cm_demo', clear
merge 1:1 id_grappe id_menage id_men using `structure_men', nogenerate

*------------------------------------------------------------------------------*
* Contrôles de cohérence.
*------------------------------------------------------------------------------*
quietly count if missing(sexe_cm)
local qc1 = r(N)
quietly count if missing(age_cm)
local qc2 = r(N)
quietly count if missing(region)
local qc3 = r(N)
quietly count if age_cm < 15 & !missing(age_cm)
local qc4 = r(N)
quietly count if taille_menage != nb_membres & !missing(nb_membres)
local qc5 = r(N)

file open qc using "$DOSSIER_OUT/qc_menages.csv", write replace
file write qc "controle,nombre,detail" _n
file write qc "menages sans CM identifie," (`qc_cm') ",doit valoir 0" _n
file write qc "manquants sur sexe_cm," (`qc1') ",variable attendue complete" _n
file write qc "manquants sur age_cm," (`qc2') ",variable attendue complete" _n
file write qc "manquants sur region," (`qc3') ",variable attendue complete" _n
file write qc "CM de moins de 15 ans," (`qc4') ",a verifier" _n
file write qc "taille_menage != nb_membres calcule," (`qc5') ",incoherence sur la taille du menage" _n
file close qc

*------------------------------------------------------------------------------*
* Estimations pondérées.
*------------------------------------------------------------------------------*
quietly summarize taille_menage [aw = poids], meanonly
local e_tail = r(mean)
quietly summarize (sexe_cm == 2) [aw = poids], meanonly
local e_fem = r(mean) * 100
quietly summarize age_cm [aw = poids], meanonly
local e_age = r(mean)
quietly summarize nb_moins15 [aw = poids], meanonly
local e_dep = r(mean)

file open est using "$DOSSIER_OUT/estimations_menages.csv", write replace
file write est "indicateur,valeur" _n
file write est "Taille moyenne du menage (personnes)," %5.2f (`e_tail') _n
file write est "Part des menages diriges par une femme (%)," %5.2f (`e_fem') _n
file write est "Age moyen du CM (ans)," %5.1f (`e_age') _n
file write est "Nombre moyen de membres de moins de 15 ans," %5.2f (`e_dep') _n
file close est

*------------------------------------------------------------------------------*
* Table finale.
*------------------------------------------------------------------------------*
order id_grappe id_menage id_men poids taille_menage ///
      sexe_cm age_cm groupe_age_cm situation_matrimoniale_cm ///
      niveau_etudes_cm branche_etudes_cm ///
      region departement milieu milieu_etendu ///
      nb_membres nb_hommes nb_femmes nb_moins15 nb_15plus ratio_dependance_calcule

compress
save "$DOSSIER_OUT/menages.dta", replace

display as text "{hline 64}"
display as text "Table ménages : $DOSSIER_OUT/menages.dta (" _N " ménages)"
display as text "Controles  -> $DOSSIER_OUT/qc_menages.csv"
display as text "Estimations -> $DOSSIER_OUT/estimations_menages.csv"
display as text "Journal     -> $DOSSIER_OUT/journal_menages.log"
display as text "Terminé."

capture log close
*==============================================================================*
