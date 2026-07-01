"""
ERI-ESI : module Demographie et Geographie des individus
====================================================================

Role dans le pipeline
---------------------
Ce module prend en entree la base individuelle fusionnee produite a l'amont
(roster individus + module emploi, livree par la Personne 1) et produit un
bloc propre de variables demographiques et geographiques au niveau individu.

Perimetre couvert (et uniquement celui-ci) :
  - Demographie : sexe, age, niveau d'etudes, branche d'etudes,
                  situation matrimoniale, lien de parente avec le CM
  - Geographie  : region, departement (si disponible), milieu de residence
  - Traitement des manquants et des valeurs aberrantes avec controles de coherence

Sortie : une table individus_demo_geo (.dta) qui alimente la table menages
(demographie du CM, Personne 4) et l'assemblage final (Personne 1).

Conception scalable
--------------------
L'enquete ERI-ESI est harmonisee a l'echelle sous-regionale. Pour passer d'un
pays a l'autre, il suffit en principe de modifier le dictionnaire CONFIG
ci-dessous (code pays, chemins, correspondance des noms de variables, presence
ou absence du departement). La logique de recodage et de nettoyage reste
inchangee. Les libelles des modalites sont lus directement dans les metadonnees
du fichier .dta, donc ils suivent automatiquement le pays.

Auteur : Awa GUEYE
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
import pyreadstat

# Journal d'execution partage par tout le module. Il est configure dans main()
# pour ecrire a la fois dans la console et dans un fichier journal_demo_geo.log.
log = logging.getLogger("demo_geo")

# Racine du depot (deux niveaux au dessus de scripts/python/), pour que les
# chemins input/ et output/ se resolvent quel que soit le repertoire d'appel.
RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ----------------------------------------------------------------------------
# CONFIGURATION (seul bloc a adapter pour changer de pays)
# ----------------------------------------------------------------------------

CONFIG = {
    # Identite du pays et de la vague
    "pays": "SEN",
    "vague": "2017",

    # Chemins. La base fusionnee est produite par la Personne 1.
    # On la cherche d'abord dans output/<PAYS>/ puis dans input/<PAYS>/.
    "fichier_base": "base_individus_emploi_fusionnee.dta",
    "dossier_input": os.path.join(RACINE, "input", "SEN"),
    "dossier_output": os.path.join(RACINE, "output", "SEN"),

    # Correspondance variables conceptuelles -> noms reels dans le fichier pays.
    # Pour un autre pays, on ne touche en general qu'a cette section.
    "vars": {
        # identifiants
        "id_grappe": "hh1",
        "id_menage": "hh2",
        "id_ordre": "m1",
        "poids": "hhweight",
        "taille_menage": "hhsize",

        # demographie
        "sexe": "M3",          # sexe au roster, source de reference (complet)
        "sexe_emploi": "m3E",  # sexe au module emploi, sert au controle croise
        "age": "M4",           # age au roster, source de reference (complet)
        "age_emploi": "m4",    # age au module emploi, sert au controle croise
        "lien_cm": "M2",
        "matrimoniale": "M25",

        # education : plusieurs variables combinees pour reconstituer le niveau
        "ecole_deja": "M13",       # a deja ete a l'ecole (1 oui / 2 non)
        "ecole_actuelle": "M15",   # va actuellement a l'ecole (1 oui / 2 non)
        "niveau_actuel": "M16a",   # niveau si scolarise actuellement
        "niveau_atteint": "M20a",  # niveau atteint si a quitte l'ecole
        "niveau_secours": "M19a",  # niveau de secours (annee precedente)
        "diplome": "M21",

        # geographie
        "region": "Region",
        "departement": None,       # absent du fichier Senegal, voir note plus bas
        "milieu": "MILIEU",
        "milieu_etendu": "milieu_etendu",
    },

    # Seuils de plausibilite et bornes structurelles (parametrables)
    "age_min": 0,
    "age_max": 110,           # au dela : valeur jugee aberrante
    "age_min_matrimoniale": 12,  # M25 n'est posee qu'a partir de cet age
    "codes_age_nsp": [99],    # codes a traiter comme non renseigne

    # Modalites consolidees construites par ce module (libelles maison)
    "labels_groupe_age": {
        1: "0-4 ans", 2: "5-9 ans", 3: "10-14 ans", 4: "15-24 ans",
        5: "25-34 ans", 6: "35-49 ans", 7: "50-64 ans", 8: "65 ans et plus",
    },
    "labels_lien_cm_grp": {
        1: "Chef de menage", 2: "Conjoint(e)", 3: "Enfant",
        4: "Autre parent", 5: "Sans lien de parente / domestique",
    },
    "labels_niveau_etudes": {
        0: "Non applicable (trop jeune)",
        1: "Aucun (jamais scolarise)",
        2: "Prescolaire",
        3: "Primaire",
        4: "Secondaire premier cycle",
        5: "Secondaire second cycle",
        6: "Superieur",
    },
    "labels_branche_etudes": {
        0: "Non applicable",
        1: "Enseignement general",
        2: "Enseignement technique",
        3: "Superieur",
    },
    "labels_matrimoniale": {
        0: "Non applicable (moins de 12 ans)",
        9: "Manquant",
    },
}


# Variables conceptuelles facultatives : leur absence n'arrete pas le pipeline.
VARS_FACULTATIVES = {"departement", "milieu_etendu", "age_emploi", "sexe_emploi", "diplome"}


# ----------------------------------------------------------------------------
# Utilitaires
# ----------------------------------------------------------------------------

def creer_journal(cfg):
    """
    Met en place le journal d'execution. Tout ce que le module raconte part a la
    fois vers la console et vers un fichier, pour garder une trace datee du
    traitement, utile a la relecture et au controle qualite.
    """
    os.makedirs(cfg["dossier_output"], exist_ok=True)
    chemin_log = os.path.join(cfg["dossier_output"], "journal_demo_geo.log")

    log.setLevel(logging.INFO)
    log.handlers.clear()
    fichier = logging.FileHandler(chemin_log, mode="w", encoding="utf-8")
    fichier.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s",
                                           "%Y-%m-%d %H:%M:%S"))
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(fichier)
    log.addHandler(console)
    return chemin_log


def valider_colonnes(cfg, chemin):
    """
    Verifie, avant tout traitement, que le fichier du pays contient bien les
    variables attendues. Si une variable manque, le message dit laquelle et ou
    la corriger, au lieu de laisser survenir plus loin une erreur obscure. C'est
    la garantie qu'un fichier d'un autre pays soit accueilli proprement.
    """
    _, meta = pyreadstat.read_dta(chemin, metadataonly=True)
    presentes = set(meta.column_names)

    attendues = {nom: col for nom, col in cfg["vars"].items()
                 if col is not None and nom not in VARS_FACULTATIVES}
    manquantes = {nom: col for nom, col in attendues.items() if col not in presentes}

    if manquantes:
        details = ", ".join(f"{nom} attendue sous le nom '{col}'"
                            for nom, col in manquantes.items())
        raise KeyError(
            "Le fichier ne contient pas toutes les variables requises. Manquent : "
            + details + ". La correspondance se corrige dans CONFIG['vars'] pour ce pays."
        )

    # les facultatives absentes sont seulement signalees
    facultatives = {nom: col for nom, col in cfg["vars"].items()
                    if col is not None and nom in VARS_FACULTATIVES}
    absentes_fac = [nom for nom, col in facultatives.items() if col not in presentes]
    log.info(f"  validation colonnes : {len(attendues)} variables requises presentes")
    if absentes_fac:
        log.info(f"  variables facultatives absentes (tolerees) : {', '.join(absentes_fac)}")


def localiser_base(cfg):
    """Retourne le chemin de la base fusionnee, output prioritaire sur input."""
    for dossier in (cfg["dossier_output"], cfg["dossier_input"]):
        chemin = os.path.join(dossier, cfg["fichier_base"])
        if os.path.exists(chemin):
            return chemin
    raise FileNotFoundError(
        "Base fusionnee introuvable. Attendue dans "
        f"{cfg['dossier_output']} ou {cfg['dossier_input']} sous le nom "
        f"{cfg['fichier_base']} (livrable de la Personne 1)."
    )


def charger_base(cfg):
    """Charge uniquement les colonnes utiles au bloc demo/geo et leurs metadonnees."""
    v = cfg["vars"]
    colonnes = [c for c in [
        v["id_grappe"], v["id_menage"], v["id_ordre"], v["poids"], v["taille_menage"],
        v["sexe"], v["sexe_emploi"], v["age"], v["age_emploi"], v["lien_cm"],
        v["matrimoniale"], v["ecole_deja"], v["ecole_actuelle"], v["niveau_actuel"],
        v["niveau_atteint"], v["niveau_secours"], v["diplome"],
        v["region"], v["milieu"], v["milieu_etendu"],
    ] if c is not None]
    if v["departement"] is not None:
        colonnes.append(v["departement"])

    chemin = localiser_base(cfg)
    df, meta = pyreadstat.read_dta(chemin, usecols=colonnes)
    log.info(f"  base chargee : {df.shape[0]} lignes, {df.shape[1]} colonnes")
    return df, meta


def libelles_valeurs(meta, nom_var):
    """Recupere le dictionnaire valeur -> libelle d'une variable depuis les metadonnees."""
    set_lbl = meta.variable_to_label.get(nom_var)
    if set_lbl and set_lbl in meta.value_labels:
        return dict(meta.value_labels[set_lbl])
    return {}


