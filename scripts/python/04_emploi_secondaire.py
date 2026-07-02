"""
ERI-ESI -- Module emploi secondaire
Usage : python scripts/python/04_emploi_secondaire.py
"""

import time
import pyreadstat
import pandas as pd
import numpy as np

PAYS        = "SEN"
DOSSIER_OUT = f"output/{PAYS}"
SORTIE      = f"{DOSSIER_OUT}/emploi_secondaire.dta"
HEURES_MAX  = 98
REVENU_MIN  = 1_000
REVENU_MAX  = 5_000_000

TRANCHES = {
    1: 17_500,  2: 67_500,  3: 125_000, 4: 175_000, 5: 225_000,
    6: 275_000, 7: 325_000, 8: 375_000, 9: 425_000, 10: 475_000,
    11: 525_000, 12: 575_000, 13: 625_000, 14: 675_000, 15: 725_000,
    16: 775_000, 17: 825_000, 18: 875_000, 19: 950_000, 20: 1_125_000,
    21: 1_375_000, 22: 1_750_000, 23: 2_250_000, 24: 2_750_000, 25: 3_000_000,
}


def revenu_mensuel(row):
    mode = row.get("AS10A_AS1")
    brut = row.get("AS10B_AS1")
    code = row.get("AS10C_AS1")
    tranche = TRANCHES.get(code)
    if mode == 1 and pd.notna(brut):
        return brut
    if mode == 2 and pd.notna(brut):
        return brut / 12
    if mode == 3 and tranche is not None:
        return tranche
    if mode == 4 and tranche is not None:
        return tranche / 12
    return np.nan


def main():
    debut = time.time()

    base, _ = pyreadstat.read_dta(f"{DOSSIER_OUT}/base_individus_emploi_fusionnee.dta")
    print(f"Base chargee : {base.shape[0]:,} lignes")

    df = base[["hh1", "hh2", "m1", "weightemploy"]].copy()
    df.rename(columns={"hh1": "id_grappe", "hh2": "id_menage",
                       "m1": "id_ordre", "weightemploy": "poids_emploi"}, inplace=True)
    df["id_men"] = df["id_grappe"].astype(str) + "_" + df["id_menage"].astype(str)

    df["a_emploi_secondaire"] = base["AS1A"].map({1: 1, 2: 0})
    df["nb_emplois_sec"]      = base["AS1B1"]
    df["nb_emplois_sec_grp"]  = base["AS1B1"].apply(
        lambda x: 1 if x == 1 else (2 if pd.notna(x) and x >= 2 else np.nan)
    )

    df["statut_emploi_sec"] = base["AS4_AS1"]
    df["type_emploi_sec"]   = base["AS4_AS1"].apply(
        lambda x: 1 if x in [1,2,3,4,5,6,10] else (2 if x in [7,8,9] else np.nan)
    )

    df["secteur_isic_sec_brut"]        = base["AS3S1_OLD"]
    df["flag_secteur_ancien_codage"]   = base["AS3S1_OLD"].notna().astype("Int8")

    # AS9C en minutes/jour, AS9B en jours/semaine
    heures = (base["AS9C_AS1"] / 60) * base["AS9B_AS1"]
    df["heures_semaine_sec"]   = heures
    df["flag_heures_sec_abt"]  = (heures > HEURES_MAX).astype("Int8")
    df.loc[df["flag_heures_sec_abt"] == 1, "heures_semaine_sec"] = np.nan

    df["revenu_sec_mensuel"] = base.apply(revenu_mensuel, axis=1)
    df["flag_revenu_sec_abt"] = (
        df["revenu_sec_mensuel"].notna() &
        ((df["revenu_sec_mensuel"] < REVENU_MIN) | (df["revenu_sec_mensuel"] > REVENU_MAX))
    ).astype("Int8")
    df.loc[df["flag_revenu_sec_abt"] == 1, "revenu_sec_mensuel"] = np.nan

    crit = base[["AS7B_AS1_A1", "AS7B_AS1_B1", "AS7B_AS1_C1"]].notna().all(axis=1)
    formel = crit & (base["AS7B_AS1_A1"] == 1) & (base["AS7B_AS1_B1"] == 1) & (base["AS7B_AS1_C1"] == 1)
    df["formalite_emploi_sec"] = np.where(formel, 1, np.where(crit, 2, np.nan))

    # Controles
    qc = {
        "emploi_sec=1 mais statut manquant":    int((df["a_emploi_secondaire"]==1) & df["statut_emploi_sec"].isna()).sum() if False else int(((df["a_emploi_secondaire"]==1) & df["statut_emploi_sec"].isna()).sum()),
        "emploi_sec=0 mais statut renseigne":   int(((df["a_emploi_secondaire"]==0) & df["statut_emploi_sec"].notna()).sum()),
        "heures aberrantes neutralisees":        int((df["flag_heures_sec_abt"]==1).sum()),
        "revenu aberrant neutralise":            int((df["flag_revenu_sec_abt"]==1).sum()),
    }
    pd.DataFrame(qc.items(), columns=["controle", "nombre"]).to_csv(
        f"{DOSSIER_OUT}/qc_emploi_secondaire.csv", index=False
    )

    # Estimations
    mask = df["poids_emploi"].notna()
    w = df.loc[mask, "poids_emploi"]
    taux_sec = np.average(df.loc[mask, "a_emploi_secondaire"].fillna(0), weights=w) * 100
    mask2 = mask & (df["a_emploi_secondaire"] == 1)
    rev_moy = np.average(df.loc[mask2, "revenu_sec_mensuel"].fillna(0), weights=df.loc[mask2, "poids_emploi"]) if mask2.any() else np.nan
    h_moy   = np.average(df.loc[mask2, "heures_semaine_sec"].fillna(0), weights=df.loc[mask2, "poids_emploi"]) if mask2.any() else np.nan

    est = pd.DataFrame({
        "indicateur": ["Taux avec emploi secondaire (%)", "Revenu mensuel moyen emploi secondaire (FCFA)", "Heures moyennes par semaine emploi secondaire"],
        "valeur":     [round(taux_sec, 2), round(rev_moy, 2), round(h_moy, 2)],
    })
    est.to_csv(f"{DOSSIER_OUT}/estimations_emploi_secondaire.csv", index=False)

    pyreadstat.write_dta(df, SORTIE, version=118)
    print(f"Sortie : {SORTIE} ({df.shape[0]:,} lignes)")
    print(f"Termine en {round(time.time() - debut)}s.")


if __name__ == "__main__":
    main()
