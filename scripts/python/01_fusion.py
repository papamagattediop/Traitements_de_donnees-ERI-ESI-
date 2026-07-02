"""
ERI-ESI -- Fusion roster individus + module emploi
Usage : python scripts/python/01_fusion.py
"""

import time
import pyreadstat
import pandas as pd

PAYS        = "SEN"
DOSSIER_OUT = f"output/{PAYS}"
FICHIER_IND = f"input/{PAYS}/individus_TP.dta"
FICHIER_EMP = f"input/{PAYS}/emploi_Tp.dta"
SORTIE      = f"{DOSSIER_OUT}/base_individus_emploi_fusionnee.dta"


def main():
    debut = time.time()

    ind, meta_ind = pyreadstat.read_dta(FICHIER_IND)
    emp, meta_emp = pyreadstat.read_dta(FICHIER_EMP)

    print(f"individus_TP : {ind.shape[0]:,} lignes, {ind.shape[1]} variables")
    print(f"emploi_Tp    : {emp.shape[0]:,} lignes, {emp.shape[1]} variables")

    # Harmonisation de la cle de fusion (m1 vs M1)
    if "m1" not in emp.columns and "M1" in emp.columns:
        emp = emp.rename(columns={"M1": "m1"})
    if "m1" not in ind.columns and "M1" in ind.columns:
        ind = ind.rename(columns={"M1": "m1"})

    base = pd.merge(
        ind, emp,
        on=["hh1", "hh2", "m1"],
        how="left",
        suffixes=("", "_emp"),
        indicator=True,
    )

    n_matched   = (base["_merge"] == "both").sum()
    n_left_only = (base["_merge"] == "left_only").sum()
    print(f"Apparies     : {n_matched:,}")
    print(f"Non apparies : {n_left_only} (hors champ module emploi, <10 ans)")

    base = base.drop(columns=["_merge"])

    pyreadstat.write_dta(base, SORTIE, version=118)
    print(f"Sortie : {SORTIE} ({base.shape[0]:,} lignes, {base.shape[1]} variables)")
    print(f"Termine en {round(time.time() - debut)}s.")


if __name__ == "__main__":
    main()
