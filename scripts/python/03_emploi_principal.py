"""
ERI-ESI : module Emploi principal (Personne 3)
====================================================================

Role dans le pipeline
---------------------
Ce module prend en entree la base individuelle fusionnee produite en amont
(01_fusion.do, Personne 1) et produit un bloc de variables sur l'emploi
principal au niveau individu.

Perimetre couvert (cf. note travail a faire du groupe) :
  - Statut/situation d'activite, raison d'inactivite
  - Statut dans l'emploi principal, type salarie/independant
  - Secteur/branche d'activite (ISIC Rev.4)
  - Revenu de l'emploi principal
  - Heures de travail de l'emploi principal
  - Formalite de l'emploi et de l'unite (deux indicateurs distincts)

Correction par rapport au dictionnaire initial (docs/dictionnaire_variables.csv)
---------------------------------------------------------------------------
Une inspection directe des metadonnees du fichier et du questionnaire
(docs/QST_QUESTIONNAIRE VOLET EMPLOI_ERI-ESI 28122016.docx) a montre que
plusieurs variables du dictionnaire initial etaient mal identifiees :
  - AP6A n'est pas "heures de travail" mais "regime fiscal" (bloc formalite
    de l'unite)
  - AP7 n'est pas "formalite" mais "lieu de travail"
  - AP8A1 n'est pas "revenu" mais "anciennete dans l'emploi" (mois)
  - AP4 n'est pas la branche ISIC mais le secteur institutionnel
  - SE9 n'est pas "raison d'inactivite" mais "disponibilite" (SE11 est la
    vraie raison d'inactivite)
Le detail des corrections est documente dans docs/note_emploi_principal.md
et docs/dictionnaire_variables_emploi_principal.csv.

Definitions officielles utilisees (rapport final ANSD, chapitre 1.5)
---------------------------------------------------------------------------
  - Formalite de l'unite : non-enregistrement + non-tenue de comptabilite
    formelle + absence de production marchande (AP6a, AP6d, AP6e)
  - Formalite de l'emploi : absence d'au moins un des trois avantages
    (cotisations de protection sociale, conges maladie remunere, conges
    annuels payes ou compensation) -> AP16_21, AP16_23, AP16_22

Sortie : une table emploi_principal (.dta) qui alimente l'assemblage final
(Personne 1) et le fichier QAQC global.

Conception scalable
--------------------
Comme pour le module demographie/geographie (Personne 2), seul le
dictionnaire CONFIG ci-dessous est a adapter pour changer de pays (chemins,
correspondance des noms de variables). La logique de recodage reste
inchangee. Les libelles des modalites sont lus directement dans les
metadonnees du fichier .dta.

Auteure : Aissatou Gueye
"""

import os
import sys
import numpy as np
import pandas as pd
import pyreadstat

# Racine du depot (deux niveaux au dessus de scripts/python/)
RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ----------------------------------------------------------------------------
# CONFIGURATION (seul bloc a adapter pour changer de pays)
# ----------------------------------------------------------------------------

CONFIG = {
    "pays": "SEN",
    "vague": "2017",

    "fichier_base": "base_individus_emploi_fusionnee.dta",
    # Plusieurs emplacements candidats : la structure locale ne suit pas
    # toujours exactement input/<PAYS>/ (cf. config.do). On cherche aux
    # emplacements les plus probables, output prioritaire sur input, comme
    # dans le module de la Personne 2.
    "dossiers_candidats": [
        os.path.join(RACINE, "output", "SEN"),
        os.path.join(RACINE, "output"),
        os.path.join(RACINE, "input", "SEN"),
        os.path.join(RACINE, "input"),
    ],
    "dossier_output": os.path.join(RACINE, "output", "SEN"),

    # Correspondance variables conceptuelles -> noms reels dans le fichier
    # pays, corrigee par verification directe (metadonnees + questionnaire).
    "vars": {
        # identifiants
        "id_grappe": "hh1",
        "id_menage": "hh2",
        "id_ordre": "m1",
        "poids_emploi": "weightemploy",

        # situation d'activite
        "sitac": "sitac",
        "raison_inactivite": "SE11",

        # statut emploi principal
        "statut_emploi": "AP3",

        # branche d'activite (deja agregee en 21 sections ISIC Rev.4)
        "branche": "AP2_Niv1",

        # heures de travail (semaine de reference, confirme questionnaire AP10c)
        "heures_semaine": "AP10C",
        "jours_semaine": "AP10B",
        "heure_debut_h": "AP18A_H",
        "heure_debut_m": "AP18A_M",
        "heure_fin_h": "AP18B_H",
        "heure_fin_m": "AP18B_M",

        # revenu (routage AP13a confirme par questionnaire)
        "revenu_mode": "AP13A",
        "revenu_montant": "AP13B",
        "revenu_tranche": "AP13C",

        # formalite de l'unite (definition officielle ANSD, chap. 1.5)
        "regime_fiscal": "AP6A",
        "comptabilite_formelle": "AP6D",
        "activite_marchande": "AP6E",

        # formalite de l'emploi (definition officielle ANSD, chap. 1.5)
        "avantage_protection_sociale": "AP16_21A",
        "avantage_conges_payes": "AP16_22A",
        "avantage_conges_maladie": "AP16_23A",
    },

    # Bornes de plausibilite (parametrables)
    "heures_semaine_max": 98,   # au dela : aberrant (14h/jour x 7)
    "revenu_mensuel_min": 1000,       # FCFA/mois, en dessous : suspect
    "revenu_mensuel_max": 5000000,    # FCFA/mois, au dela : suspect
}


