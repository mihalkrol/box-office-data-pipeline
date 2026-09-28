# Movie revenue pipeline (OMDb)

Daily US box office revenue per movie, enriched with OMDb metadata, modeled as a star schema in DuckDB, with a Streamlit dashboard on top.

Stack: Python, pandas, DuckDB, requests, Streamlit.

## How to run

1. `python3 -m venv .venv`, `source .venv/bin/activate`, `pip install -r requirements.txt`
2. Source file is included in data/revenues_per_day_fm.csv (data provided by Future Mind for this task)
3. Run `pipeline.ipynb` top to bottom. It builds `data/movies.duckdb`.
4. In the terminal: `streamlit run app.py`

Run in VS Code or Jupyter.

OMDb responses are saved in `data/omdb_raw.json`. If the file exists, there is no API connection, so no API key is needed. To query the API again, delete the file and put your own key in `.env` as `API_KEY=...` (full run ~33 min).

The notebook closes the DuckDB connection at the end. DuckDB allows one writing process or several reading ones, so the dashboard can't open the database while the notebook holds it.

## Pipeline

csv → raw_revenues → stg_revenue → stg_series → OMDb API → omdb_raw.json → stg_omdb → dim_movie, dim_date, fact_revenue → dashboard

## Data exploration

- 337,818 rows, 6,545 unique titles, dates 2000-01-01 to 2023-03-06
- 0.05% nulls in theaters. Distributor: 225 nulls plus 7,419 rows with "-" as a placeholder, so 2.3% missing after labeling them correctly.
- Avengers: Endgame earned $157M on opening day, which is true, so revenue is in USD. There are 63 rows with 0 USD.
- id is unique for title and day, not for distinct movies.
- Some movies are remakes and some are re-releases, so a title is not a movie (The Kid 2000 and 2019, Hellboy 2004 and 2019).

## Staging

stg_revenue: one row per movie per day.
- series_number: if there is no previous date, or the gap is larger than a year (365 days), the screening ended and we treat it as another run. It's a hypothesis, checked later with OMDb.
- base_title: some titles are labeled with a year and "Re-release" or "Anniversary" (Maurice2017 Re-release, The Polar Express2005 IMAX Release). 341 titles have "release" or "anniversary" in the name. A regex removes the label only at the end of the title, so it can be used for the OMDb search.
- distributor "-" replaced with NULL.

stg_series: one row per screening run, 6,634 runs. Sum of revenue is the same in stg_revenue and stg_series (205,110,995,141).

## OMDb enrichment

- One query per run, using type "movie" to avoid other types (series, episodes).
- If it's a re-release: title without year (OMDb knows the original year).
- Otherwise: title and year, and if the year doesn't work, year - 1 (premiere dates, festivals).
- Normal movies are never searched without a year: The Kid without a year returns Chaplin's 1921 film.
- stg_omdb: 'N/A' replaced with nulls, numbers cast from strings.
- 6,185 of 6,634 runs matched (93.2%), and 98.4% of revenue is from movies matched with an IMDb ID. The 449 unmatched runs are 6.8% of runs but only 1.6% of revenue, so they are mostly small titles.

## Data model

Diagram: er_futuremind.jpg

Star schema. Grain of the fact: one row per movie per day.

- fact_revenue: id (PK), movie_key (FK), date (FK), revenue, theaters, distributor
- dim_movie: movie_key (PK), movie_identity, imdbID, title, release_year, rated, runtime, genre, country, imdb_rating
- dim_date: date (PK), day_of_month, day_of_week, month, quarter, year, is_weekend (generated, not from the csv)

Decisions:
- Movie identity: imdbID if possible, else title + release_year. Runs with the same imdbID (re-releases) become one movie. 6,634 runs → 6,521 movies, 6,072 with imdbID.
- movie_key is a surrogate key (ROW_NUMBER). Identity has two formats and can change after better matching, so the fact points to a number. It's consistent because everything is rebuilt on each run.
- distributor stays in the fact (degenerate dimension): no other attributes, and it can change between runs of the same movie.
- theaters is semi-additive: sum across movies on one day, not across days.
- genre and country stay as strings (lists like "Action, Drama").

Checks:
- stg_revenue has the same number of rows as the source (337,818), no "-" left in distributor
- The Kid splits into 2 runs (2000 and 2019)
- same revenue sum in stg_revenue, stg_series and fact_revenue (205,110,995,141)
- same number of records in fact_revenue and stg_revenue (337,818)
- movie_identity and imdbID are unique in dim_movie
- dim_date has 8,466 days, the data has 8,455. 11 dates have no revenue at all, 6 of them are 28 Mar - 2 Apr 2020 (US cinema closures)

## Dashboard

- Top 10 movies by total revenue
- Revenue per calendar year (2020-2021 COVID, 2023 only until 6 March)
- Average revenue per movie by release year. 2000-2001 look highest, but the source has only 85 and 110 movies from those years, compared with 200+ later (mostly big releases early on), so it's a data coverage effect, not a trend.
- Top 100: not even one movie without United States in countries. If we only count the first listed country, 18 movies are not US.
- Average revenue per day of the week: Saturday ~$47.5M, Friday and Sunday $33-39M, Monday-Thursday $12-14M.

## Limitations

- genre and country as strings, no bridge table
- 1.6% of revenue without OMDb metadata
- the regex covers the main label patterns, a few unusual labels may remain
- the 365-day gap for splitting runs is an assumption

## Use of AI

I used Claude (Anthropic) as a mentor during this task: to explain concepts (gaps and islands, surrogate keys, semi-additive measures), to help with syntax (the regex for release labels, DuckDB functions) and to review my notebook. The Streamlit dashboard code was written with Claude, based on my SQL queries. The data exploration, the data model and the decisions described above are mine, and I can explain every step of the pipeline.