# ----------------------------------------------------------------------------
# Etapes de nettoyage et de recodage
# ----------------------------------------------------------------------------

def nettoyer_sexe(df, cfg):
    """
    Reference = sexe du roster (complet). On le croise avec le sexe du module
    emploi pour signaler les incoherences, sans ecraser la reference.
    Repond a la tache : traiter les manquants reels sexe/age (~32% sur m3E/m4).
    """
    v = cfg["vars"]
    sexe = df[v["sexe"]].copy()
    sexe_emp = df[v["sexe_emploi"]]

    # signalement des desaccords la ou les deux sources existent
    flag = (sexe.notna() & sexe_emp.notna() & (sexe != sexe_emp))
    df["sexe"] = sexe
    df["flag_sexe_incoherent"] = flag.astype("int8")
    log.info(f"  sexe : {int(df['sexe'].isna().sum())} manquant(s), "
          f"{int(flag.sum())} desaccord(s) roster/emploi (roster conserve)")
    return df


def nettoyer_age(df, cfg):
    """
    Reference = age du roster. On neutralise les codes NSP et les ages aberrants,
    puis on construit un groupe d'age. Le module emploi (32% manquant) ne sert
    qu'au controle croise et ne degrade pas la reference complete.
    """
    v = cfg["vars"]
    age = df[v["age"]].copy().astype("float")

    # codes type 99 = NSP -> manquant
    age = age.replace(cfg["codes_age_nsp"], np.nan)
    # bornes de plausibilite
    aberrant = (age < cfg["age_min"]) | (age > cfg["age_max"])
    df["flag_age_aberrant"] = aberrant.fillna(False).astype("int8")
    age = age.mask(aberrant, np.nan)
    df["age"] = age

    bornes = [-0.1, 5, 10, 15, 25, 35, 50, 65, 200]
    df["groupe_age"] = pd.cut(age, bins=bornes, labels=list(range(1, 9))).astype("float")

    log.info(f"  age : {int(df['age'].isna().sum())} manquant(s), "
          f"{int(df['flag_age_aberrant'].sum())} aberrant(s) neutralise(s)")
    return df


