from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"

DIVISION_PATTERN = r"0[1-9]|1[0-2]"

CATEGORY_SPECS = {
    "age": {
        "file": "TF102.csv",
        "column": "AGPR",
        "labels": {
            "1": "Moins de 25 ans",
            "2": "25-34 ans",
            "3": "35-44 ans",
            "4": "45-54 ans",
            "5": "55-64 ans",
            "6": "65-74 ans",
            "7": "75 ans ou plus",
            "TOT": "Ensemble",
        },
    },
    "categorie_socioprofessionnelle": {
        "file": "TF103.csv",
        "column": "CSPR",
        "labels": {
            "1": "Agriculteurs",
            "2": "Artisans, commercants et chefs d'entreprise",
            "3": "Cadres",
            "4": "Professions intermediaires",
            "5": "Employes",
            "6": "Ouvriers",
            "7": "Retraites",
            "8": "Autres inactifs",
            "TOT": "Ensemble",
        },
    },
    "lieu_de_residence": {
        "file": "TF104.csv",
        "column": "STRATE",
        "labels": {
            "0": "Communes rurales",
            "1": "Petites villes (< 20 000 hab.)",
            "2": "Villes moyennes (20 000 a 100 000 hab.)",
            "3": "Grandes villes (> 100 000 hab.)",
            "4": "Agglomeration parisienne",
            "TOT": "Ensemble",
        },
    },
    "type_de_menage": {
        "file": "TF105.csv",
        "column": "TYPMEN",
        "labels": {
            "1": "Personnes seules",
            "2": "Familles monoparentales",
            "3": "Couples sans enfant",
            "4": "Couples avec enfants",
            "5": "Autres menages",
            "TOT": "Ensemble",
        },
    },
    "decile_de_niveau_de_vie": {
        "file": "TF106.csv",
        "column": "DECUC",
        "labels": {**{str(i): f"Decile {i}" for i in range(1, 11)}, "TOT": "Ensemble"},
    },
    "statut_d_occupation": {
        "file": "TF107.csv",
        "column": "STATUT",
        "keep": ["P", "L", "TOT"],
        "labels": {"P": "Proprietaires", "L": "Locataires", "TOT": "Ensemble"},
    },
}

DIVISION_LABELS = {
    "01": "Alimentation et boissons non alcoolisees",
    "02": "Boissons alcoolisees et tabac",
    "03": "Habillement et chaussures",
    "04": "Logement, eau et energie",
    "05": "Meubles et entretien du foyer",
    "06": "Sante",
    "07": "Transports",
    "08": "Information et communication",
    "09": "Loisirs et culture",
    "10": "Enseignement",
    "11": "Restauration et hebergement",
    "12": "Autres biens et services",
}


def load_price_ratios() -> tuple[pd.DataFrame, dict[str, float], dict]:
    """Charge les indices Insee d'aout 2026 et construit le pont COICOP."""
    path = RAW / "IPC_2026-08_detail.xls"
    ipc = pd.read_excel(path, dtype={0: str})
    ipc.columns = [
        "code",
        "label",
        "weight_2026",
        "index_2025_08",
        "index_2026_05",
        "index_2026_06",
        "index_2026_07",
        "index_2026_08",
        "monthly_rate",
        "quarterly_rate",
        "annual_rate_published",
    ]
    ipc["code"] = ipc["code"].astype(str).str.strip()
    divisions = ipc[ipc["code"].str.fullmatch(r"0[1-9]|1[0-3]", na=False)].copy()
    divisions["price_ratio"] = divisions["index_2026_08"] / divisions["index_2025_08"]
    divisions["annual_rate_exact"] = (divisions["price_ratio"] - 1) * 100

    ratios = dict(zip(divisions["code"], divisions["price_ratio"]))

    # eCOICOP v2 a scinde l'ancienne division 12 entre les nouvelles divisions
    # 12 et 13. Faute de ventilation BDF 2017 compatible, on les recombine avec
    # les ponderations nationales de l'IPC 2026.
    split = divisions[divisions["code"].isin(["12", "13"])].copy()
    ratios["12"] = float(
        (split["price_ratio"] * split["weight_2026"]).sum() / split["weight_2026"].sum()
    )

    headline = ipc.loc[ipc["code"] == "00"].iloc[0]
    metadata = {
        "price_month": "2026-08",
        "comparison_month": "2025-08",
        "official_headline_rate": float(headline["annual_rate_published"]),
        "official_headline_exact_from_indices": float(
            (headline["index_2026_08"] / headline["index_2025_08"] - 1) * 100
        ),
        "bridge_old_division_12_rate": (ratios["12"] - 1) * 100,
    }
    return divisions, ratios, metadata


