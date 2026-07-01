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

    # Points milieu des tranches de revenu (AP13c), en milliers de FCFA.
    # La derniere tranche (>=3000) est ouverte : on retient la borne basse,
    # ce qui sous-estime volontairement plutot que de deviner un plafond.
    "tranches_revenu_milliers": {
        1: 17.5, 2: 67.5, 3: 125, 4: 175, 5: 225, 6: 275, 7: 325, 8: 375,
        9: 425, 10: 475, 11: 525, 12: 575, 13: 625, 14: 675, 15: 725,
        16: 775, 17: 825, 18: 875, 19: 950, 20: 1125, 21: 1375, 22: 1750,
        23: 2250, 24: 2750, 25: 3000,
    },
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


def recoder_statut_emploi(df, cfg, meta):
    """
    Statut dans l'emploi principal (AP3, categorie socioprofessionnelle),
    confirme correct dans le dictionnaire initial. On en deduit le type
    d'emploi salarie/independant en suivant le regroupement fait par le
    questionnaire lui-meme (bloc "Salarie" vs bloc "Employeur/Independant") :
      - 1 a 6 et 10 (cadre superieur a manoeuvre, apprenti paye ou non) -> salarie
      - 7, 8, 9 (employeur, compte propre, aide familial) -> independant
    Manquant structurel = non occupe (memes 91676 lignes que les autres
    variables du bloc AP).
    """
    v = cfg["vars"]
    df["statut_emploi"] = df[v["statut_emploi"]]

    correspondance_type = {
        1: "salarie", 2: "salarie", 3: "salarie", 4: "salarie",
        5: "salarie", 6: "salarie", 10: "salarie",
        7: "independant", 8: "independant", 9: "independant",
    }
    df["type_emploi"] = df["statut_emploi"].map(correspondance_type)

    n_total = len(df)
    n_manquant = int(df["statut_emploi"].isna().sum())
    print(f"  statut emploi : {n_manquant}/{n_total} manquant structurel (non occupe)")
    print("  repartition type d'emploi (parmi occupes) :")
    print(df["type_emploi"].value_counts(dropna=False, normalize=True).mul(100).round(1).to_string())

    return df


def recoder_branche(df, cfg, meta):
    """
    Branche/secteur d'activite (AP2_Niv1) : le dictionnaire initial pointait
    a tort vers AP4 (secteur institutionnel, concept different). AP2_Niv1
    est confirme par le questionnaire et par ses modalites, qui sont deja
    les 21 sections ISIC Rev.4 (Agriculture, Industries extractives,
    Fabrication, ..., Organisations extraterritoriales) : rien a agreger,
    contrairement a ce qui etait envisage avant verification.

    On ajoute egalement un regroupement en 4 grandes familles
    (Primaire/Industrie/Commerce/Service), identique a celui utilise dans
    le rapport final ANSD pour ses propres tableaux de resultats - utile
    pour comparer nos estimations aux chiffres deja publies.
    """
    v = cfg["vars"]
    df["secteur_isic_principal"] = df[v["branche"]]

    # Regroupement Primaire/Industrie/Commerce/Service, calque sur celui du
    # rapport final ANSD (tableau 5.18) :
    #   Primaire  : Agriculture/sylviculture/peche (1)
    #   Industrie : extractives, fabrication, electricite/gaz, eau/dechets,
    #               construction (2,3,4,5,6)
    #   Commerce  : commerce (7)
    #   Service   : tout le reste (transports, hebergement, information,
    #               finance, immobilier, services divers, administration,
    #               enseignement, sante, arts, menages, extraterritoriales)
    correspondance_4cat = {1: "Primaire"}
    correspondance_4cat.update({c: "Industrie" for c in [2, 3, 4, 5, 6]})
    correspondance_4cat[7] = "Commerce"
    correspondance_4cat.update({c: "Service" for c in range(8, 22)})
    df["secteur_isic_principal_4cat"] = df["secteur_isic_principal"].map(correspondance_4cat)

    n_total = len(df)
    n_manquant = int(df["secteur_isic_principal"].isna().sum())
    print(f"  branche d'activite : {n_manquant}/{n_total} manquant structurel (non occupe)")
    print("  repartition 4 familles (parmi occupes) :")
    presents = df["secteur_isic_principal_4cat"].dropna()
    print(presents.value_counts(normalize=True).mul(100).round(1).to_string())

    return df


