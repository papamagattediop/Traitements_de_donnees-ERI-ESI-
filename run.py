"""
ERI-ESI -- Point d'entree unique du pipeline (lanceur Stata via Python)
Usage : python run.py
"""

import subprocess
import time
import sys
from pathlib import Path

STATA = r"C:\Program Files\Stata18\StataBE-64.exe"

SCRIPTS = [
    "scripts/stata/01_fusion.do",
    "scripts/stata/03_demographie_geo.do",
    "scripts/stata/03_emploi_principal.do",
    "scripts/stata/04_emploi_secondaire.do",
    "scripts/stata/05_menages.do",
    "scripts/stata/06_consolidation.do",
]


def run_script(script: str) -> bool:
    print(f"  -> {script}")
    result = subprocess.run(
        [STATA, "-e", "do", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"     ERREUR (code {result.returncode})")
        return False
    return True


def main():
    racine = Path(__file__).parent
    if Path(STATA).exists() is False:
        sys.exit(f"Stata introuvable : {STATA}")

    print(f"Pipeline ERI-ESI 2017 -- repertoire : {racine}\n")
    debut = time.time()

    for script in SCRIPTS:
        ok = run_script(script)
        if not ok:
            sys.exit(f"Pipeline interrompu sur {script}.")

    duree = round(time.time() - debut)
    print(f"\nPipeline termine en {duree} secondes.")
    print("Tables produites dans output/SEN/ :")
    print("  individus_consolide.dta")
    print("  menages_consolide.dta")


if __name__ == "__main__":
    main()
