"""
Tests automatiques du bloc demographie/geographie
=================================================

Ce script relit la table produite par 03_demographie_geo.py et verifie une
serie d'invariants qui doivent tenir apres traitement. Chaque regle est ecrite
une seule fois, en clair. Si une regle dure est violee, le script le dit
franchement et se termine en erreur, ce qui rend une anomalie impossible a
ignorer. Les regles souples signalent des cas a surveiller sans faire echouer.

Utilisation (depuis la racine du depot) :
    python scripts/python/tests_demo_geo.py
"""

import os
import sys
import pyreadstat

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FICHIER = os.path.join(RACINE, "output", "SEN", "individus_demo_geo.dta")

# Age minimal a partir duquel la situation matrimoniale est posee.
AGE_MIN_MATRIMONIALE = 12


def charger():
    if not os.path.exists(FICHIER):
        print(f"ECHEC : fichier de sortie introuvable ({FICHIER}). "
              f"Le module 03_demographie_geo.py doit tourner d'abord.")
        sys.exit(1)
    df, _ = pyreadstat.read_dta(FICHIER)
    return df


class Rapport:
    """Petit collecteur de resultats, sans dependance externe."""

    def __init__(self):
        self.echecs_durs = 0
        self.alertes = 0

    def dur(self, nom, condition, detail=""):
        # condition vraie signifie que l'invariant tient.
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

    # 1) le sexe est complet et binaire
    r.dur("sexe sans manquant", df["sexe"].notna().all(),
          f"{int(df['sexe'].isna().sum())} manquant(s)")
    r.dur("sexe dans {1,2}", df["sexe"].dropna().isin([1, 2]).all())

    # 2) tout age manquant correspond a un age signale aberrant
    age_manquant_non_signale = int((df["age"].isna() & (df["flag_age_aberrant"] != 1)).sum())
    r.dur("age manquant uniquement si aberrant signale", age_manquant_non_signale == 0,
          f"{age_manquant_non_signale} manquant(s) non expliques")
    ages = df["age"].dropna()
    r.dur("age dans les bornes plausibles", ((ages >= 0) & (ages <= 110)).all())

    # 3) un et un seul chef de menage par menage
    nb_cm = df[df["lien_cm"] == 1].groupby("id_men").size()
    menages = df["id_men"].nunique()
    r.dur("un seul CM par menage",
          (nb_cm == 1).all() and len(nb_cm) == menages,
          f"{int((nb_cm != 1).sum())} menage(s) hors regle, "
          f"{menages - len(nb_cm)} sans CM")

    # 4) aucun marie en dessous de l'age matrimonial
    maries_jeunes = int((df["matrimoniale"].isin([2, 3])
                         & (df["age"] < AGE_MIN_MATRIMONIALE)).sum())
    r.dur("aucun marie sous l'age matrimonial", maries_jeunes == 0,
          f"{maries_jeunes} cas")

    # 5) region et milieu complets
    r.dur("region sans manquant", df["region"].notna().all())
    r.dur("milieu sans manquant", df["milieu"].notna().all())

    # 6) coherence matrimoniale / age : non applicable exactement sous l'age seuil
    na_hors_place = int(((df["matrimoniale"] == 0)
                         & (df["age"] >= AGE_MIN_MATRIMONIALE)).sum())
    r.dur("non applicable matrimonial reserve aux plus jeunes", na_hors_place == 0,
          f"{na_hors_place} cas de 12 ans et plus codes non applicable")

    # 7) coherence branche / niveau : branche nulle quand le niveau est aucun ou non applicable
    branche_incoherente = int(((df["niveau_etudes"].isin([0, 1]))
                               & (df["branche_etudes"] != 0)).sum())
    r.dur("branche coherente avec le niveau", branche_incoherente == 0,
          f"{branche_incoherente} cas")

    # 8) le groupe d'age suit l'age
    sous_15 = df[(df["age"].notna()) & (df["age"] < 15)]
    r.dur("groupe d'age coherent sous 15 ans",
          sous_15["groupe_age"].isin([1, 2, 3]).all())

    print("\nControles souples (a surveiller, sans echec)")

    # niveau superieur declare tres tot : possible mais rare, on le signale
    sup_jeune = int(((df["niveau_etudes"] == 6) & (df["age"] < 18)).sum())
    r.souple("peu ou pas de niveau superieur avant 18 ans", sup_jeune == 0,
             f"{sup_jeune} cas a verifier")

    # desaccords de sexe entre roster et emploi
    des = int(df["flag_sexe_incoherent"].sum())
    r.souple("peu de desaccords de sexe roster/emploi", des < 500,
             f"{des} desaccord(s)")

    return r


def main():
    print("Tests du bloc demographie/geographie")
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
