# Inflation differenciee en France, actualisation Insee 2026

Ce depot reprend la logique du projet `memoireESCP`, mais remplace les indices Eurostat par les indices des prix a la consommation de l'Insee. Il estime la hausse des prix subie par differents profils de menages entre aout 2025 et aout 2026, a structure de consommation constante.

Le resultat central est le fichier **[`RESULTATS.md`](RESULTATS.md)**, lisible directement sur GitHub. Il regroupe toutes les categories dans un tableau unique et compare aussi l'amplitude des ecarts pour chaque dimension. Une version exploitable dans un tableur est disponible dans **[`outputs/tables/tableau_comparatif.csv`](outputs/tables/tableau_comparatif.csv)**.

[![Ouvrir dans Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rm951/inflationDifferenciee2026/blob/main/notebooks/analyse_insee_2026.ipynb)

Le bouton ci-dessus ouvre le notebook dans Google Colab. Dans Colab, choisir `Exécution` puis `Tout exécuter`: le dépôt et la dépendance nécessaire à la lecture des fichiers Insee sont chargés automatiquement.

## Resultat principal

Avec les paniers de l'enquete Budget de famille 2017, la hausse des prix modelisee atteint environ:

- **2,66 % pour les menages des communes rurales**;
- **2,50 % dans l'agglomeration parisienne**;
- soit un ecart de **0,16 point**.

Le transport creuse l'ecart rural-Paris d'environ 0,37 point. Le logement et l'energie le reduisent d'environ 0,27 point.

Ces chiffres sont des calculs reproductibles a partir de donnees Insee, et non des indices categoriels publies par l'Insee. L'IPC officiel pour l'ensemble des menages augmente de 2,4 % sur la meme periode.

## Categories calculees

- age de la personne de reference;
- categorie socioprofessionnelle;
- categorie de la commune de residence;
- type de menage;
- decile de niveau de vie;
- proprietaires et locataires.

## Methode

Le calcul conserve l'idee du notebook `Figure07.ipynb`:

1. selectionner les depenses annuelles moyennes de chaque groupe dans Budget de famille 2017;
2. convertir ces depenses en parts de budget;
3. appliquer les variations nationales de l'IPC Insee a chaque division de consommation;
4. additionner les contributions pour obtenir une inflation propre au panier du groupe;
5. comparer chaque groupe au panier moyen construit avec la meme methode.

Le calcul est realise au niveau des divisions COICOP. Ce choix permet un raccord integral et controlable entre Budget de famille 2017 et l'eCOICOP v2 utilisee par l'IPC depuis janvier 2026.

La nouvelle nomenclature a scinde l'ancienne division 12 entre les divisions 12 et 13. Le code les recombine avec leurs ponderations nationales dans l'IPC 2026. Cette approximation est documentee dans le code et dans `SOURCES.md`.

## Reproduire l'analyse

### En ligne avec Google Colab

Cliquer sur le bouton `Ouvrir dans Google Colab` en haut de cette page, puis sur `Exécution` > `Tout exécuter`. Aucun téléchargement ni environnement Python local n'est nécessaire.

### En local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/analyse.py
python -m nbconvert --to notebook --execute notebooks/analyse_insee_2026.ipynb --inplace
```

Les tableaux sont ecrits dans `outputs/tables/`. L'analyse ne genere pas de graphiques.

## Prudence editoriale

Formulation recommandee: "Selon un calcul realise a partir des structures de consommation de l'Insee en 2017 et de ses indices de prix d'aout 2026..."

Ne pas presenter ces estimations comme une mesure des ecarts locaux de prix ou comme un indice officiel de l'Insee. Les paniers datent de 2017 et ne captent pas les adaptations de consommation depuis cette date.

La categorie "rural" est celle du tableau TF104 de Budget de famille 2017. Elle ne doit pas etre confondue avec une classification territoriale plus recente fondee sur la grille communale de densite.
