"""
ERI-ESI : graphiques d'analyse exploratoire - bloc emploi principal
====================================================================

Role
----
Ce script est separe de 03_emploi_principal.py : il ne refait aucun
nettoyage, il lit uniquement les fichiers deja produits
(emploi_principal.dta, estimations_emploi_principal.csv) et genere des
graphiques PNG. Optionnel par rapport au livrable principal (table +
QAQC), utile pour l'analyse exploratoire et la note methodologique.

Sortie : PNG dans output/SEN/graphiques_emploi_principal/

Auteure : Aissatou Gueye
"""

import os
import sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import missingno as msno
import pyreadstat

plt.style.use("ggplot")
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#333333",
    "axes.titleweight": "bold",
    "axes.titlesize": 13,
    "font.size": 10,
})

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

CONFIG = {
    "dossier_output": os.path.join(RACINE, "output", "SEN"),
    "fichier_table": "emploi_principal.dta",
    "dossier_graphiques": "graphiques_emploi_principal",
}


def charger_donnees(cfg):
    chemin = os.path.join(cfg["dossier_output"], cfg["fichier_table"])
    if not os.path.exists(chemin):
        raise FileNotFoundError(
            f"{chemin} introuvable. Lancer d'abord 03_emploi_principal.py."
        )
    df, meta = pyreadstat.read_dta(chemin)
    # applique les libelles de valeurs pour un affichage lisible sur les graphiques
    for col in df.columns:
        labels = meta.variable_value_labels.get(col)
        if labels:
            df[col] = df[col].map(labels)
    return df


def graphique_barres(df, colonne, titre, chemin_fichier):
    effectifs = df[colonne].dropna().value_counts()
    fig, ax = plt.subplots(figsize=(7, 4))
    effectifs.plot(kind="bar", ax=ax, color="#4C72B0")
    ax.set_title(titre)
    ax.set_xlabel("")
    ax.set_ylabel("Nombre d'individus")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(chemin_fichier, dpi=120)
    plt.close(fig)


def graphique_histogramme(serie, titre, chemin_fichier, ligne_bornee=None, note=None):
    fig, ax = plt.subplots(figsize=(7, 4))
    serie.dropna().plot(kind="hist", bins=40, ax=ax, color="#55A868")
    if ligne_bornee is not None:
        ax.axvline(ligne_bornee, color="red", linestyle="--", label="borne de plausibilite")
        ax.legend()
    ax.set_title(titre)
    if note:
        fig.text(0.01, 0.01, note, fontsize=8, color="gray")
    fig.tight_layout()
    fig.savefig(chemin_fichier, dpi=120)
    plt.close(fig)


def graphique_boxplot(df, colonne_valeur, colonne_groupe, titre, chemin_fichier):
    sous_df = df[[colonne_valeur, colonne_groupe]].dropna()
    groupes = sous_df.groupby(colonne_groupe)[colonne_valeur]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.boxplot([g.values for _, g in groupes], tick_labels=[str(k) for k, _ in groupes], showfliers=False)
    ax.set_title(titre)
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(chemin_fichier, dpi=120)
    plt.close(fig)


def graphique_manquants_matrice(df, variables, chemin_fichier):
    """Matrice de nullite (type missingno/naniar/VIM::aggr) : une ligne par
    individu, une colonne par variable, blanc = manquant. Montre d'un coup
    d'oeil les motifs de manquant communs entre variables (ex : tout le
    bloc AP vide ensemble pour les non-occupes)."""
    ax = msno.matrix(df[variables], figsize=(9, 5), fontsize=10, sparkline=True)
    ax.set_title("Matrice de nullite - bloc emploi principal\n"
                  "(blanc = manquant, ligne = un individu)", fontsize=13, fontweight="bold")
    fig = ax.get_figure()
    fig.tight_layout()
    fig.savefig(chemin_fichier, dpi=120, bbox_inches="tight")
    plt.close(fig)


