"""
Etape 2 : fusion individus <-> emploi sur les cles de menage/individu.
Produit la base de travail individuelle complete (avant derivation des
variables thematiques par chaque membre du groupe).
Usage : python 02_merge.py [PAYS]
"""

import sys
import pandas as pd

from config import OUTPUT_DIR, get_config, PAYS_ACTIF
from importlib import import_module

extract = import_module("01_extract")


def fusionner(pays: str = PAYS_ACTIF) -> pd.DataFrame:
    cfg = get_config(pays)
    data = extract.extraire(pays)

    df = data["individus"].merge(
        data["emploi"],
        left_on=cfg["cles_individus"],
        right_on=cfg["cles_emploi"],
        how="left",
        suffixes=("", "_emploi"),
        indicator=True,
    )

    print(df["_merge"].value_counts())
    non_appaires = (df["_merge"] != "both").sum()
    if non_appaires:
        print(f"ATTENTION : {non_appaires} individus sans donnees emploi appariees.")

    df = df.drop(columns=["_merge"])

    dossier_sortie = OUTPUT_DIR / pays
    dossier_sortie.mkdir(parents=True, exist_ok=True)
    chemin = dossier_sortie / "base_individus_emploi_fusionnee.csv"
    df.to_csv(chemin, index=False)
    print(f"Base fusionnee ecrite dans : {chemin} ({df.shape})")

    return df


if __name__ == "__main__":
    pays = sys.argv[1] if len(sys.argv) > 1 else PAYS_ACTIF
    fusionner(pays)