def recoder_lien_cm(df, cfg, meta):
    """Conserve le code detaille (M2) et ajoute un regroupement lisible."""
    v = cfg["vars"]
    df["lien_cm"] = df[v["lien_cm"]]

    correspondance = {1: 1, 2: 2, 3: 3, 4: 4, 5: 4, 6: 4, 7: 4, 8: 5, 9: 5}
    df["lien_cm_grp"] = df["lien_cm"].map(correspondance).astype("float")
    log.info(f"  lien CM : {int(df['lien_cm'].isna().sum())} manquant(s)")
    return df


def recoder_matrimoniale(df, cfg):
    """
    M25 n'est posee qu'a partir de 12 ans. Les manquants en dessous de cet age
    sont structurels (non applicable), pas des manquants reels. Au dessus, un
    manquant residuel est code explicitement 'Manquant'.
    """
    v = cfg["vars"]
    seuil = cfg["age_min_matrimoniale"]
    mat = df[v["matrimoniale"]].copy()

    non_applicable = df["age"].notna() & (df["age"] < seuil)
    manquant_reel = mat.isna() & (df["age"] >= seuil)

    mat = mat.copy()
    mat[non_applicable] = 0   # non applicable (trop jeune)
    mat[manquant_reel] = 9    # manquant residuel signale
    df["matrimoniale"] = mat
    df["flag_matrimoniale_manquant"] = manquant_reel.astype("int8")

    log.info(f"  matrimoniale : {int(non_applicable.sum())} non applicable (<{seuil} ans), "
          f"{int(manquant_reel.sum())} manquant(s) reel(s)")
    return df


