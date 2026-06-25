"""
Etape 1 : extraction brute des fichiers .dta vers des DataFrames pandas.
Usage : python 01_extract.py [PAYS]
"""

import sys
import pandas as pd

from config import INPUT_DIR, get_config, PAYS_ACTIF


def extraire(pays: str = PAYS_ACTIF) -> dict:
    cfg = get_config(pays)
    dossier = INPUT_DIR / pays

    df_individus = pd.read_stata(
        dossier / cfg["fichier_individus"], convert_categoricals=False
    )
    df_emploi = pd.read_stata(
        dossier / cfg["fichier_emploi"], convert_categoricals=False
    )

    print(f"[{pays}] individus : {df_individus.shape}")
    print(f"[{pays}] emploi    : {df_emploi.shape}")

    return {"individus": df_individus, "emploi": df_emploi}


if __name__ == "__main__":
    pays = sys.argv[1] if len(sys.argv) > 1 else PAYS_ACTIF
    extraire(pays)