def recoder_heures_travail(df, cfg, meta):
    """
    Heures de travail (AP10C), confirmees par le questionnaire comme etant
    un nombre d'heures par semaine ("au cours des 7 derniers jours, ou
    habituellement par semaine"). Le dictionnaire initial pointait a tort
    vers AP6A (regime fiscal).

    Nettoyage : les valeurs au-dela de la borne de plausibilite (98h/semaine,
    soit 14h/jour x 7) sont neutralisees et signalees plutot que gardees
    telles quelles - on a observe un maximum brut de 224h/semaine, ce qui est
    physiquement impossible.

    Controle de coherence : une duree quotidienne est recalculee a partir des
    heures de debut/fin de journee (AP18A, AP18B, gestion du passage minuit),
    multipliee par le nombre de jours travailles dans la semaine (AP10B), et
    comparee a la valeur declaree (AP10C). Un ecart important est signale
    sans jamais corriger automatiquement l'une par l'autre.
    """
    v = cfg["vars"]
    heures = df[v["heures_semaine"]].copy()

    aberrant = heures > cfg["heures_semaine_max"]
    df["flag_heures_aberrantes"] = aberrant.fillna(False).astype("int8")
    heures = heures.mask(aberrant, np.nan)
    df["heures_semaine_principal"] = heures

    debut = df[v["heure_debut_h"]] + df[v["heure_debut_m"]] / 60
    fin = df[v["heure_fin_h"]] + df[v["heure_fin_m"]] / 60
    duree_quotidienne = fin - debut
    duree_quotidienne = duree_quotidienne.where(duree_quotidienne >= 0, duree_quotidienne + 24)

    heures_calculees = duree_quotidienne * df[v["jours_semaine"]]
    ecart = (df["heures_semaine_principal"] - heures_calculees).abs()
    df["flag_ecart_heures"] = (ecart > 10).fillna(False).astype("int8")

    n_total = len(df)
    n_manquant = int(df["heures_semaine_principal"].isna().sum())
    print(f"  heures de travail : {n_manquant}/{n_total} manquant (structurel + "
          f"{int(aberrant.sum())} aberrant(s) neutralise(s))")
    print("  statistiques (parmi occupes, apres nettoyage) :")
    print(df["heures_semaine_principal"].dropna().describe().to_string())
    print(f"  ecart > 10h avec calcul debut/fin x jours : "
          f"{int(df['flag_ecart_heures'].sum())} cas signales")

    return df


def recoder_revenu(df, cfg, meta):
    """
    Revenu de l'emploi principal, consolide selon le routage AP13a confirme
    par le questionnaire (le dictionnaire initial pointait a tort vers
    AP8A1, qui est l'anciennete dans l'emploi) :
      - AP13a=1 : AP13b est deja un montant mensuel direct
      - AP13a=2 : AP13b est un montant annuel direct -> divise par 12
      - AP13a=3 : AP13c est une tranche mensuelle -> point milieu de la tranche
      - AP13a=4 : AP13c est une tranche annuelle -> point milieu / 12
      - AP13a=5 ou 6 (refus / ne sait pas) : revenu non renseigne, signale
        par un flag dedie, jamais impute (cf. echange sur l'imputation :
        ce n'est ni un manquant structurel ni un cas a deviner)

    Nettoyage : apres consolidation en FCFA/mois, les valeurs hors bornes de
    plausibilite sont neutralisees et signalees (des valeurs observees comme
    "2 FCFA/mois" ou "10 milliards FCFA/mois" ne peuvent pas etre de vrais
    montants).
    """
    v = cfg["vars"]
    mode = df[v["revenu_mode"]]
    montant_direct = df[v["revenu_montant"]]
    tranche = df[v["revenu_tranche"]].map(cfg["tranches_revenu_milliers"]) * 1000

    revenu = pd.Series(np.nan, index=df.index, dtype="float")
    revenu = revenu.where(mode != 1, montant_direct)
    revenu = revenu.where(mode != 2, montant_direct / 12)
    revenu = revenu.where(mode != 3, tranche)
    revenu = revenu.where(mode != 4, tranche / 12)

    df["flag_revenu_non_renseigne"] = mode.isin([5, 6]).astype("int8")

    aberrant = (revenu < cfg["revenu_mensuel_min"]) | (revenu > cfg["revenu_mensuel_max"])
    df["flag_revenu_aberrant"] = aberrant.fillna(False).astype("int8")
    revenu = revenu.mask(aberrant, np.nan)

    df["revenu_principal_mensuel_fcfa"] = revenu
    df["revenu_source"] = mode.map({
        1: "direct_mensuel", 2: "direct_annuel_convertit",
        3: "tranche_mensuelle", 4: "tranche_annuelle_convertie",
        5: "refuse", 6: "ne_sait_pas",
    })

    n_total = len(df)
    n_manquant = int(df["revenu_principal_mensuel_fcfa"].isna().sum())
    print(f"  revenu : {n_manquant}/{n_total} manquant (structurel + refus/NSP + "
          f"{int(aberrant.sum())} aberrant(s) neutralise(s))")
    print("  repartition source du revenu (parmi occupes) :")
    print(df["revenu_source"].value_counts(dropna=False).to_string())
    print("  statistiques revenu mensuel consolide (FCFA, apres nettoyage) :")
    print(df["revenu_principal_mensuel_fcfa"].dropna().describe().to_string())
    print("  reference rapport ANSD : moyenne Senegal 125 485 FCFA/mois "
          "(non pondere ici, a comparer une fois l'estimation ponderee faite)")

    return df


