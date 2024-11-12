# swisslaw-scraping

## Importing into DB
```shell
poetry run import-db output/chromadb output/law_vectors.jsonl
```

## Requests examples

```shell
poetry run search-db output/chromadb "résiliation de bail anticipé"
```

```shell
poetry run search-tf-idf output/law_articles.jsonl.gz "résiliation de bail anticipé"
```

```text
"Diffamation publique,Injure publique,Outrage,Trouble à l'ordre public,Atteinte à la dignité: Conséquences juridiques et sanctions pénales pour injure publique, diffamation et trouble à l'ordre public dans le cadre d'un conflit de voisinage avec témoins. Éléments constitutifs de l'infraction d'outrage et d'atteinte à la dignité en cas d'insultes proférées en public."

"Quelles sont les conséquences légales, en termes de responsabilité civile et pénale, et les risques encourus pour une personne qui, dans un accès de colère, insulte publiquement un voisin, en criant et en présence de témoins ? Ce comportement constitue-t-il une injure publique ou une atteinte à l'honneur, et quelles sont les sanctions potentielles (amendes, dommages et intérêts, peine) ou poursuites en matière de droit civil ou pénal ?"
```

## Extracting relevant links for downloading laws in xml format later on

```shell
poetry run scrape-links
```

## Downloading current laws in XML format

```shell
poetry run load-laws
```
