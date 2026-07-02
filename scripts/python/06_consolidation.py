"""
ERI-ESI -- Consolidation finale : tables individus et menages
Usage : python scripts/python/06_consolidation.py
"""

import time
import pyreadstat
import pandas as pd
import numpy as np

PAYS        = "SEN"
DOSSIER_OUT = f"output/{PAYS}"

SOURCES = {
    "individus_demo_geo":   f"{DOSSIER_OUT}/individus_demo_geo.dta",
    "emploi_principal":     f"{DOSSIER_OUT}/emploi_principal.dta",
    "emploi_secondaire":    f"{DOSSIER_OUT}/emploi_secondaire.dta",
    "menages":              f"{DOSSIER_OUT}/menages.dta",
}

CLE_IND = ["id_grappe", "id_menage", "id_ordre"]
CLE_MEN = ["id_men"]


def main():
    debut = time.time()

    for nom, chemin in SOURCES.items():
        try:
            open(chemin)
        except FileNotFoundError:
            raise FileNotFoundError(f"Fichier manquant : {chemin}")

    # --- Table individus
    ind, _  = pyreadstat.read_dta(SOURCES["individus_demo_geo"])
    emp, _  = pyreadstat.read_dta(SOURCES["emploi_principal"])
    sec, _  = pyreadstat.read_dta(SOURCES["emploi_secondaire"])

    individus = ind.merge(emp, on=CLE_IND, how="left", suffixes=("", "_emp"))
    individus = individus.merge(sec, on=CLE_IND, how="left", suffixes=("", "_sec"))

    n_elig      = individus["eligible_module_emploi"].eq(1).sum() if "eligible_module_emploi" in individus.columns else np.nan
    n_sans_sit  = (individus.get("eligible_module_emploi") == 1) & individus.get("situation_activite", pd.Series(dtype=float)).isna()

    qc_ind = pd.DataFrame({
        "controle": [
            "eligibles module emploi sans situation_activite",
            "occupes sans information emploi secondaire",
        ],
        "nombre": [
            int(n_sans_sit.sum()) if hasattr(n_sans_sit, "sum") else 0,
            int(((individus.get("situation_activite") == 1) & individus.get("a_emploi_secondaire", pd.Series(dtype=float)).isna()).sum()),
        ],
        "detail": ["doit valoir 0", "a verifier"],
    })
    qc_ind.to_csv(f"{DOSSIER_OUT}/qc_consolidation_individus.csv", index=False)

    pyreadstat.write_dta(individus, f"{DOSSIER_OUT}/individus_consolide.dta", version=118)
    print(f"individus_consolide.dta : {individus.shape[0]:,} lignes")

    # --- Agregats emploi au niveau menage
    sitac = individus.get("situation_activite", pd.Series(dtype=float))
    individus["est_occupe"]   = (sitac == 1).astype(int)
    individus["est_salarie"]  = ((sitac == 1) & (individus.get("type_emploi", pd.Series(dtype=float)) == 1)).astype(int)
    individus["est_informel"] = (
        (individus.get("formalite_unite", pd.Series(dtype=float)) == 2) |
        (individus.get("formalite_emploi", pd.Series(dtype=float)) == 2)
    ).astype(int)

    agg = individus.groupby("id_men").agg(
        nb_occupes   =("est_occupe",  "sum"),
        nb_salaries  =("est_salarie", "sum"),
        nb_informels =("est_informel","sum"),
    ).reset_index()
    agg["a_actif_occupe"]  = (agg["nb_occupes"] > 0).astype(int)

    # Ratio de dependance
    if "nb_membres" in individus.columns:
        mem = individus[["id_men", "nb_membres"]].drop_duplicates("id_men")
        agg = agg.merge(mem, on="id_men", how="left")
        agg["ratio_dependance"] = np.where(
            agg["nb_occupes"] > 0,
            (agg["nb_membres"] - agg["nb_occupes"]) / agg["nb_occupes"],
            np.nan,
        )

    # --- Table menages
    men, _ = pyreadstat.read_dta(SOURCES["menages"])
    menages = men.merge(agg, on="id_men", how="left")

    qc_men = pd.DataFrame({
        "controle": [
            "menages sans identifiant",
            "occupes > membres du menage",
            "a_actif_occupe=1 mais nb_occupes=0",
        ],
        "nombre": [
            int(menages["id_men"].isna().sum()),
            int(((menages.get("nb_membres", pd.Series(dtype=float)) < menages["nb_occupes"]) & menages["nb_occupes"].notna()).sum()),
            int(((menages["a_actif_occupe"] == 1) & (menages["nb_occupes"] == 0)).sum()),
        ],
        "detail": ["doit valoir 0", "incoherence a verifier", "doit valoir 0"],
    })
    qc_men.to_csv(f"{DOSSIER_OUT}/qc_consolidation_menages.csv", index=False)

    # Estimations finales
    w = menages["poids"]
    e_tail  = np.average(menages["taille_menage"].fillna(0), weights=w) if "taille_menage" in menages.columns else np.nan
    e_dep   = np.average(menages["ratio_dependance"].fillna(0), weights=w) if "ratio_dependance" in menages.columns else np.nan
    e_act   = np.average((menages["a_actif_occupe"] == 1).astype(float), weights=w) * 100
    e_femcm = np.average((menages["sexe_cm"] == 2).astype(float), weights=w) * 100

    est = pd.DataFrame({
        "indicateur": ["Taille moyenne du menage", "Ratio de dependance moyen",
                       "Part menages avec actif occupe (%)", "Part menages diriges par une femme (%)"],
        "valeur":     [round(e_tail, 2), round(e_dep, 2), round(e_act, 2), round(e_femcm, 2)],
    })
    est.to_csv(f"{DOSSIER_OUT}/estimations_consolidation.csv", index=False)

    pyreadstat.write_dta(menages, f"{DOSSIER_OUT}/menages_consolide.dta", version=118)
    print(f"menages_consolide.dta  : {menages.shape[0]:,} menages")
    print(f"Termine en {round(time.time() - debut)}s.")


if __name__ == "__main__":
    main()