def graphique_manquants_structurel_vs_reel(df, chemin_fichier):
    """Barres horizontales en %, structurel vs reel, par variable - le
    manquant reel est mis en evidence par une etiquette de valeur (les
    volumes sont trop desequilibres pour rester lisibles en barres brutes)."""
    # situation_activite_grp (pas situation_activite) : libelles construits
    # par nous ("Actif occupe", sans accent), fiables pour la comparaison -
    # situation_activite reprend le libelle source accentue ("Actif occupé"),
    # source d'un bug de comparaison detecte a la relecture des graphiques.
    occupe = df["situation_activite_grp"] == "Actif occupe"
    variables = ["statut_emploi", "secteur_isic_principal", "heures_semaine_principal",
                 "revenu_principal_mensuel_fcfa", "formalite_unite", "formalite_emploi"]

    lignes = []
    for var in variables:
        manquant = df[var].isna()
        reel = int((occupe & manquant).sum())
        structurel = int((~occupe & manquant).sum())
        total = len(df)
        lignes.append({"variable": var, "structurel_pct": 100 * structurel / total,
                        "reel_pct": 100 * reel / total, "reel_n": reel})

    resume = pd.DataFrame(lignes).set_index("variable")
    fig, ax = plt.subplots(figsize=(8, 5))
    resume[["structurel_pct", "reel_pct"]].plot(
        kind="barh", stacked=True, ax=ax, color=["#B0B0B0", "#C44E52"],
        legend=True)
    ax.legend(["Manquant structurel", "Manquant reel"], loc="lower right")
    for i, (var, row) in enumerate(resume.iterrows()):
        ax.annotate(f"n={row['reel_n']}", xy=(100.5, i), va="center", fontsize=8, color="#C44E52")
    ax.set_xlim(0, 110)
    ax.set_title("Manquants structurels vs reels par variable (%)")
    ax.set_xlabel("% des individus (n=120 693)")
    fig.tight_layout()
    fig.savefig(chemin_fichier, dpi=120)
    plt.close(fig)


def main():
    cfg = CONFIG
    print("Graphiques - bloc emploi principal")
    print("-" * 64)

    df = charger_donnees(cfg)
    dossier_sortie = os.path.join(cfg["dossier_output"], cfg["dossier_graphiques"])
    os.makedirs(dossier_sortie, exist_ok=True)

    def chemin(nom):
        return os.path.join(dossier_sortie, nom)

    graphique_barres(df, "situation_activite_grp", "Situation d'activite", chemin("01_situation_activite.png"))
    graphique_barres(df, "type_emploi", "Type d'emploi (salarie/independant)", chemin("02_type_emploi.png"))
    graphique_barres(df, "secteur_isic_principal_4cat", "Secteur d'activite (4 familles)", chemin("03_secteur_4cat.png"))
    graphique_barres(df, "formalite_unite", "Formalite de l'unite", chemin("04_formalite_unite.png"))
    graphique_barres(df, "formalite_emploi", "Formalite de l'emploi (salaries)", chemin("05_formalite_emploi.png"))

    graphique_histogramme(
        df["revenu_principal_mensuel_fcfa"], "Revenu mensuel consolide (FCFA), apres nettoyage",
        chemin("06_revenu_histogramme.png"),
        note="Valeurs hors bornes [1000 ; 5 000 000] deja neutralisees (cf. qc_emploi_principal.csv)")

    graphique_histogramme(
        df["heures_semaine_principal"], "Heures travaillees par semaine, apres nettoyage",
        chemin("07_heures_histogramme.png"), ligne_bornee=98,
        note="Valeurs >98h/semaine deja neutralisees (cf. qc_emploi_principal.csv)")

    graphique_boxplot(df, "revenu_principal_mensuel_fcfa", "secteur_isic_principal_4cat",
                       "Revenu par secteur d'activite", chemin("08_revenu_par_secteur.png"))
    graphique_boxplot(df, "revenu_principal_mensuel_fcfa", "type_emploi",
                       "Revenu par type d'emploi", chemin("09_revenu_par_type_emploi.png"))
    graphique_boxplot(df, "heures_semaine_principal", "type_emploi",
                       "Heures de travail par type d'emploi", chemin("10_heures_par_type_emploi.png"))

    variables_bloc = ["statut_emploi", "secteur_isic_principal", "heures_semaine_principal",
                      "revenu_principal_mensuel_fcfa", "formalite_unite", "formalite_emploi"]
    graphique_manquants_matrice(df, variables_bloc, chemin("11_manquants_matrice.png"))
    graphique_manquants_structurel_vs_reel(df, chemin("12_manquants_structurel_vs_reel.png"))

    print(f"Graphiques ecrits dans : {dossier_sortie}")
    print("Termine.")


if __name__ == "__main__":
    sys.exit(main())