# ----------------------------------------------------------------------------
# Utilitaires
# ----------------------------------------------------------------------------

def localiser_base(cfg):
    """Retourne le chemin de la base fusionnee, en cherchant parmi plusieurs
    emplacements candidats (la structure locale peut differer de
    input/<PAYS>/ tel que defini dans config.do)."""
    for dossier in cfg["dossiers_candidats"]:
        chemin = os.path.join(dossier, cfg["fichier_base"])
        if os.path.exists(chemin):
            return chemin
    emplacements = "\n".join(cfg["dossiers_candidats"])
    raise FileNotFoundError(
        f"Base fusionnee '{cfg['fichier_base']}' introuvable. Emplacements "
        f"verifies :\n{emplacements}\n(livrable de la Personne 1)."
    )


def charger_base(cfg):
    """Charge uniquement les colonnes utiles au bloc emploi principal et
    leurs metadonnees."""
    v = cfg["vars"]
    colonnes = list(v.values())

    chemin = localiser_base(cfg)
    df, meta = pyreadstat.read_dta(chemin, usecols=colonnes)
    print(f"  base chargee : {df.shape[0]} lignes, {df.shape[1]} colonnes")
    print(f"  source : {chemin}")
    return df, meta


def libelles_valeurs(meta, nom_var):
    """Recupere le dictionnaire valeur -> libelle d'une variable depuis les
    metadonnees."""
    set_lbl = meta.variable_to_label.get(nom_var)
    if set_lbl and set_lbl in meta.value_labels:
        return dict(meta.value_labels[set_lbl])
    return {}


# ----------------------------------------------------------------------------
# Etapes de nettoyage et de recodage
# ----------------------------------------------------------------------------

def recoder_situation_activite(df, cfg, meta):
    """
    Situation d'activite (sitac) : deja calculee par l'ANSD, reprise telle
    quelle. On ajoute un regroupement simplifie en 4 postes, utile pour les
    comparaisons inter-pays : 1 actif occupe, 2 chomeur BIT, 3 main d'oeuvre
    potentielle (regroupe les sous-codes 31/32/33), 4 inactif hors main
    d'oeuvre.

    Raison d'inactivite (SE11) : le dictionnaire initial indiquait SE9, qui
    est en realite la disponibilite (cf. note_emploi_principal.md). La vraie
    raison d'inactivite est SE11, reprise ici, structurellement renseignee
    seulement chez les inactifs (sitac==4).
    """
    v = cfg["vars"]
    df["situation_activite"] = df[v["sitac"]]

    correspondance_groupe = {1: 1, 2: 2, 31: 3, 32: 3, 33: 3, 4: 4}
    df["situation_activite_grp"] = df["situation_activite"].map(correspondance_groupe)

    df["raison_inactivite"] = df[v["raison_inactivite"]]

    n_total = len(df)
    n_manquant_structurel = int(df["situation_activite"].isna().sum())
    print(f"  situation d'activite : {n_manquant_structurel}/{n_total} manquant "
          f"structurel (moins de 15 ans)")
    print("  repartition (regroupe) :")
    print(df["situation_activite_grp"].value_counts(dropna=False).sort_index().to_string())

    inactifs = df["situation_activite"] == 4
    n_inactifs = int(inactifs.sum())
    n_raison_renseignee = int((inactifs & df["raison_inactivite"].notna()).sum())
    n_raison_hors_inactif = int((~inactifs & df["raison_inactivite"].notna()).sum())
    print(f"  raison d'inactivite : renseignee pour {n_raison_renseignee}/{n_inactifs} "
          f"inactifs ({100 * n_raison_renseignee / n_inactifs:.1f}%)")
    if n_raison_hors_inactif > 0:
        print(f"  ATTENTION : raison d'inactivite renseignee pour {n_raison_hors_inactif} "
              f"individus non-inactifs (a verifier, cf. main d'oeuvre potentielle)")

    return df


# ----------------------------------------------------------------------------
# Orchestration (etapes de recodage restantes ajoutees dans les prochains
# commits : statut emploi, branche, heures, revenu, formalite)
# ----------------------------------------------------------------------------

def main():
    cfg = CONFIG
    print(f"Module emploi principal - pays {cfg['pays']} {cfg['vague']}")
    print("-" * 64)

    df, meta = charger_base(cfg)

    v = cfg["vars"]
    df["id_men"] = (df[v["id_grappe"]].astype("Int64").astype(str) + "_"
                    + df[v["id_menage"]].astype("Int64").astype(str))

    df = recoder_situation_activite(df, cfg, meta)

    print("-" * 64)
    print("Etape situation d'activite OK. Suite a venir dans les prochains commits.")


if __name__ == "__main__":
    sys.exit(main())
