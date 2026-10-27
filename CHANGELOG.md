# Changelog

## v1.0 (2026-10-27)

First public version. The pipeline itself was built between 24 and 28 September 2026 (see commit history).

- README: data sources with attribution, project origin, roadmap
- ER diagram as Mermaid in the README, generated from the actual schema (the old image showed `movie_identity` as the key instead of the surrogate `movie_key`)
- Source file renamed to `data/revenues_per_day.csv`
- Notebook runs top to bottom without an API key or network access: the cells that demo the OMDb API are skipped when no key is set
- Verified from a clean environment: notebook rebuilds `data/movies.duckdb` with the same row counts and revenue totals as documented, and the dashboard renders without errors
