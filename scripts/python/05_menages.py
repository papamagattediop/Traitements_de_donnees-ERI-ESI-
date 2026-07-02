"""
ERI-ESI -- Table menages consolidee
Usage : python scripts/python/05_menages.py
"""

import time
import pyreadstat
import pandas as pd
import numpy as np

PAYS        = "SEN"
DOSSIER_OUT = f"output/{PAYS}"
SORTIE      = f"{DOSSIER_OUT}/menages.dta"


def main():
    debut = time.time()

    ind, _ = pyreadstat.read_dta(f"{DOSSIER_OUT}/individus_demo_geo.dta")
    print(f"individus_demo_geo : {ind.shape[0]:,} lignes")

    # Structure du menage calculee avant reduction au CM
    ind["est_homme"]  = (ind["sexe"] == 1).astype(int)
    ind["est_femme"]  = (ind["sexe"] == 2).astype(int)
    ind["est_u15"]    = ((ind["age"] < 15) & ind["age"].notna()).astype(int)
    ind["est_15plus"] = ((ind["age"] >= 15) & ind["age"].notna()).astype(int)

    grp = ind.groupby("id_men").agg(
        nb_membres  =("id_ordre", "count"),
        nb_hommes   =("est_homme", "sum"),
        nb_femmes   =("est_femme", "sum"),
        nb_u15      =("est_u15", "sum"),
        nb_15plus   =("est_15plus", "sum"),
    ).reset_index()

    # Reduction au CM
    cm = ind[ind["lien_cm"] == 1].copy()

    cm = cm.rename(columns={
        "sexe":           "sexe_cm",
        "age":            "age_cm",
        "groupe_age":     "groupe_age_cm",
        "niveau_etudes":  "niveau_etudes_cm",
        "branche_etudes": "branche_etudes_cm",
    })

    if "matrimoniale" in cm.columns:
        cm = cm.rename(columns={"matrimoniale": "situation_matrimoniale_cm"})
    else:
        cm["situation_matrimoniale_cm"] = np.nan

    cm = cm.merge(grp, on="id_men", how="left")

    cols = ["id_grappe", "id_menage", "id_men", "poids", "taille_menage",
            "sexe_cm", "age_cm", "groupe_age_cm", "situation_matrimoniale_cm",
            "niveau_etudes_cm", "branche_etudes_cm",
            "region", "departement", "milieu", "milieu_etendu",
            "nb_membres", "nb_hommes", "nb_femmes", "nb_u15", "nb_15plus"]
    cols = [c for c in cols if c in cm.columns]
    cm = cm[cols]

    # Controles
    qc_cm   = int((grp["nb_membres"] == 0).sum())
    qc_sex  = int(cm["sexe_cm"].isna().sum())
    qc_age  = int(cm["age_cm"].isna().sum())
    qc_jeun = int(((cm["age_cm"] < 15) & cm["age_cm"].notna()).sum())
    qc_tail = int(((cm["taille_menage"] != cm["nb_membres"]) & cm["nb_membres"].notna()).sum()) if "taille_menage" in cm.columns else 0

    qc = pd.DataFrame({
        "controle": ["menages sans CM unique", "manquants sexe_cm", "manquants age_cm",
                     "CM de moins de 15 ans", "taille_menage != nb_membres calcule"],
        "nombre":   [qc_cm, qc_sex, qc_age, qc_jeun, qc_tail],
        "detail":   ["doit valoir 0", "variable attendue complete", "variable attendue complete",
                     "a verifier", "incoherence a verifier"],
    })
    qc.to_csv(f"{DOSSIER_OUT}/qc_menages.csv", index=False)

    # Estimations
    w = cm["poids"]
    e_tail  = np.average(cm["taille_menage"].fillna(0), weights=w) if "taille_menage" in cm.columns else np.nan
    e_femcm = np.average((cm["sexe_cm"] == 2).astype(float), weights=w) * 100
    e_age   = np.average(cm["age_cm"].fillna(0), weights=w)

    est = pd.DataFrame({
        "indicateur": ["Taille moyenne du menage", "Part menages diriges par une femme (%)", "Age moyen du CM (ans)"],
        "valeur":     [round(e_tail, 2), round(e_femcm, 2), round(e_age, 1)],
    })
    est.to_csv(f"{DOSSIER_OUT}/estimations_menages.csv", index=False)

    pyreadstat.write_dta(cm, SORTIE, version=118)
    print(f"Sortie : {SORTIE} ({cm.shape[0]:,} menages)")
    print(f"Termine en {round(time.time() - debut)}s.")


if __name__ == "__main__":
    main()