def consolider_education(df, cfg):
    """
    Reconstitue un niveau d'etudes unique a partir de plusieurs variables :
      - jamais scolarise (M13==2)            -> Aucun
      - scolarise actuellement (M15==1)      -> niveau actuel (M16a)
      - a quitte l'ecole (M15==2)            -> niveau atteint (M20a), secours M19a
      - trop jeune (M13 manquant, age bas)   -> Non applicable
    Le niveau brut ERI-ESI (0 a 6) est ensuite simplifie en categories
    comparables entre pays. La branche (general / technique) est deduite du
    meme code, car les modalites distinguent ces deux filieres au secondaire.
    """
    v = cfg["vars"]

    deja = df[v["ecole_deja"]]
    actuelle = df[v["ecole_actuelle"]]
    niv_actuel = df[v["niveau_actuel"]]
    niv_atteint = df[v["niveau_atteint"]]
    niv_secours = df[v["niveau_secours"]]

    # niveau brut ERI-ESI (echelle 0 a 6) selon la situation scolaire
    niveau_brut = pd.Series(np.nan, index=df.index, dtype="float")
    niveau_brut = niveau_brut.where(~(actuelle == 1), niv_actuel)
    a_quitte = (actuelle == 2)
    niveau_brut = niveau_brut.where(~a_quitte, niv_atteint)
    # secours pour les sortants sans niveau atteint renseigne
    manque_sortant = a_quitte & niveau_brut.isna()
    niveau_brut = niveau_brut.where(~manque_sortant, niv_secours)

    # simplification vers categories portables
    def simplifier(code):
        if pd.isna(code):
            return np.nan
        code = int(code)
        return {0: 2, 1: 3, 2: 4, 3: 5, 4: 4, 5: 5, 6: 6}.get(code, np.nan)

    niveau = niveau_brut.map(simplifier)

    # jamais scolarise -> Aucun (1)
    niveau = niveau.where(~(deja == 2), 1)
    # trop jeune (jamais d'info ecole et age bas) -> Non applicable (0)
    trop_jeune = deja.isna() & (df["age"].notna()) & (df["age"] < 6)
    niveau = niveau.where(~trop_jeune, 0)

    df["niveau_etudes"] = niveau

    # branche d'etudes deduite du niveau brut (general vs technique vs superieur)
    def brancher(code):
        if pd.isna(code):
            return np.nan
        code = int(code)
        if code in (2, 3):
            return 1   # secondaire general
        if code in (4, 5):
            return 2   # secondaire technique
        if code == 6:
            return 3   # superieur
        return 0       # non applicable (prescolaire, primaire, aucun)

    df["branche_etudes"] = niveau_brut.map(brancher)
    # aligner les non applicables education avec le niveau
    df.loc[df["niveau_etudes"].isin([0, 1]), "branche_etudes"] = 0

    n_renseigne = int(df["niveau_etudes"].notna().sum())
    log.info(f"  education : niveau renseigne pour {n_renseigne} individus "
          f"({100*n_renseigne/len(df):.1f}%)")
    return df


def recoder_geographie(df, cfg):
    """Region et milieu de residence. Le departement est gere selon sa disponibilite."""
    v = cfg["vars"]
    df["region"] = df[v["region"]]
    df["milieu"] = df[v["milieu"]]
    if v.get("milieu_etendu"):
        df["milieu_etendu"] = df[v["milieu_etendu"]]

    if v["departement"] is not None:
        df["departement"] = df[v["departement"]]
        statut_dep = "present"
    else:
        # Le fichier Senegal ne contient pas le departement. On cree la colonne
        # vide pour garder un schema de sortie stable entre pays, et on le
        # documente dans le journal et le QC.
        df["departement"] = np.nan
        statut_dep = "absent (non collecte dans ce fichier)"

    log.info(f"  geographie : region et milieu recodes, departement {statut_dep}")
    return df, statut_dep


