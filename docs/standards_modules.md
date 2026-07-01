# Standard commun aux modules thematiques (a lire avant de livrer)

Ce document recapitule ce que les deux modules deja livres (demographie/
geographie - Awa, emploi principal - Aissatou) ont en commun, pour que le
prochain module (emploi secondaire, chomage, menages) reste au meme niveau.
Rien n'est obligatoire au sens strict du sujet du prof, mais s'ecarter de ces
points sans raison rend le rendu final heterogene entre les blocs.

## Ce que chaque module produit aujourd'hui

| Element | Fichier | Role |
|---|---|---|
| Script de traitement | `03_<bloc>.py` (et `.do` si une version Stata existe) | Coeur du module, seul le bloc CONFIG en tete est a adapter par pays |
| Journal d'execution | `output/SEN/journal_<bloc>.log` | Trace horodatee, console + fichier |
| Validation des colonnes | fonction `valider_colonnes()` dans le script | Verifie en amont que le fichier pays contient les variables attendues, message clair sinon |
| Table de sortie | `output/SEN/<bloc>.dta` | Cle sur `id_grappe`/`id_menage`/`id_ordre`/`id_men`, valeurs codees numeriquement + libellees (jamais de texte brut dans les colonnes) |
| Controles de cohererence + estimations ponderees | `qc_<bloc>.csv`, `estimations_<bloc>.csv` | Alimentent le QAQC global (Papa) |
| Codebook | `codebook_<bloc>.csv` | Une ligne par variable/modalite, effectif et part ponderee |
| Tests automatiques | `tests_<bloc>.py` | Invariants durs (doivent tenir) et souples (a surveiller), code de sortie 1 si echec dur |
| Dictionnaire de variables propre au module | `docs/dictionnaire_variables_<bloc>.csv` | Ne pas modifier le `docs/dictionnaire_variables.csv` partage directement - en creer un a part, verifie |
| Note methodologique | `docs/note_<bloc>.md` | Perimetre, corrections par rapport au dictionnaire initial, definitions officielles utilisees, traitement des manquants, limites connues |

## Points d'attention particuliers pour la suite (emploi secondaire, chomage, menages)

1. **Le dictionnaire de variables central (`docs/dictionnaire_variables.csv`) n'est pas fiable tel quel.** Sur le bloc emploi principal, 5 des 8 variables listees etaient en realite mal identifiees (verifie sur les metadonnees du fichier et le questionnaire officiel). Les lignes concernant les variables `AS` (emploi secondaire) sont deja marquees "a verifier" dans ce fichier - ce n'est pas une precaution excessive, c'est tres probablement necessaire. Ne pas coder sur la seule foi de ce fichier : verifier chaque variable sur les metadonnees `.dta` (labels, modalites) et si besoin sur `docs/QST_QUESTIONNAIRE VOLET EMPLOI_ERI-ESI 28122016.docx` avant de commencer a coder.

2. **Choisir un langage et le dire au groupe, plutot que de dupliquer.** Deux modules existent aujourd'hui en Python et en Stata en parallele (demographie/geographie, et bientot emploi principal). Ce n'est pas interdit, mais ca cree un risque reel de divergence entre les deux versions si elles ne sont pas maintenues ensemble a chaque changement. Si un nouveau module est fait dans un seul langage, le signaler clairement plutot que de laisser deviner lequel est "the source of truth" pour l'assemblage final.

3. **Verifier la configuration git (`git config user.name` / `user.email`) avant de committer.** Plusieurs commits du projet portent l'auteur "unknown" au lieu du vrai nom, ce qui empeche l'attribution correcte de la contribution individuelle.

4. **Le poids a utiliser depend du niveau d'analyse.** Il existe deux poids distincts dans les donnees : `hhweight` (poids menage) et `weightemploy` (poids individuel emploi) - ce dernier n'apparaissait meme pas dans le dictionnaire de variables central. Verifier lequel est pertinent avant de calculer des estimations ponderees.

5. **Distinguer manquant structurel et manquant reel des le depart.** Une grande partie du "manquant" dans ce type d'enquete correspond a des sous-populations hors champ (filtres en cascade du questionnaire), pas a de la non-reponse. Confondre les deux fausse a la fois le nettoyage et les controles de coherence.
