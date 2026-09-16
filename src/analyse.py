from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TABLES = ROOT / "outputs" / "tables"

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
            "2": "Artisans, commerçants et chefs d'entreprise",
            "3": "Cadres",
            "4": "Professions intermédiaires",
            "5": "Employés",
            "6": "Ouvriers",
            "7": "Retraités",
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
            "2": "Villes moyennes (20 000 à 100 000 hab.)",
            "3": "Grandes villes (> 100 000 hab.)",
            "4": "Agglomération parisienne",
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
            "5": "Autres ménages",
            "TOT": "Ensemble",
        },
    },
    "decile_de_niveau_de_vie": {
        "file": "TF106.csv",
        "column": "DECUC",
        "labels": {**{str(i): f"Décile {i}" for i in range(1, 11)}, "TOT": "Ensemble"},
    },
    "statut_d_occupation": {
        "file": "TF107.csv",
        "column": "STATUT",
        "keep": ["P", "L", "TOT"],
        "labels": {"P": "Propriétaires", "L": "Locataires", "TOT": "Ensemble"},
    },
}

CATEGORY_TITLES = {
    "age": "Âge de la personne de référence",
    "categorie_socioprofessionnelle": "Catégorie socioprofessionnelle",
    "lieu_de_residence": "Lieu de résidence",
    "type_de_menage": "Type de ménage",
    "decile_de_niveau_de_vie": "Décile de niveau de vie",
    "statut_d_occupation": "Statut d'occupation",
}

DIVISION_LABELS = {
    "01": "Alimentation et boissons non alcoolisées",
    "02": "Boissons alcoolisées et tabac",
    "03": "Habillement et chaussures",
    "04": "Logement, eau et énergie",
    "05": "Meubles et entretien du foyer",
    "06": "Santé",
    "07": "Transports",
    "08": "Information et communication",
    "09": "Loisirs et culture",
    "10": "Enseignement",
    "11": "Restauration et hébergement",
    "12": "Autres biens et services",
}

DIVISION_SHORT_LABELS = {
    "01": "Alimentation",
    "02": "Alcool-tabac",
    "03": "Habillement",
    "04": "Logement-énergie",
    "05": "Équipement du foyer",
    "06": "Santé",
    "07": "Transports",
    "08": "Information-communication",
    "09": "Loisirs-culture",
    "10": "Enseignement",
    "11": "Restauration-hébergement",
    "12": "Autres biens-services",
}

SHARE_COLUMNS = {code: f"spending_share_{code}_pct" for code in DIVISION_LABELS}


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