# ----------------------------------------------------------------------------
# Controles de coherence (bloc demo/geo seulement)
# ----------------------------------------------------------------------------

def controles_coherence(df, cfg):
    """
    Controles propres au bloc demo/geo. Ils alimentent le fichier QAQC global
    (Personne 1) sans s'y substituer. Retourne un tableau de constats.
    """
    constats = []

    def ajouter(test, n, detail=""):
        constats.append({"controle": test, "nombre": int(n), "detail": detail})

    # 1) un seul chef de menage par menage
    cm_par_menage = df.loc[df["lien_cm"] == 1].groupby("id_men").size()
    ajouter("menages avec un nombre de CM different de 1",
            int((cm_par_menage != 1).sum()),
            "doit valoir 0")

    # 2) coherence age / lien CM : un CM de moins de 12 ans est suspect
    ajouter("CM de moins de 12 ans",
            int(((df["lien_cm"] == 1) & (df["age"] < 12)).sum()),
            "a verifier")

    # 3) coherence matrimoniale / age : marie de moins de 12 ans
    ajouter("personnes mariees de moins de 12 ans",
            int((df["matrimoniale"].isin([2, 3]) & (df["age"] < 12)).sum()),
            "doit valoir 0")

    # 4) coherence education / age : niveau superieur avant 18 ans
    ajouter("niveau superieur declare avant 18 ans",
            int(((df["niveau_etudes"] == 6) & (df["age"] < 18)).sum()),
            "a verifier")

    # 5) manquants residuels sur variables cles
    for var in ["sexe", "age", "region", "milieu", "lien_cm"]:
        ajouter(f"manquants sur {var}", int(df[var].isna().sum()),
                "variable attendue complete")

    # 6) desaccords sexe roster / emploi
    ajouter("desaccords sexe roster vs emploi",
            int(df["flag_sexe_incoherent"].sum()),
            "roster conserve comme reference")

    return pd.DataFrame(constats)


def estimations_primaires(df, cfg):
    """
    Quelques estimations ponderees apres traitement, pour verifier que les
    distributions restent plausibles. Sert de premier coup d'oeil qualite.
    """
    w = df[cfg["vars"]["poids"]].fillna(0)
    lignes = []

    def part_ponderee(masque, libelle):
        total = w.sum()
        part = w[masque].sum() / total * 100 if total else np.nan
        lignes.append({"indicateur": libelle, "valeur_%": round(part, 2)})

    part_ponderee(df["sexe"] == 2, "Part de femmes")
    part_ponderee(df["age"] < 15, "Part de moins de 15 ans")
    part_ponderee(df["age"] >= 65, "Part de 65 ans et plus")
    part_ponderee(df["milieu"] == 1, "Part en milieu urbain")
    part_ponderee((df["matrimoniale"] == 2) | (df["matrimoniale"] == 3),
                  "Part de maries (12 ans et plus, ponderee sur tous)")
    part_ponderee(df["niveau_etudes"] == 1, "Part sans aucun niveau scolaire")

    age_moyen = np.average(df["age"].dropna(),
                           weights=w[df["age"].notna()]) if w.sum() else np.nan
    lignes.append({"indicateur": "Age moyen (ans)", "valeur_%": round(age_moyen, 1)})
    return pd.DataFrame(lignes)


