Work in progress.

- Source: 337,818 rows, 2000-01-01 – 2023-03-06, 6,545 titles
- id unique per row (title + day), not per movie; title + date unique; 0 duplicates
- theaters: 161 nulls; distributor: 225 nulls + 7,419 "-" placeholders → NULL
- 63 rows with revenue = 0
- Revenue in USD (checked: Avengers: Endgame opening day ≈ $157M)

- Title ≠ movie: remakes share titles (The Kid 2000/2019, Hellboy 2004/2019)
- Split titles into screening runs: new run when gap > 365 days → 6,634 runs
- Revenue check: stg_revenue = stg_series = 205,110,995,141

- 341 titles with glued release suffixes (Total Recall2012 Re-release, Titanic2012 3D Release)
- Regex strips suffix at end of title only: 336/341 cleaned, 0 other titles changed
- TODO: Titanic25 Year Anniversary, Blade RunnerThe Final Cut (2007 re-release)
- TODO: broken characters (Lu00e9on Morin)

- OMDb: one query per run, type=movie
- Match: exact year → year − 1 (festival premiere before US release)
- Re-releases: no year (OMDb uses original year)
- Normal movies never without year (The Kid → Chaplin 1921)
- Raw responses in data/omdb_raw.json; if file exists, no API calls
- Matched: 98.4% of revenue, TODO% of runs; unmatched = small titles, live events

- Star schema, grain: one row per movie per day
- fact_daily_revenue: id (PK), movie_key, date, revenue, theaters, distributor
- dim_movie: movie_key (surrogate), imdb_id, title, release_year, rated, runtime, genre, country, type
- dim_date: date (PK), day, weekday, month, quarter, year, weekend
- Movie identity: imdb_id, else title + release_year; re-releases merge by imdb_id
- distributor in fact (no own attributes, changes between runs)
- theaters semi-additive
- genre as string (limitation; bridge table = next step)
