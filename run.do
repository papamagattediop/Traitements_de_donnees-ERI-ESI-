*==============================================================================*
*  ERI-ESI — Point d'entrée unique du pipeline
*  do run.do
*==============================================================================*

clear all
set more off

display as text "Pipeline ERI-ESI 2017 -- debut"
display as text "Repertoire de travail : " c(pwd)

local debut = clock("$S_DATE $S_TIME", "DMYhms")

do scripts/stata/01_fusion.do
do scripts/stata/03_demographie_geo.do
do scripts/stata/03_emploi_principal.do
do scripts/stata/04_emploi_secondaire.do
do scripts/stata/05_menages.do
do scripts/stata/06_consolidation.do

local fin  = clock("$S_DATE $S_TIME", "DMYhms")
local duree = round((`fin' - `debut') / 1000)

display as text "Pipeline termine en `duree' secondes."
display as text "Tables produites dans output/SEN/ :"
display as text "  individus_consolide.dta"
display as text "  menages_consolide.dta"