def build_comparison_table(results: pd.DataFrame, details: pd.DataFrame) -> pd.DataFrame:
    comparison = results[results["group_code"] != "TOT"].copy()
    comparison["dimension"] = comparison["category"].map(CATEGORY_TITLES)

    shares = details[details["group_code"] != "TOT"].pivot(
        index=["category", "group_code"],
        columns="division",
        values="budget_share",
    )
    shares = (shares * 100).rename(columns=SHARE_COLUMNS).reset_index()
    comparison = comparison.merge(shares, on=["category", "group_code"], how="left")
    order = {category: index for index, category in enumerate(CATEGORY_SPECS)}
    comparison["dimension_order"] = comparison["category"].map(order)
    comparison["display_order"] = -comparison["modeled_inflation"]
    is_decile = comparison["category"] == "decile_de_niveau_de_vie"
    comparison.loc[is_decile, "display_order"] = pd.to_numeric(
        comparison.loc[is_decile, "group_code"]
    )
    comparison = comparison.sort_values(
        ["dimension_order", "display_order", "group_label"],
        ascending=[True, True, True],
    )
    return comparison[
        [
            "category",
            "dimension",
            "group_code",
            "group_label",
            "modeled_inflation",
            "difference_vs_modeled_total",
            *SHARE_COLUMNS.values(),
        ]
    ].reset_index(drop=True)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def write_readable_results(
    comparison: pd.DataFrame,
    metadata: dict,
    division_rates: dict[str, float],
) -> None:
    official_rate = f"{metadata['official_headline_rate']:.2f}".replace(".", ",")
    modeled_rate = f"{metadata['modeled_total_rate_bdf2017']:.2f}".replace(".", ",")
    summary_rows = []
    for category in CATEGORY_SPECS:
        subset = comparison[comparison["category"] == category]
        highest = subset.loc[subset["modeled_inflation"].idxmax()]
        lowest = subset.loc[subset["modeled_inflation"].idxmin()]
        summary_rows.append(
            [
                CATEGORY_TITLES[category],
                f"{highest['group_label']} ({highest['modeled_inflation']:.2f} %)".replace(".", ","),
                f"{lowest['group_label']} ({lowest['modeled_inflation']:.2f} %)".replace(".", ","),
                f"{highest['modeled_inflation'] - lowest['modeled_inflation']:.2f} point".replace(".", ","),
            ]
        )

    detail_rows = []
    for row in comparison.itertuples():
        spending_shares = [
            f"{getattr(row, SHARE_COLUMNS[code]):.2f} %".replace(".", ",")
            for code in DIVISION_LABELS
        ]
        detail_rows.append(
            [
                row.dimension,
                row.group_label,
                f"{row.modeled_inflation:.2f} %".replace(".", ","),
                f"{row.difference_vs_modeled_total:+.2f} point".replace(".", ","),
                *spending_shares,
            ]
        )

    explanatory_headers = []
    for code in DIVISION_LABELS:
        rate = f"{division_rates[code]:+.2f} %".replace(".", ",")
        explanatory_headers.append(f"{DIVISION_SHORT_LABELS[code]} ({rate})")

    content = [
        "# Tableau comparatif de l'inflation différenciée",
        "",
        "Période: août 2025-août 2026. Calcul à paniers fixes à partir de l'enquête Budget de famille 2017 et de l'IPC Insee d'août 2026.",
        "",
        f"IPC officiel de l'ensemble des ménages: **{official_rate} %**. Panier moyen modélisé avec les pondérations BDF 2017: **{modeled_rate} %**.",
        "",
        "## Amplitude des écarts dans chaque dimension",
        "",
        markdown_table(
            ["Dimension", "Inflation la plus élevée", "Inflation la plus faible", "Écart"],
            summary_rows,
        ),
        "",
        "## Toutes les catégories",
        "",
        "**Définition des déciles:** ils partagent la distribution des niveaux de vie en dix groupes de même taille, classés du plus faible au plus élevé. Dans ce tableau, le décile 1 correspond aux 10 % situés en bas de la distribution et le décile 10 aux 10 % situés en haut.",
        "",
        "**Lecture des postes de dépenses:** le pourcentage entre parenthèses dans chaque en-tête est l'inflation nationale du poste entre août 2025 et août 2026. Les cellules indiquent la part de ce poste dans le budget 2017 du profil. Chaque ligne totalise 100 % sur les douze postes avant arrondi.",
        "",
        markdown_table(
            [
                "Dimension",
                "Catégorie",
                "Inflation modélisée",
                "Écart au panier moyen",
                *explanatory_headers,
            ],
            detail_rows,
        ),
        "",
        "## Lecture et limites",
        "",
        "Les catégories de dimensions différentes se recoupent: un même ménage peut être rural, locataire, ouvrier et appartenir à un décile de niveau de vie. La comparaison transversale sert donc à repérer les paniers les plus exposés, pas à additionner les effets.",
        "",
        "Ces estimations ne sont pas des indices catégoriels publiés par l'Insee. Elles mesurent uniquement l'effet de structures de consommation différentes, avec des paniers datant de 2017.",
        "",
    ]
    (ROOT / "RESULTATS.md").write_text("\n".join(content), encoding="utf-8")


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)

    divisions, ratios, metadata = load_price_ratios()
    all_results = []
    all_details = []
    for category, spec in CATEGORY_SPECS.items():
        result, detail = calculate_category(category, spec, ratios)
        all_results.append(result)
        all_details.append(detail)

    results = pd.concat(all_results, ignore_index=True)
    details = pd.concat(all_details, ignore_index=True)
    comparison = build_comparison_table(results, details)
    results.to_csv(TABLES / "inflation_par_categorie.csv", index=False)
    details.to_csv(TABLES / "contributions_detaillees.csv", index=False)
    comparison_export = comparison.copy()
    comparison_export["modeled_inflation"] = comparison_export["modeled_inflation"].round(2)
    comparison_export["difference_vs_modeled_total"] = comparison_export[
        "difference_vs_modeled_total"
    ].round(2)
    for column in SHARE_COLUMNS.values():
        comparison_export[column] = comparison_export[column].round(2)
    comparison_export.to_csv(TABLES / "tableau_comparatif.csv", index=False)

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
    division_rates = (
        details.groupby("division", sort=False)["division_rate"].first().to_dict()
    )
    write_readable_results(comparison, metadata, division_rates)

    display = comparison.copy()
    display["modeled_inflation"] = display["modeled_inflation"].round(3)
    display["difference_vs_modeled_total"] = display["difference_vs_modeled_total"].round(3)
    print(display[["dimension", "group_label", "modeled_inflation", "difference_vs_modeled_total"]].to_string(index=False))
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