def exporter_codebook(sortie, val_labels, col_labels, cfg):
    """
    Construit un codebook lisible : pour chaque variable de sortie, son libelle,
    ses modalites avec leur effectif et leur part ponderee, ou ses statistiques
    de base si elle est numerique. C'est la carte d'identite du fichier produit,
    qui documente ce qui a reellement ete cree.
    """
    poids = sortie["poids"].fillna(0)
    total = poids.sum()
    numeriques = {"poids", "taille_menage", "age"}
    identifiants = {"id_grappe", "id_menage", "id_ordre", "id_men"}
    lignes = []

    for col in sortie.columns:
        libelle = col_labels.get(col, col)

        if col in identifiants:
            lignes.append({
                "variable": col, "libelle_variable": libelle,
                "modalite": "identifiant", "libelle_modalite": "",
                "effectif": int(sortie[col].notna().sum()),
                "part_ponderee_%": "",
                "detail": f"{sortie[col].nunique()} valeurs distinctes",
            })
            continue

        if col in numeriques:
            serie = pd.to_numeric(sortie[col], errors="coerce")
            lignes.append({
                "variable": col, "libelle_variable": libelle,
                "modalite": "statistiques", "libelle_modalite": "",
                "effectif": int(serie.notna().sum()),
                "part_ponderee_%": "",
                "detail": (f"min={serie.min():.0f} moyenne={serie.mean():.1f} "
                           f"max={serie.max():.0f} manquants={int(serie.isna().sum())}"),
            })
            continue

        labels_col = val_labels.get(col, {})
        valeurs = sorted(sortie[col].dropna().unique().tolist())
        for val in valeurs:
            masque = sortie[col] == val
            eff = int(masque.sum())
            part = poids[masque].sum() / total * 100 if total else np.nan
            lignes.append({
                "variable": col, "libelle_variable": libelle,
                "modalite": val,
                "libelle_modalite": labels_col.get(val, labels_col.get(int(val), "")),
                "effectif": eff,
                "part_ponderee_%": round(part, 2),
                "detail": "",
            })
        n_manquant = int(sortie[col].isna().sum())
        if n_manquant:
            lignes.append({
                "variable": col, "libelle_variable": libelle,
                "modalite": "manquant", "libelle_modalite": "",
                "effectif": n_manquant, "part_ponderee_%": "", "detail": "",
            })

    return pd.DataFrame(lignes)


# ----------------------------------------------------------------------------
# Assemblage et ecriture de la sortie
# ----------------------------------------------------------------------------

def construire_sortie(df, cfg, meta):
    """Selectionne et nomme les colonnes finales du bloc demo/geo."""
    v = cfg["vars"]
    sortie = pd.DataFrame()
    sortie["id_grappe"] = df[v["id_grappe"]]
    sortie["id_menage"] = df[v["id_menage"]]
    sortie["id_ordre"] = df[v["id_ordre"]]
    sortie["id_men"] = df["id_men"]
    sortie["poids"] = df[v["poids"]]
    sortie["taille_menage"] = df[v["taille_menage"]]

    sortie["sexe"] = df["sexe"]
    sortie["age"] = df["age"]
    sortie["groupe_age"] = df["groupe_age"]
    sortie["lien_cm"] = df["lien_cm"]
    sortie["lien_cm_grp"] = df["lien_cm_grp"]
    sortie["matrimoniale"] = df["matrimoniale"]
    sortie["niveau_etudes"] = df["niveau_etudes"]
    sortie["branche_etudes"] = df["branche_etudes"]

    sortie["region"] = df["region"]
    sortie["departement"] = df["departement"]
    sortie["milieu"] = df["milieu"]
    if "milieu_etendu" in df:
        sortie["milieu_etendu"] = df["milieu_etendu"]

    sortie["flag_sexe_incoherent"] = df["flag_sexe_incoherent"]
    sortie["flag_age_aberrant"] = df["flag_age_aberrant"]
    sortie["flag_matrimoniale_manquant"] = df["flag_matrimoniale_manquant"]
    return sortie