def recoder_formalite(df, cfg, meta):
    """
    Deux indicateurs de formalite distincts, definis officiellement dans le
    rapport final ANSD (chapitre 1.5) - pas un indice compose invente :

    1) Formalite de l'UNITE (secteur informel au sens ANSD/BIT) : une unite
       marchande (AP6E) est informelle si au moins un des deux criteres
       suivants n'est pas rempli : enregistrement fiscal (AP6A) et tenue
       d'une comptabilite formelle (AP6D). Les unites non marchandes sont
       hors champ de cette classification (non applicable), pas "formelles"
       par defaut.
       Codes reels verifies dans les metadonnees (different de l'ordre du
       questionnaire papier) : AP6A - {1,2,4}=regime fiscal donc enregistre,
       3=ne paie pas d'impot ; AP6D - 2=comptabilite formelle OHADA, {1,3}=non.

    2) Formalite de l'EMPLOI : un salarie est en emploi informel si au moins
       un des trois avantages suivants lui est refuse : cotisations de
       protection sociale payees par l'employeur (AP16_21A), conges annuels
       payes (AP16_22A), conges maladie remuneres (AP16_23A). Ce bloc n'est
       administre qu'aux salaries (structurellement absent pour les
       independants) : formalite_emploi reste non applicable pour eux.
    """
    v = cfg["vars"]

    marchande = df[v["activite_marchande"]].isin([1, 2])
    non_enregistre = df[v["regime_fiscal"]] == 3
    non_comptabilite = df[v["comptabilite_formelle"]].isin([1, 3])

    formalite_unite = pd.Series(np.nan, index=df.index, dtype="object")
    informel_unite = marchande & (non_enregistre | non_comptabilite)
    formel_unite = marchande & ~(non_enregistre | non_comptabilite)
    formalite_unite = formalite_unite.mask(informel_unite, "informel")
    formalite_unite = formalite_unite.mask(formel_unite, "formel")
    df["formalite_unite"] = formalite_unite

    a_protection = df[v["avantage_protection_sociale"]] == 1
    a_conges_payes = df[v["avantage_conges_payes"]] == 1
    a_conges_maladie = df[v["avantage_conges_maladie"]] == 1
    trois_criteres_renseignes = (df[v["avantage_protection_sociale"]].notna()
                                 & df[v["avantage_conges_payes"]].notna()
                                 & df[v["avantage_conges_maladie"]].notna())

    formalite_emploi = pd.Series(np.nan, index=df.index, dtype="object")
    informel_emploi = trois_criteres_renseignes & ~(a_protection & a_conges_payes & a_conges_maladie)
    formel_emploi = trois_criteres_renseignes & (a_protection & a_conges_payes & a_conges_maladie)
    formalite_emploi = formalite_emploi.mask(informel_emploi, "informel")
    formalite_emploi = formalite_emploi.mask(formel_emploi, "formel")
    df["formalite_emploi"] = formalite_emploi

    print("  formalite de l'unite (parmi unites concernees) :")
    print(df["formalite_unite"].value_counts(dropna=False).to_string())
    print("  formalite de l'emploi (parmi salaries avec bloc avantages renseigne) :")
    print(df["formalite_emploi"].value_counts(dropna=False).to_string())

    return df


# ----------------------------------------------------------------------------
# Orchestration : toutes les etapes de recodage thematique sont posees.
# Reste a venir : assemblage de la sortie, controles de coherence globaux,
# estimations ponderees, ecriture des fichiers.
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
    df = recoder_statut_emploi(df, cfg, meta)
    df = recoder_branche(df, cfg, meta)
    df = recoder_heures_travail(df, cfg, meta)
    df = recoder_revenu(df, cfg, meta)
    df = recoder_formalite(df, cfg, meta)

    print("-" * 64)
    print("Tous les blocs thematiques sont poses. Suite : assemblage et QAQC.")


if __name__ == "__main__":
    sys.exit(main())
