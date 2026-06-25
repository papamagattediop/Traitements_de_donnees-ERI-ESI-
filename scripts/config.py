"""
Configuration du pipeline ERI-ESI.
Pour adapter a un autre pays : dupliquer le bloc PAYS_CONFIG ci-dessous
avec un nouveau code pays, sans toucher au reste du pipeline.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
DOCS_DIR = ROOT / "docs"

PAYS_CONFIG = {
    "SEN": {
        "fichier_individus": "individus_TP.dta",
        "fichier_emploi": "emploi_Tp.dta",
        "cles_individus": ["hh1", "hh2", "M1"],
        "cles_emploi": ["hh1", "hh2", "m1"],
    },
    # "CIV": { ... a completer pour un autre pays ... }
}

PAYS_ACTIF = "SEN"


def get_config(pays: str = PAYS_ACTIF) -> dict:
    if pays not in PAYS_CONFIG:
        raise KeyError(f"Pays '{pays}' non configure dans PAYS_CONFIG.")
    return PAYS_CONFIG[pays]
