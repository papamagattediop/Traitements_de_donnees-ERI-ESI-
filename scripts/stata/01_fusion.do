* Etape 1 : fusion individus <-> emploi sur les cles de menage/individu.
* Produit la base de travail individuelle complete (avant derivation des
* variables thematiques par chaque membre du groupe).
*
* Usage : do 01_fusion.do

do "config.do"

use "${INPUT}/${FICHIER_INDIVIDUS}", clear

* harmonise les noms de cles cote individus sur les noms cote emploi
local n : word count ${CLES_INDIVIDUS}
forvalues i = 1/`n' {
    local cle_ind : word `i' of ${CLES_INDIVIDUS}
    local cle_emp : word `i' of ${CLES_EMPLOI}
    capture confirm variable `cle_emp'
    if _rc & "`cle_ind'" != "`cle_emp'" {
        rename `cle_ind' `cle_emp'
    }
}

merge 1:1 ${CLES_EMPLOI} using "${INPUT}/${FICHIER_EMPLOI}"

tab _merge
count if _merge != 3
local non_apparies = r(N)
if `non_apparies' > 0 {
    display as error "ATTENTION : `non_apparies' individus sans correspondance des deux cotes."
}

drop _merge

save "${OUTPUT}/base_individus_emploi_fusionnee.dta", replace

display "Base fusionnee ecrite dans : ${OUTPUT}/base_individus_emploi_fusionnee.dta"
