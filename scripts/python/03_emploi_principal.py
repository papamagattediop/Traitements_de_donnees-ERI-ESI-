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
        # age de reference (M4, bloc Personne 2) - utilise uniquement ici
        # pour reperer le travail des enfants (10-14 ans), pas reexporte
        # comme variable demographique (deja du ressort de la Personne 2)
        "age_reference": "M4",

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

        # sous-emploi lie a la duree du travail (definition officielle ANSD,
        # chap. 1.5). Ces variables ne sont pas dans le bloc SE malgre ce que
        # suggerait repartition.html, mais dans le bloc AP (heures) et R
        # (chomage, bloc nominalement suivi par la Personne 4 - utilisees ici
        # uniquement pour ce concept precis, a signaler pour eviter tout
        # doublon de travail).
        "raison_moins_40h": "AP11A",
        "disponible_travailler_plus": "R3",
    },

    # Bornes de plausibilite (parametrables)
    "heures_semaine_max": 98,   # au dela : aberrant (14h/jour x 7)
    "revenu_mensuel_min": 1000,       # FCFA/mois, en dessous : suspect
    "revenu_mensuel_max": 5000000,    # FCFA/mois, au dela : suspect
    "seuil_duree_legale_semaine": 40,  # heures/semaine, seuil du sous-emploi

    # Points milieu des tranches de revenu (AP13c), en milliers de FCFA.
    # La derniere tranche (>=3000) est ouverte : on retient la borne basse,
    # ce qui sous-estime volontairement plutot que de deviner un plafond.
    "tranches_revenu_milliers": {
        1: 17.5, 2: 67.5, 3: 125, 4: 175, 5: 225, 6: 275, 7: 325, 8: 375,
        9: 425, 10: 475, 11: 525, 12: 575, 13: 625, 14: 675, 15: 725,
        16: 775, 17: 825, 18: 875, 19: 950, 20: 1125, 21: 1375, 22: 1750,
        23: 2250, 24: 2750, 25: 3000,
    },

    # Libelles des variables categorielles construites par ce module (codes
    # numeriques, jamais de texte brut dans les colonnes de sortie - meme
    # convention que le module demographie/geographie)
    "labels_situation_activite_grp": {
        1: "Actif occupe", 2: "Chomeur BIT",
        3: "Main-d'oeuvre potentielle", 4: "Inactif (hors main d'oeuvre)",
    },
    "labels_type_emploi": {1: "Salarie", 2: "Independant"},
    "labels_secteur_4cat": {1: "Primaire", 2: "Industrie", 3: "Commerce", 4: "Service"},
    "labels_formalite": {1: "Formel", 2: "Informel"},
    "labels_oui_non": {1: "Oui", 2: "Non"},
    "labels_revenu_source": {
        1: "Direct mensuel", 2: "Direct annuel (converti)",
        3: "Tranche mensuelle", 4: "Tranche annuelle (convertie)",
        5: "Refuse de dire", 6: "Ne sait pas",
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

    Eligibilite au module emploi (eligible_module_emploi) : le questionnaire
    emploi est administre a partir de 10 ans, mais sitac (situation
    d'activite synthetique) n'est calcule par l'ANSD qu'a partir de 15 ans -
    d'ou un grand nombre de lignes structurellement vides sur tout le bloc
    au-dela des seuls "moins de 15 ans". Ce flag (base sur la presence du
    poids emploi, weightemploy) rend cette eligibilite explicite plutot que
    de laisser deviner pourquoi une ligne est entierement vide.
    """
    v = cfg["vars"]
    df["situation_activite"] = df[v["sitac"]]

    correspondance_groupe = {1: 1, 2: 2, 31: 3, 32: 3, 33: 3, 4: 4}
    df["situation_activite_grp"] = df["situation_activite"].map(correspondance_groupe)

    df["raison_inactivite"] = df[v["raison_inactivite"]]

    # code numerique + libelle (cfg["labels_oui_non"])
    df["eligible_module_emploi"] = df[v["poids_emploi"]].notna().map({True: 1, False: 2})

    n_total = len(df)
    n_manquant_structurel = int(df["situation_activite"].isna().sum())
    print(f"  situation d'activite : {n_manquant_structurel}/{n_total} manquant "
          f"structurel (moins de 15 ans)")
    print("  repartition (regroupe) :")
    print(df["situation_activite_grp"].value_counts(dropna=False).sort_index().to_string())
    n_eligibles = int((df["eligible_module_emploi"] == 1).sum())
    print(f"  eligibles au module emploi (10 ans et plus) : {n_eligibles}/{n_total}")

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

    Travail des enfants (flag_travail_enfant_10_14) : sitac n'etant calcule
    par l'ANSD qu'a partir de 15 ans, les 10-14 ans qui travaillent
    n'apparaissent jamais comme "occupes" (situation_activite==1) meme
    quand AP3 est bel et bien renseigne pour eux (932 cas verifies). Ce
    n'est pas une incoherence a corriger mais un phenomene reel a signaler
    explicitement plutot que de le laisser se fondre dans les donnees ou
    d'etre lu a tort comme une erreur.
    """
    v = cfg["vars"]
    df["statut_emploi"] = df[v["statut_emploi"]]

    # type_emploi code numerique + libelle (cf. cfg["labels_type_emploi"]) :
    # 1 = salarie (statut 1-6, 10), 2 = independant (statut 7-9)
    correspondance_type = {
        1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 10: 1,
        7: 2, 8: 2, 9: 2,
    }
    df["type_emploi"] = df["statut_emploi"].map(correspondance_type)

    enfant_10_14 = df[v["age_reference"]].between(10, 14)
    travail_enfant = enfant_10_14 & df["statut_emploi"].notna()
    df["flag_travail_enfant_10_14"] = travail_enfant.astype("int8")

    n_total = len(df)
    n_manquant = int(df["statut_emploi"].isna().sum())
    print(f"  statut emploi : {n_manquant}/{n_total} manquant structurel (non occupe)")
    print(f"  travail des enfants (10-14 ans avec statut emploi renseigne) : "
          f"{int(df['flag_travail_enfant_10_14'].sum())} cas")
    print("  repartition type d'emploi (parmi occupes) :")
    print(df["type_emploi"].map(cfg["labels_type_emploi"])
          .value_counts(dropna=False, normalize=True).mul(100).round(1).to_string())

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

    # Regroupement Primaire(1)/Industrie(2)/Commerce(3)/Service(4), calque
    # sur celui du rapport final ANSD (tableau 5.18) - code numerique +
    # libelle (cfg["labels_secteur_4cat"]) :
    #   Primaire  : Agriculture/sylviculture/peche (1)
    #   Industrie : extractives, fabrication, electricite/gaz, eau/dechets,
    #               construction (2,3,4,5,6)
    #   Commerce  : commerce (7)
    #   Service   : tout le reste (transports, hebergement, information,
    #               finance, immobilier, services divers, administration,
    #               enseignement, sante, arts, menages, extraterritoriales)
    correspondance_4cat = {1: 1}
    correspondance_4cat.update({c: 2 for c in [2, 3, 4, 5, 6]})
    correspondance_4cat[7] = 3
    correspondance_4cat.update({c: 4 for c in range(8, 22)})
    df["secteur_isic_principal_4cat"] = df["secteur_isic_principal"].map(correspondance_4cat)

    n_total = len(df)
    n_manquant = int(df["secteur_isic_principal"].isna().sum())
    print(f"  branche d'activite : {n_manquant}/{n_total} manquant structurel (non occupe)")
    print("  repartition 4 familles (parmi occupes) :")
    presents = df["secteur_isic_principal_4cat"].map(cfg["labels_secteur_4cat"]).dropna()
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


def recoder_sous_emploi(df, cfg, meta):
    """
    Sous-emploi lie a la duree du travail, definition officielle ANSD
    (chap. 1.5) : une personne en emploi qui remplit les trois criteres
    suivants - i) travaille involontairement moins que la duree legale
    (40h/semaine), ii) disponible pour travailler plus et/ou iii) a la
    recherche d'un travail supplementaire.

    Faute d'une variable directe pour le critere (iii) dans le perimetre
    inspecte, on retient (i) et (ii) uniquement - la definition officielle
    utilise "et/ou" entre (ii) et (iii), donc (ii) seul reste une
    application valide, documentee comme simplification.
      i)   heures_semaine_principal < seuil legal (40h)
      ii)  disponible pour travailler plus (R3 == 1)
      involontaire = raison economique (AP11A == 3, "Moins de travail du a
      la mauvaise conjoncture"), le proxy standard pour l'involontaire dans
      ce type d'enquete.
    """
    v = cfg["vars"]
    seuil = cfg["seuil_duree_legale_semaine"]

    heures = df["heures_semaine_principal"]
    # Involontaire au sens large : horaire fixe par la loi/l'employeur (2) ou
    # mauvaise conjoncture (3) - exclut le choix personnel (1: ne veut pas
    # travailler plus, 4: probleme personnel), plus proche du sens ILO/BIT
    # que la seule raison economique stricte.
    involontaire = df[v["raison_moins_40h"]].isin([2, 3])
    disponible_plus = df[v["disponible_travailler_plus"]] == 1

    eligible = heures.notna()
    sous_emploi = eligible & (heures < seuil) & involontaire.fillna(False) & disponible_plus.fillna(False)

    # code numerique + libelle (cfg["labels_oui_non"]) : 1 = oui, 2 = non
    df["sous_emploi_duree"] = pd.Series(np.nan, index=df.index, dtype="float")
    df.loc[eligible, "sous_emploi_duree"] = 2
    df.loc[sous_emploi, "sous_emploi_duree"] = 1

    n_eligible = int(eligible.sum())
    n_sous_emploi = int(sous_emploi.sum())
    print(f"  sous-emploi (duree) : {n_sous_emploi}/{n_eligible} occupes avec heures "
          f"renseignees ({100 * n_sous_emploi / n_eligible:.1f}%)")

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
    # revenu_source reprend directement le code AP13a (deja porteur de sens),
    # libelle dans cfg["labels_revenu_source"]
    df["revenu_source"] = mode

    n_total = len(df)
    n_manquant = int(df["revenu_principal_mensuel_fcfa"].isna().sum())
    print(f"  revenu : {n_manquant}/{n_total} manquant (structurel + refus/NSP + "
          f"{int(aberrant.sum())} aberrant(s) neutralise(s))")
    print("  repartition source du revenu (parmi occupes) :")
    print(df["revenu_source"].map(cfg["labels_revenu_source"]).value_counts(dropna=False).to_string())
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

    # code numerique + libelle (cfg["labels_formalite"]) : 1 = formel, 2 = informel
    formalite_unite = pd.Series(np.nan, index=df.index, dtype="float")
    informel_unite = marchande & (non_enregistre | non_comptabilite)
    formel_unite = marchande & ~(non_enregistre | non_comptabilite)
    formalite_unite = formalite_unite.mask(informel_unite, 2)
    formalite_unite = formalite_unite.mask(formel_unite, 1)
    df["formalite_unite"] = formalite_unite

    a_protection = df[v["avantage_protection_sociale"]] == 1
    a_conges_payes = df[v["avantage_conges_payes"]] == 1
    a_conges_maladie = df[v["avantage_conges_maladie"]] == 1
    trois_criteres_renseignes = (df[v["avantage_protection_sociale"]].notna()
                                 & df[v["avantage_conges_payes"]].notna()
                                 & df[v["avantage_conges_maladie"]].notna())

    formalite_emploi = pd.Series(np.nan, index=df.index, dtype="float")
    informel_emploi = trois_criteres_renseignes & ~(a_protection & a_conges_payes & a_conges_maladie)
    formel_emploi = trois_criteres_renseignes & (a_protection & a_conges_payes & a_conges_maladie)
    formalite_emploi = formalite_emploi.mask(informel_emploi, 2)
    formalite_emploi = formalite_emploi.mask(formel_emploi, 1)
    df["formalite_emploi"] = formalite_emploi

    print("  formalite de l'unite (parmi unites concernees) :")
    print(df["formalite_unite"].map(cfg["labels_formalite"]).value_counts(dropna=False).to_string())
    print("  formalite de l'emploi (parmi salaries avec bloc avantages renseigne) :")
    print(df["formalite_emploi"].map(cfg["labels_formalite"]).value_counts(dropna=False).to_string())

    return df


# ----------------------------------------------------------------------------
# Assemblage et ecriture de la sortie
# ----------------------------------------------------------------------------

def construire_sortie(df, cfg):
    """Selectionne et nomme les colonnes finales du bloc emploi principal.
    Les variables brutes intermediaires (AP13A, AP6D, ...) ne sont pas
    reprises - seulement les variables construites."""
    v = cfg["vars"]
    sortie = pd.DataFrame()
    sortie["id_grappe"] = df[v["id_grappe"]]
    sortie["id_menage"] = df[v["id_menage"]]
    sortie["id_ordre"] = df[v["id_ordre"]]
    sortie["id_men"] = df["id_men"]
    sortie["poids_emploi"] = df[v["poids_emploi"]]
    sortie["eligible_module_emploi"] = df["eligible_module_emploi"]

    sortie["situation_activite"] = df["situation_activite"]
    sortie["situation_activite_grp"] = df["situation_activite_grp"]
    sortie["raison_inactivite"] = df["raison_inactivite"]

    sortie["statut_emploi"] = df["statut_emploi"]
    sortie["type_emploi"] = df["type_emploi"]
    sortie["flag_travail_enfant_10_14"] = df["flag_travail_enfant_10_14"]

    sortie["secteur_isic_principal"] = df["secteur_isic_principal"]
    sortie["secteur_isic_principal_4cat"] = df["secteur_isic_principal_4cat"]

    sortie["heures_semaine_principal"] = df["heures_semaine_principal"]
    sortie["sous_emploi_duree"] = df["sous_emploi_duree"]
    sortie["flag_heures_aberrantes"] = df["flag_heures_aberrantes"]
    sortie["flag_ecart_heures"] = df["flag_ecart_heures"]

    sortie["revenu_principal_mensuel_fcfa"] = df["revenu_principal_mensuel_fcfa"]
    sortie["revenu_source"] = df["revenu_source"]
    sortie["flag_revenu_non_renseigne"] = df["flag_revenu_non_renseigne"]
    sortie["flag_revenu_aberrant"] = df["flag_revenu_aberrant"]

    sortie["formalite_unite"] = df["formalite_unite"]
    sortie["formalite_emploi"] = df["formalite_emploi"]
    return sortie


def libelles_sortie(cfg, meta):
    """Construit les dictionnaires de libelles a ecrire dans le .dta de
    sortie : libelles source repris tels quels pour les variables gardees
    avec leur code d'origine, libelles maison pour les variables construites."""
    v = cfg["vars"]
    val_labels = {
        # repris des metadonnees source (suivent le pays automatiquement)
        "situation_activite": libelles_valeurs(meta, v["sitac"]),
        "raison_inactivite": libelles_valeurs(meta, v["raison_inactivite"]),
        "statut_emploi": libelles_valeurs(meta, v["statut_emploi"]),
        "secteur_isic_principal": libelles_valeurs(meta, v["branche"]),
        # construits par ce module
        "eligible_module_emploi": cfg["labels_oui_non"],
        "situation_activite_grp": cfg["labels_situation_activite_grp"],
        "type_emploi": cfg["labels_type_emploi"],
        "secteur_isic_principal_4cat": cfg["labels_secteur_4cat"],
        "sous_emploi_duree": cfg["labels_oui_non"],
        "revenu_source": cfg["labels_revenu_source"],
        "formalite_unite": cfg["labels_formalite"],
        "formalite_emploi": cfg["labels_formalite"],
    }

    col_labels = {
        "id_grappe": "Grappe", "id_menage": "Numero de menage",
        "id_ordre": "Numero d'ordre", "id_men": "Identifiant menage",
        "poids_emploi": "Poids de sondage (emploi)",
        "eligible_module_emploi": "Eligible au module emploi (10 ans et plus)",
        "situation_activite": "Situation d'activite (code source)",
        "situation_activite_grp": "Situation d'activite (regroupee)",
        "raison_inactivite": "Raison d'inactivite",
        "statut_emploi": "Statut dans l'emploi principal (categorie socioprofessionnelle)",
        "type_emploi": "Type d'emploi (salarie/independant)",
        "flag_travail_enfant_10_14": "Travail des enfants (10-14 ans avec statut emploi renseigne)",
        "secteur_isic_principal": "Secteur/branche d'activite (ISIC Rev.4, 21 sections)",
        "secteur_isic_principal_4cat": "Secteur d'activite (4 familles)",
        "heures_semaine_principal": "Heures travaillees par semaine (emploi principal)",
        "sous_emploi_duree": "Sous-emploi lie a la duree du travail",
        "flag_heures_aberrantes": "Heures aberrantes neutralisees (>98h/semaine)",
        "flag_ecart_heures": "Ecart >10h entre heures declarees et calculees",
        "revenu_principal_mensuel_fcfa": "Revenu mensuel consolide de l'emploi principal (FCFA)",
        "revenu_source": "Source/mode de declaration du revenu",
        "flag_revenu_non_renseigne": "Revenu non renseigne (refus/NSP)",
        "flag_revenu_aberrant": "Revenu aberrant neutralise",
        "formalite_unite": "Formalite de l'unite de production (secteur informel ANSD)",
        "formalite_emploi": "Formalite de l'emploi (avantages employeur, salaries uniquement)",
    }
    return val_labels, col_labels


# ----------------------------------------------------------------------------
# Controles de coherence (bloc emploi principal seulement)
# ----------------------------------------------------------------------------

def controles_coherence(df, cfg):
    """
    Controles propres au bloc emploi principal. Ils alimentent le fichier
    QAQC global (Personne 1) sans s'y substituer. Retourne un tableau de
    constats, sur le meme modele que le module demographie/geographie.
    """
    constats = []

    def ajouter(test, n, detail=""):
        constats.append({"controle": test, "nombre": int(n), "detail": detail})

    occupe = df["situation_activite"] == 1
    inactif = df["situation_activite"] == 4

    ajouter("occupes sans statut_emploi renseigne",
            int((occupe & df["statut_emploi"].isna()).sum()), "doit etre nul ou tres faible")

    # Distinguer la vraie anomalie (adulte non-occupe avec statut renseigne)
    # du travail des enfants (10-14 ans, non couverts par sitac mais bel et
    # bien en emploi selon AP3 - cf. flag_travail_enfant_10_14)
    statut_hors_occupe = ~occupe & df["statut_emploi"].notna()
    travail_enfant = df["flag_travail_enfant_10_14"] == 1
    ajouter("statut_emploi renseigne chez des non-occupes ADULTES (hors travail enfants)",
            int((statut_hors_occupe & ~travail_enfant).sum()), "doit valoir 0")
    ajouter("travail des enfants (10-14 ans, hors champ de sitac mais AP3 renseigne)",
            int(travail_enfant.sum()),
            "pas une anomalie : sitac exclut les moins de 15 ans par convention ANSD")

    ajouter("occupes sans secteur_isic_principal renseigne",
            int((occupe & df["secteur_isic_principal"].isna()).sum()), "a verifier")

    ajouter("heures aberrantes neutralisees (>98h/semaine)",
            int(df["flag_heures_aberrantes"].sum()), "neutralisees, individus conserves")
    ajouter("ecart >10h entre heures declarees et calculees (debut/fin x jours)",
            int(df["flag_ecart_heures"].sum()),
            "probablement du a l'absence de pause dejeuner dans le calcul de controle")

    ajouter("revenu non renseigne (refus/NSP, AP13a=5 ou 6)",
            int(df["flag_revenu_non_renseigne"].sum()), "non impute, cf. echange sur l'imputation")
    ajouter("revenu aberrant neutralise (hors bornes de plausibilite)",
            int(df["flag_revenu_aberrant"].sum()), "")

    ajouter("raison d'inactivite renseignee pour des non-inactifs",
            int((~inactif & df["raison_inactivite"].notna()).sum()),
            "cf. main d'oeuvre potentielle, structurel probable")

    ajouter("occupes sans formalite_unite (unites non marchandes ou non renseigne)",
            int((occupe & df["formalite_unite"].isna()).sum()),
            "inclut les unites non marchandes, hors champ par definition ANSD")

    return pd.DataFrame(constats)


def estimations_primaires(df, cfg):
    """
    Estimations ponderees (poids_emploi = weightemploy) apres traitement,
    comparees quand possible aux chiffres deja publies dans le rapport final
    ANSD - sert de premier controle de qualite/plausibilite.
    """
    w = df["poids_emploi"]
    occupe = df["situation_activite"] == 1
    chomeur = df["situation_activite"] == 2
    main_oeuvre = occupe | chomeur

    lignes = []

    def ajouter(indicateur, valeur, reference=None):
        lignes.append({
            "indicateur": indicateur,
            "valeur": round(valeur, 2) if pd.notna(valeur) else np.nan,
            "reference_ansd": reference,
        })

    def part(masque_num, masque_denom):
        denom = w[masque_denom].sum()
        return w[masque_num].sum() / denom * 100 if denom else np.nan

    ajouter("Taux de chomage BIT (%)", part(chomeur, main_oeuvre), 2.9)
    ajouter("Taux d'emplois vulnerables - independant (%)",
            part(occupe & (df["type_emploi"] == 2), occupe), 66.1)
    ajouter("Taux de salarisation (%)",
            part(occupe & (df["type_emploi"] == 1), occupe), 38.6)

    secteurs_ref = {1: ("Primaire", 24.7), 2: ("Industrie", 19.0),
                    3: ("Commerce", 27.6), 4: ("Service", 28.7)}
    for code, (label, reference) in secteurs_ref.items():
        ajouter(f"Secteur {label} parmi occupes (%)",
                part(occupe & (df["secteur_isic_principal_4cat"] == code), occupe), reference)

    ajouter("Taux d'emploi informel (%)",
            part(df["formalite_emploi"] == 2, df["formalite_emploi"].notna()), 95.4)
    ajouter("Taux >48h/semaine parmi occupes (%)",
            part(occupe & (df["heures_semaine_principal"] > 48),
                 occupe & df["heures_semaine_principal"].notna()), 42.3)
    ajouter("Sous-emploi lie a la duree parmi occupes (%)",
            part(df["sous_emploi_duree"] == 1, df["sous_emploi_duree"].notna()), None)

    masque_rev = occupe & df["revenu_principal_mensuel_fcfa"].notna()
    revenu_moyen = (np.average(df.loc[masque_rev, "revenu_principal_mensuel_fcfa"],
                                weights=w[masque_rev]) if masque_rev.sum() else np.nan)
    ajouter("Revenu mensuel moyen, emploi principal (FCFA)", revenu_moyen, 125485)

    masque_heures = occupe & df["heures_semaine_principal"].notna()
    heures_moyennes = (np.average(df.loc[masque_heures, "heures_semaine_principal"],
                                   weights=w[masque_heures]) if masque_heures.sum() else np.nan)
    ajouter("Heures moyennes travaillees par semaine", heures_moyennes, None)

    remuneration_horaire = df["revenu_principal_mensuel_fcfa"] / (df["heures_semaine_principal"] * 4.33)
    masque_rh = masque_rev & masque_heures & (df["heures_semaine_principal"] > 0)
    rh_moyenne = (np.average(remuneration_horaire[masque_rh], weights=w[masque_rh])
                  if masque_rh.sum() else np.nan)
    ajouter("Remuneration horaire moyenne (FCFA/heure)", rh_moyenne, 821.9)

    return pd.DataFrame(lignes)


# ----------------------------------------------------------------------------
# Orchestration : toutes les etapes de recodage thematique sont posees.
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
    df = recoder_sous_emploi(df, cfg, meta)
    df = recoder_revenu(df, cfg, meta)
    df = recoder_formalite(df, cfg, meta)

    sortie = construire_sortie(df, cfg)
    val_labels, col_labels = libelles_sortie(cfg, meta)

    os.makedirs(cfg["dossier_output"], exist_ok=True)
    chemin_dta = os.path.join(cfg["dossier_output"], "emploi_principal.dta")
    pyreadstat.write_dta(sortie, chemin_dta,
                         variable_value_labels=val_labels,
                         column_labels=col_labels)

    print("-" * 64)
    print(f"Table emploi principal ecrite : {chemin_dta} "
          f"({sortie.shape[0]} lignes, {sortie.shape[1]} colonnes)")

    qc = controles_coherence(sortie, cfg)
    est = estimations_primaires(sortie, cfg)
    chemin_qc = os.path.join(cfg["dossier_output"], "qc_emploi_principal.csv")
    chemin_est = os.path.join(cfg["dossier_output"], "estimations_emploi_principal.csv")
    qc.to_csv(chemin_qc, index=False, encoding="utf-8")
    est.to_csv(chemin_est, index=False, encoding="utf-8")

    print("\nControles de coherence (bloc emploi principal) :")
    print(qc.to_string(index=False))
    print("\nEstimations ponderees (poids_emploi) vs reference ANSD :")
    print(est.to_string(index=False))
    print(f"\nFichiers ecrits : {chemin_qc}")
    print(f"                  {chemin_est}")
    print("\nTermine.")


if __name__ == "__main__":
    sys.exit(main())