def libelles_sortie(cfg, meta):
    """Construit les dictionnaires de libelles a ecrire dans le .dta de sortie."""
    v = cfg["vars"]
    val_labels = {
        # repris des metadonnees source (suivent le pays automatiquement)
        "sexe": libelles_valeurs(meta, v["sexe"]),
        "lien_cm": libelles_valeurs(meta, v["lien_cm"]),
        "region": libelles_valeurs(meta, v["region"]),
        "milieu": libelles_valeurs(meta, v["milieu"]),
        # construits par ce module
        "groupe_age": cfg["labels_groupe_age"],
        "lien_cm_grp": cfg["labels_lien_cm_grp"],
        "niveau_etudes": cfg["labels_niveau_etudes"],
        "branche_etudes": cfg["labels_branche_etudes"],
    }
    if v.get("milieu_etendu"):
        val_labels["milieu_etendu"] = libelles_valeurs(meta, v["milieu_etendu"])

    # matrimoniale : libelles source + codes maison 0 et 9
    mat = libelles_valeurs(meta, v["matrimoniale"])
    mat.update(cfg["labels_matrimoniale"])
    val_labels["matrimoniale"] = mat

    col_labels = {
        "id_grappe": "Grappe", "id_menage": "Numero de menage",
        "id_ordre": "Numero d'ordre", "id_men": "Identifiant menage",
        "poids": "Poids de sondage", "taille_menage": "Taille du menage",
        "sexe": "Sexe", "age": "Age (annees)", "groupe_age": "Groupe d'age",
        "lien_cm": "Lien de parente avec le CM (detaille)",
        "lien_cm_grp": "Lien de parente avec le CM (regroupe)",
        "matrimoniale": "Situation matrimoniale",
        "niveau_etudes": "Niveau d'etudes consolide",
        "branche_etudes": "Branche d'etudes",
        "region": "Region", "departement": "Departement",
        "milieu": "Milieu de residence", "milieu_etendu": "Strate de residence",
        "flag_sexe_incoherent": "Desaccord sexe roster vs emploi",
        "flag_age_aberrant": "Age aberrant neutralise",
        "flag_matrimoniale_manquant": "Situation matrimoniale manquante (12 ans et plus)",
    }
    return val_labels, col_labels


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------

def main():
    cfg = CONFIG
    chemin_log = creer_journal(cfg)
    log.info(f"Module demographie/geographie - pays {cfg['pays']} {cfg['vague']}")
    log.info("-" * 64)

    # Le fichier est d'abord localise, puis ses colonnes sont controlees avant
    # tout traitement. Un fichier d'un autre pays mal aligne est arrete ici avec
    # un message explicite.
    chemin_base = localiser_base(cfg)
    valider_colonnes(cfg, chemin_base)

    df, meta = charger_base(cfg)

    # identifiant menage unique
    v = cfg["vars"]
    df["id_men"] = (df[v["id_grappe"]].astype("Int64").astype(str) + "_"
                    + df[v["id_menage"]].astype("Int64").astype(str))

    df = nettoyer_sexe(df, cfg)
    df = nettoyer_age(df, cfg)
    df = recoder_lien_cm(df, cfg, meta)
    df = recoder_matrimoniale(df, cfg)
    df = consolider_education(df, cfg)
    df, statut_dep = recoder_geographie(df, cfg)

    sortie = construire_sortie(df, cfg, meta)
    val_labels, col_labels = libelles_sortie(cfg, meta)

    os.makedirs(cfg["dossier_output"], exist_ok=True)
    chemin_dta = os.path.join(cfg["dossier_output"], "individus_demo_geo.dta")
    pyreadstat.write_dta(sortie, chemin_dta,
                         variable_value_labels=val_labels,
                         column_labels=col_labels)
    log.info("-" * 64)
    log.info(f"Table individus ecrite : {chemin_dta} ({sortie.shape[0]} lignes, "
          f"{sortie.shape[1]} colonnes)")

    # controles de coherence et estimations primaires (bloc demo/geo)
    qc = controles_coherence(df, cfg)
    est = estimations_primaires(df, cfg)
    codebook = exporter_codebook(sortie, val_labels, col_labels, cfg)
    chemin_qc = os.path.join(cfg["dossier_output"], "qc_demo_geo.csv")
    chemin_est = os.path.join(cfg["dossier_output"], "estimations_demo_geo.csv")
    chemin_cb = os.path.join(cfg["dossier_output"], "codebook_demo_geo.csv")
    qc.to_csv(chemin_qc, index=False, encoding="utf-8")
    est.to_csv(chemin_est, index=False, encoding="utf-8")
    codebook.to_csv(chemin_cb, index=False, encoding="utf-8")

    log.info("\nControles de coherence (bloc demo/geo) :")
    log.info(qc.to_string(index=False))
    log.info("\nEstimations primaires ponderees :")
    log.info(est.to_string(index=False))
    log.info(f"\nNote departement : {statut_dep}")
    log.info(f"Codebook ecrit : {chemin_cb} ({len(codebook)} lignes)")
    log.info(f"Journal ecrit  : {chemin_log}")
    log.info("\nTermine.")


if __name__ == "__main__":
    sys.exit(main())