def calculate_category(category: str, spec: dict, ratios: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    key = spec["column"]
    bdf = pd.read_csv(
        RAW / spec["file"],
        sep=";",
        dtype={"NOMENCLATURE": str, key: str},
    )
    bdf = bdf[bdf["NOMENCLATURE"].str.fullmatch(DIVISION_PATTERN, na=False)].copy()
    if "keep" in spec:
        bdf = bdf[bdf[key].isin(spec["keep"])].copy()

    bdf["price_ratio"] = bdf["NOMENCLATURE"].map(ratios)
    if bdf["price_ratio"].isna().any():
        missing = sorted(bdf.loc[bdf["price_ratio"].isna(), "NOMENCLATURE"].unique())
        raise ValueError(f"Divisions sans indice de prix: {missing}")

    bdf["budget_total"] = bdf.groupby(key)["CONSO"].transform("sum")
    bdf["budget_share"] = bdf["CONSO"] / bdf["budget_total"]
    bdf["division_rate"] = (bdf["price_ratio"] - 1) * 100
    bdf["contribution_points"] = bdf["budget_share"] * bdf["division_rate"]
    bdf["category"] = category
    bdf["group_code"] = bdf[key]
    bdf["group_label"] = bdf[key].map(spec["labels"]).fillna(bdf[key])
    bdf["division_label"] = bdf["NOMENCLATURE"].map(DIVISION_LABELS)

    detail = bdf[
        [
            "category",
            "group_code",
            "group_label",
            "NOMENCLATURE",
            "division_label",
            "CONSO",
            "budget_share",
            "division_rate",
            "contribution_points",
        ]
    ].rename(columns={"NOMENCLATURE": "division", "CONSO": "annual_spending_euros_2017"})

    result = (
        detail.groupby(["category", "group_code", "group_label"], as_index=False)
        .agg(
            modeled_inflation=("contribution_points", "sum"),
            annual_spending_euros_2017=("annual_spending_euros_2017", "sum"),
            budget_share_sum=("budget_share", "sum"),
        )
    )
    reference = float(result.loc[result["group_code"] == "TOT", "modeled_inflation"].iloc[0])
    result["difference_vs_modeled_total"] = result["modeled_inflation"] - reference
    return result, detail


def plot_category(results: pd.DataFrame, category: str, filename: str, title: str) -> None:
    data = results[(results["category"] == category) & (results["group_code"] != "TOT")].copy()
    data = data.sort_values("modeled_inflation", ascending=True)
    fig, ax = plt.subplots(figsize=(10, max(4.8, 0.52 * len(data))))
    colors = ["#b2182b" if x > 0 else "#2166ac" for x in data["difference_vs_modeled_total"]]
    bars = ax.barh(data["group_label"], data["modeled_inflation"], color=colors)
    reference = float(results.loc[(results["category"] == category) & (results["group_code"] == "TOT"), "modeled_inflation"].iloc[0])
    ax.axvline(reference, color="#333333", linestyle="--", linewidth=1.4, label=f"Panier moyen modelise: {reference:.2f}%")
    ax.bar_label(bars, labels=[f"{v:.2f}%" for v in data["modeled_inflation"]], padding=4)
    ax.set_title(title, loc="left", fontweight="bold")
    ax.set_xlabel("Hausse des prix entre aout 2025 et aout 2026")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", alpha=0.2)
    ax.legend(frameon=False, loc="lower right", bbox_to_anchor=(1, 1.01))
    fig.text(0.01, 0.01, "Calcul reproductible a partir de donnees Insee. Paniers BDF 2017, prix IPC aout 2026.", fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIGURES / filename, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_rural_paris_contributions(details: pd.DataFrame) -> None:
    data = details[details["category"] == "lieu_de_residence"]
    pivot = data.pivot(index=["division", "division_label"], columns="group_code", values="contribution_points")
    pivot["difference"] = pivot["0"] - pivot["4"]
    pivot = pivot.sort_values("difference")
    fig, ax = plt.subplots(figsize=(10, 6.5))
    colors = ["#b2182b" if x > 0 else "#2166ac" for x in pivot["difference"]]
    bars = ax.barh(pivot.index.get_level_values("division_label"), pivot["difference"], color=colors)
    ax.axvline(0, color="#333333", linewidth=0.8)
    ax.bar_label(bars, labels=[f"{v:+.2f}" for v in pivot["difference"]], padding=3, fontsize=8)
    ax.set_title("Ce qui creuse ou reduit l'ecart rural-Paris", loc="left", fontweight="bold")
    ax.set_xlabel("Contribution a l'ecart d'inflation, en point")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", alpha=0.2)
    fig.text(0.01, 0.01, "Lecture: une valeur positive accroît l'inflation modelisee des communes rurales par rapport a Paris.", fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIGURES / "contributions_ecart_rural_paris.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    divisions, ratios, metadata = load_price_ratios()
    all_results = []
    all_details = []
    for category, spec in CATEGORY_SPECS.items():
        result, detail = calculate_category(category, spec, ratios)
        all_results.append(result)
        all_details.append(detail)

    results = pd.concat(all_results, ignore_index=True)
    details = pd.concat(all_details, ignore_index=True)
    results.to_csv(TABLES / "inflation_par_categorie.csv", index=False)
    details.to_csv(TABLES / "contributions_detaillees.csv", index=False)

    bridge = divisions[
        ["code", "label", "weight_2026", "index_2025_08", "index_2026_08", "annual_rate_exact"]
    ].copy()
    bridge.to_csv(TABLES / "indices_insee_divisions.csv", index=False)

    modeled_total = float(
        results.loc[
            (results["category"] == "lieu_de_residence") & (results["group_code"] == "TOT"),
            "modeled_inflation",
        ].iloc[0]
    )
    metadata["modeled_total_rate_bdf2017"] = modeled_total
    metadata["difference_model_vs_official"] = modeled_total - metadata["official_headline_exact_from_indices"]
    (TABLES / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    plot_category(
        results,
        "lieu_de_residence",
        "inflation_lieu_de_residence.png",
        "Inflation modelisee selon le lieu de residence",
    )
    plot_category(
        results,
        "decile_de_niveau_de_vie",
        "inflation_decile_niveau_de_vie.png",
        "Inflation modelisee selon le decile de niveau de vie",
    )
    plot_rural_paris_contributions(details)

    display = results[results["group_code"] != "TOT"].copy()
    display["modeled_inflation"] = display["modeled_inflation"].round(3)
    display["difference_vs_modeled_total"] = display["difference_vs_modeled_total"].round(3)
    print(display[["category", "group_label", "modeled_inflation", "difference_vs_modeled_total"]].to_string(index=False))
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
