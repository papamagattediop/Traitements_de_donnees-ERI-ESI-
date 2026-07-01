"""
Tests automatiques du bloc emploi principal
============================================

Ce script relit la table produite par 03_emploi_principal.py et verifie une
serie d'invariants qui doivent tenir apres traitement. Meme convention que
tests_demo_geo.py (Personne 2) : chaque regle est ecrite une seule fois, en
clair. Si une regle dure est violee, le script le dit franchement et se
termine en erreur. Les regles souples signalent des cas a surveiller sans
faire echouer.

Utilisation (depuis la racine du depot) :
    python scripts/python/tests_emploi_principal.py
"""

import os
import sys
import pyreadstat

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FICHIER = os.path.join(RACINE, "output", "SEN", "emploi_principal.dta")

HEURES_MAX = 98
REVENU_MIN = 1000
REVENU_MAX = 5000000


def charger():
    if not os.path.exists(FICHIER):
        print(f"ECHEC : fichier de sortie introuvable ({FICHIER}). "
              f"Le module 03_emploi_principal.py doit tourner d'abord.")
        sys.exit(1)
    df, _ = pyreadstat.read_dta(FICHIER)
    return df


class Rapport:
    """Petit collecteur de resultats, sans dependance externe."""

    def __init__(self):
        self.echecs_durs = 0
        self.alertes = 0

    def dur(self, nom, condition, detail=""):
        if condition:
            print(f"  OK    {nom}")
        else:
            self.echecs_durs += 1
            print(f"  ECHEC {nom}" + (f" -> {detail}" if detail else ""))

    def souple(self, nom, condition, detail=""):
        if condition:
            print(f"  OK    {nom}")
        else:
            self.alertes += 1
            print(f"  ALERTE {nom}" + (f" -> {detail}" if detail else ""))


def lancer_tests(df):
    r = Rapport()
    print("Invariants durs (doivent tenir absolument)")

    # 1) pas de doublon d'identifiant individu
    doublons = int(df.duplicated(subset=["id_grappe", "id_menage", "id_ordre"]).sum())
    r.dur("pas de doublon d'identifiant individu", doublons == 0, f"{doublons} doublon(s)")

    # 2) eligible_module_emploi coherent avec la presence du poids emploi
    incoherent_eligibilite = int(((df["eligible_module_emploi"] == 1) & df["poids_emploi"].isna()).sum())
    r.dur("eligible au module emploi implique poids_emploi renseigne",
          incoherent_eligibilite == 0, f"{incoherent_eligibilite} cas")

    # 3) type_emploi dans {1,2} quand renseigne
    r.dur("type_emploi dans {1,2}", df["type_emploi"].dropna().isin([1, 2]).all())

    # 4) secteur_isic_principal_4cat dans {1,2,3,4} quand renseigne
    r.dur("secteur_isic_principal_4cat dans {1,2,3,4}",
          df["secteur_isic_principal_4cat"].dropna().isin([1, 2, 3, 4]).all())

    # 5) formalite_unite et formalite_emploi dans {1,2} quand renseignes
    r.dur("formalite_unite dans {1,2}", df["formalite_unite"].dropna().isin([1, 2]).all())
    r.dur("formalite_emploi dans {1,2}", df["formalite_emploi"].dropna().isin([1, 2]).all())

    # 6) heures et revenu dans les bornes de plausibilite deja appliquees
    heures = df["heures_semaine_principal"].dropna()
    r.dur("heures dans les bornes [0 ; 98]", ((heures >= 0) & (heures <= HEURES_MAX)).all())
    revenu = df["revenu_principal_mensuel_fcfa"].dropna()
    r.dur("revenu dans les bornes [1000 ; 5000000]",
          ((revenu >= REVENU_MIN) & (revenu <= REVENU_MAX)).all())

    # 7) flags binaires stricts
    for col in ["flag_heures_aberrantes", "flag_ecart_heures", "flag_revenu_non_renseigne",
                "flag_revenu_aberrant", "flag_travail_enfant_10_14"]:
        r.dur(f"{col} strictement binaire (0/1)", df[col].dropna().isin([0, 1]).all())

    # 8) statut_emploi renseigne chez un non-occupe ADULTE = vraie anomalie
    #    (le travail des enfants 10-14 ans est un cas legitime distinct, cf.
    #    flag_travail_enfant_10_14 et docs/note_emploi_principal.md)
    non_occupe = df["situation_activite"] != 1
    anomalie_adulte = int((non_occupe & df["statut_emploi"].notna()
                          & (df["flag_travail_enfant_10_14"] == 0)).sum())
    r.dur("statut_emploi renseigne chez non-occupe adulte : doit etre nul",
          anomalie_adulte == 0, f"{anomalie_adulte} cas")

    print("\nControles souples (a surveiller, sans echec)")

    # occupes sans statut_emploi : un residu connu et documente (1 cas verifie)
    occupe = df["situation_activite"] == 1
    sans_statut = int((occupe & df["statut_emploi"].isna()).sum())
    r.souple("occupes sans statut_emploi quasi nul", sans_statut <= 5,
             f"{sans_statut} cas (cf. controles_coherence, residu connu)")

    # ecart heures declarees/calculees : eleve mais documente (absence de pause dejeuner)
    part_ecart = df["flag_ecart_heures"].mean() * 100
    r.souple("part d'ecart heures documentee (<70%)", part_ecart < 70,
             f"{part_ecart:.1f}% (limite connue, cf. note methodologique)")

    return r


def main():
    print("Tests du bloc emploi principal")
    print("-" * 48)
    df = charger()
    r = lancer_tests(df)

    print("-" * 48)
    print(f"Echecs durs : {r.echecs_durs} | Alertes : {r.alertes}")
    if r.echecs_durs:
        print("Resultat : des invariants sont violes, la sortie n'est pas valide.")
        return 1
    print("Resultat : tous les invariants tiennent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
