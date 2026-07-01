"""
Profil visuel du bloc demographie/geographie
============================================

Ce script relit la table produite et dessine deux figures qui donnent a voir la
qualite et la forme des donnees traitees : une pyramide des ages ponderee, et la
repartition du niveau d'etudes selon le milieu de residence. Les figures sont
enregistrees en image, pretes a etre glissees dans un rapport.

Utilisation (depuis la racine du depot) :
    python scripts/python/profil_demo_geo.py
"""

import os
import sys
import numpy as np
import pyreadstat

import matplotlib
matplotlib.use("Agg")  # rendu sans ecran, adapte a une execution en ligne de commande
import matplotlib.pyplot as plt

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOSSIER = os.path.join(RACINE, "output", "SEN")
FICHIER = os.path.join(DOSSIER, "individus_demo_geo.dta")
SORTIE = os.path.join(DOSSIER, "profil_demo_geo.png")

# Palette sobre, dans l'esprit d'un rapport institutionnel.
BLEU = "#3b6ea5"
CORAIL = "#c66b5a"
DEGRADE = ["#e9eef4", "#c7d4e4", "#9fb6d2", "#6f92bb", "#4a6fa0", "#2f4d78", "#1d3357"]

GROUPES = {1: "0-4", 2: "5-9", 3: "10-14", 4: "15-24",
           5: "25-34", 6: "35-49", 7: "50-64", 8: "65+"}
NIVEAUX = {0: "Non applicable", 1: "Aucun", 2: "Prescolaire", 3: "Primaire",
           4: "Secondaire 1er cycle", 5: "Secondaire 2nd cycle", 6: "Superieur"}
MILIEUX = {1: "Urbain", 2: "Rural"}


def charger():
    if not os.path.exists(FICHIER):
        print(f"Fichier de sortie introuvable ({FICHIER}). "
              f"Le module 03_demographie_geo.py doit tourner d'abord.")
        sys.exit(1)
    df, _ = pyreadstat.read_dta(FICHIER)
    df["poids"] = df["poids"].fillna(0)
    return df


def pyramide_des_ages(ax, df):
    """Population ponderee par groupe d'age, hommes a gauche, femmes a droite."""
    codes = sorted(GROUPES)
    hommes, femmes = [], []
    for c in codes:
        hommes.append(df.loc[(df["groupe_age"] == c) & (df["sexe"] == 1), "poids"].sum())
        femmes.append(df.loc[(df["groupe_age"] == c) & (df["sexe"] == 2), "poids"].sum())

    total = df["poids"].sum()
    hommes = [-h / total * 100 for h in hommes]  # a gauche, en pourcentage de la population
    femmes = [f / total * 100 for f in femmes]
    y = np.arange(len(codes))

    ax.barh(y, hommes, color=BLEU, label="Hommes")
    ax.barh(y, femmes, color=CORAIL, label="Femmes")
    ax.set_yticks(y)
    ax.set_yticklabels([GROUPES[c] for c in codes])
    ax.set_xlabel("Part de la population (%)")
    ax.set_title("Pyramide des ages (ponderee)")
    limite = max(max(abs(min(hommes)), max(femmes)) * 1.15, 1)
    ax.set_xlim(-limite, limite)
    ticks = ax.get_xticks()
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{abs(t):.0f}" for t in ticks])
    ax.set_xlim(-limite, limite)
    ax.axvline(0, color="#888", linewidth=0.8)
    ax.legend(loc="lower right", frameon=False)
    ax.grid(axis="x", linewidth=0.3, alpha=0.4)


def niveau_par_milieu(ax, df):
    """Repartition ponderee du niveau d'etudes selon le milieu, en barres empilees."""
    codes_niveau = sorted(NIVEAUX)
    milieux = [1, 2]
    x = np.arange(len(milieux))
    bas = np.zeros(len(milieux))

    for i, niv in enumerate(codes_niveau):
        parts = []
        for mil in milieux:
            masque_mil = df["milieu"] == mil
            total_mil = df.loc[masque_mil, "poids"].sum()
            part = df.loc[masque_mil & (df["niveau_etudes"] == niv), "poids"].sum()
            parts.append(part / total_mil * 100 if total_mil else 0)
        ax.bar(x, parts, bottom=bas, color=DEGRADE[i % len(DEGRADE)], label=NIVEAUX[niv])
        bas += np.array(parts)

    ax.set_xticks(x)
    ax.set_xticklabels([MILIEUX[m] for m in milieux])
    ax.set_ylabel("Part au sein du milieu (%)")
    ax.set_title("Niveau d'etudes selon le milieu")
    ax.set_ylim(0, 100)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12),
              ncol=3, frameon=False, fontsize=8)
    ax.grid(axis="y", linewidth=0.3, alpha=0.4)


def main():
    df = charger()
    fig, (g, d) = plt.subplots(1, 2, figsize=(13, 6))
    fig.suptitle("Profil demographique et geographique (Senegal, ERI-ESI 2017)",
                 fontsize=13, fontweight="bold")
    pyramide_des_ages(g, df)
    niveau_par_milieu(d, df)
    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    fig.savefig(SORTIE, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Profil visuel ecrit : {SORTIE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
