"""
ERI-ESI -- Point d'entree unique du pipeline
Usage : python run.py           (lance le pipeline Stata via subprocess)
        python run.py --python  (lance le pipeline Python natif)
"""

import subprocess
import time
import sys
from pathlib import Path

STATA = r"C:\Program Files\Stata18\StataBE-64.exe"

SCRIPTS_STATA = [
    "scripts/stata/01_fusion.do",
    "scripts/stata/03_demographie_geo.do",
    "scripts/stata/03_emploi_principal.do",
    "scripts/stata/04_emploi_secondaire.do",
    "scripts/stata/05_menages.do",
    "scripts/stata/06_consolidation.do",
]

SCRIPTS_PYTHON = [
    "scripts/python/01_fusion.py",
    "scripts/python/03_demographie_geo.py",
    "scripts/python/03_emploi_principal.py",
    "scripts/python/04_emploi_secondaire.py",
    "scripts/python/05_menages.py",
    "scripts/python/06_consolidation.py",
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


def run_python_script(script: str) -> bool:
    print(f"  -> {script}")
    result = subprocess.run([sys.executable, script], capture_output=False, text=True)
    if result.returncode != 0:
        print(f"     ERREUR (code {result.returncode})")
        return False
    return True


def main():
    racine = Path(__file__).parent
    mode_python = "--python" in sys.argv

    print(f"Pipeline ERI-ESI 2017 -- repertoire : {racine}")

    if mode_python:
        print("Mode : Python natif\n")
        debut = time.time()
        for script in SCRIPTS_PYTHON:
            if not run_python_script(script):
                sys.exit(f"Pipeline interrompu sur {script}.")
    else:
        if not Path(STATA).exists():
            sys.exit(f"Stata introuvable : {STATA}")
        print("Mode : Stata (batch)\n")
        debut = time.time()
        for script in SCRIPTS_STATA:
            if not run_script(script):
                sys.exit(f"Pipeline interrompu sur {script}.")

    duree = round(time.time() - debut)
    print(f"\nPipeline termine en {duree} secondes.")
    print("Tables produites dans output/SEN/ :")
    print("  individus_consolide.dta")
    print("  menages_consolide.dta")


if __name__ == "__main__":
    main()
