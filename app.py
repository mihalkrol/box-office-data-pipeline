"""US box office rankings dashboard.

Reads the star schema from data/movies.duckdb (built by the notebook):
fact_revenue, dim_movie, dim_date.

Run from the repository root:
    streamlit run app.py
Close the notebook's DuckDB connection first (con.close() or restart the kernel):
DuckDB allows one writing process OR several read-only ones, not both.
"""

import altair as alt
import duckdb
import streamlit as st

DB_PATH = "data/movies.duckdb"
ACCENT = "#8E1B2E"      # cinema curtain red
MUTED = "#B9B4AE"       # neutral for context bars
WARNING = "#D9A441"     # highlight for special periods

st.set_page_config(page_title="US Box Office 2000–2023", layout="wide")


@st.cache_resource
def get_connection():
    return duckdb.connect(DB_PATH, read_only=True)


@st.cache_data
def query(sql, params=None):
    return get_connection().execute(sql, params or []).df()


try:
    get_connection()
except duckdb.Error as e:
    st.error(
        f"Could not open {DB_PATH}. Run the notebook first to build the database, "
        f"then close its connection (con.close() or restart the kernel).\n\nDetails: {e}"
    )
    st.stop()


# --- Header ------------------------------------------------------------------
st.title("US box office, 2000–2023")
st.caption(
    "Daily US box office revenue per movie, enriched with OMDb metadata. "
    "All amounts are revenue (box office gross) in USD, not profit."
)

kpi = query("""
    SELECT
        SUM(r.revenue)                                                  AS total_revenue,
        COUNT(DISTINCT r.movie_key)                                     AS movies,
        SUM(CASE WHEN m.imdbID IS NOT NULL THEN r.revenue END)
            / SUM(r.revenue)                                            AS matched_share
    FROM fact_revenue r
    JOIN dim_movie m ON m.movie_key = r.movie_key
""").iloc[0]

c1, c2, c3 = st.columns(3)
c1.metric("Total revenue", f"${kpi.total_revenue / 1e9:,.1f} B")
c2.metric("Movies", f"{kpi.movies:,.0f}")
c3.metric("Revenue with OMDb metadata", f"{kpi.matched_share:.1%}")

st.divider()


# --- 1. Top 10 movies ----------------------------------------------------------
st.subheader("Top 10 movies by total revenue")

top = query("""
    SELECT
        m.title,
        MIN(m.release_year)            AS release_year,
        m.genre,
        SUM(r.revenue) / 1000000       AS revenue_mln
    FROM fact_revenue r
    JOIN dim_movie m ON m.movie_key = r.movie_key
    GROUP BY m.movie_key, m.title, m.genre
    ORDER BY revenue_mln DESC
    LIMIT 10
""")
top.insert(0, "rank", range(1, len(top) + 1))

st.dataframe(
    top,
    hide_index=True,
    width="stretch",
    column_config={
        "rank": st.column_config.NumberColumn("#", width="small"),
        "title": "Movie",
        "release_year": st.column_config.NumberColumn("Year", format="%d"),
        "genre": "Genre",
        "revenue_mln": st.column_config.ProgressColumn(
            "Revenue (USD M)",
            format="$%.0f M",
            min_value=0,
            max_value=float(top.revenue_mln.max()),
        ),
    },
)

st.divider()


# --- 2. Revenue per calendar year ---------------------------------------------
st.subheader("Revenue per calendar year")

by_year = query("""
    SELECT d.year, SUM(r.revenue) / 1e9 AS revenue_bn
    FROM fact_revenue r
    JOIN dim_date d ON d.date = r.date
    GROUP BY d.year
    ORDER BY d.year
""")
by_year["period"] = "Full year"
by_year.loc[by_year.year.isin([2020, 2021]), "period"] = "COVID closures"
by_year.loc[by_year.year == 2023, "period"] = "Partial year (to 6 Mar)"

year_chart = (
    alt.Chart(by_year)
    .mark_bar()
    .encode(
        x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("revenue_bn:Q", title="Revenue (USD B)"),
        color=alt.Color(
            "period:N",
            title=None,
            scale=alt.Scale(
                domain=["Full year", "COVID closures", "Partial year (to 6 Mar)"],
                range=[ACCENT, WARNING, MUTED],
            ),
            legend=alt.Legend(orient="top"),
        ),
        tooltip=[alt.Tooltip("year:O", title="Year"),
                 alt.Tooltip("revenue_bn:Q", title="USD B", format=".2f")],
    )
    .properties(height=320)
)
st.altair_chart(year_chart, width="stretch")
st.caption(
    "Revenue is assigned to the year the money came in, not the movie's release year. "
    "No revenue at all was recorded on 28 Mar – 2 Apr 2020 (US cinema closures)."
)

st.divider()


# --- 3. Average revenue per movie by release year ------------------------------
st.subheader("Average revenue per movie, by release year")

per_release = query("""
    SELECT
        m.release_year,
        SUM(r.revenue) / COUNT(DISTINCT r.movie_key) / 1e6 AS avg_revenue_mln,
        COUNT(DISTINCT r.movie_key)                        AS movies
    FROM fact_revenue r
    JOIN dim_movie m ON m.movie_key = r.movie_key
    WHERE m.release_year BETWEEN 2000 AND 2023
    GROUP BY m.release_year
    ORDER BY m.release_year
""")

st.altair_chart(
    alt.Chart(per_release)
    .mark_bar(color=ACCENT)
    .encode(
        x=alt.X("release_year:O", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("avg_revenue_mln:Q", title="Average revenue per movie (USD M)"),
        tooltip=[alt.Tooltip("release_year:O", title="Release year"),
                 alt.Tooltip("avg_revenue_mln:Q", title="USD M", format=".1f"),
                 alt.Tooltip("movies:Q", title="Movies")],
    )
    .properties(height=320),
    width="stretch",
)
st.caption(
    "Note: the source contains few movies released in 2000–2001 (under 100 per year, "
    "compared with 200–600 in later years), mostly large releases, so averages for those years are inflated."
)

st.divider()


# --- 4. Where do the top 100 movies come from? ---------------------------------
st.subheader("Top 100 movies: US and non-US productions")

top100 = query("""
    WITH sum_rev AS (
        SELECT movie_key, SUM(revenue) AS revenue
        FROM fact_revenue
        GROUP BY movie_key
        ORDER BY revenue DESC
        LIMIT 100
    )
    SELECT
        ROW_NUMBER() OVER (ORDER BY sr.revenue DESC) AS rank,
        m.title,
        m.country,
        sr.revenue / 1e6 AS revenue_mln,
        CASE WHEN m.country IS NULL THEN NULL
             WHEN m.country ILIKE '%United States%' THEN 1 ELSE 0 END AS us_involved,
        CASE WHEN m.country IS NULL THEN NULL
             WHEN m.country ILIKE 'United States%'  THEN 1 ELSE 0 END AS us_first
    FROM sum_rev sr
    JOIN dim_movie m ON m.movie_key = sr.movie_key
""")

# flags are 1 / 0 / NULL; NULL (no OMDb metadata) is counted in neither group
no_us = int((top100.us_involved == 0).sum())
not_first = top100[top100.us_first == 0]

m1, m2 = st.columns(2)
m1.metric("Without any US production country", f"{no_us} of 100")
m2.metric("Where the US is not the first listed country", f"{len(not_first)} of 100")

st.dataframe(
    not_first[["rank", "title", "country", "revenue_mln"]],
    hide_index=True,
    width="stretch",
    column_config={
        "rank": st.column_config.NumberColumn("#", width="small"),
        "title": "Movie",
        "country": "Countries (OMDb order)",
        "revenue_mln": st.column_config.NumberColumn("Revenue (USD M)", format="$%.0f M"),
    },
)
st.caption(
    "OMDb lists several countries for co-productions. Two rules are shown because the answer "
    "depends on the definition. Movies without OMDb metadata are not counted in either rule."
)

st.divider()


# --- 5. Day of the week -------------------------------------------------------
st.subheader("Average revenue per day of the week")

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
HIGHLIGHT = ["Friday", "Saturday", "Sunday"]

by_day = query("""
    SELECT
        d.day_of_week,
        SUM(r.revenue) / COUNT(DISTINCT d.date) / 1e6  AS avg_revenue_per_day_mln
    FROM fact_revenue r
    JOIN dim_date d ON d.date = r.date
    GROUP BY d.day_of_week
""")
by_day["group"] = by_day.day_of_week.apply(lambda d: "Friday–Sunday" if d in HIGHLIGHT else "Monday–Thursday")

base = alt.Chart(by_day).encode(
    x=alt.X("day_of_week:N", sort=DAYS, title=None,
            axis=alt.Axis(labelAngle=0, labelOverlap=False, labelLimit=200)),
    y=alt.Y("avg_revenue_per_day_mln:Q", title="Average revenue per day (USD M)"),
)
bars = base.mark_bar().encode(
    color=alt.Color(
        "group:N",
        title=None,
        scale=alt.Scale(domain=["Friday–Sunday", "Monday–Thursday"], range=[ACCENT, MUTED]),
        legend=alt.Legend(orient="top"),
    ),
    tooltip=[alt.Tooltip("day_of_week:N", title="Day"),
             alt.Tooltip("avg_revenue_per_day_mln:Q", title="USD M", format=".1f")],
)
labels = base.mark_text(dy=-8, fontSize=12).encode(
    text=alt.Text("avg_revenue_per_day_mln:Q", format="$.1f")
)
st.altair_chart((bars + labels).properties(height=320), width="stretch")
st.caption("Total revenue per day of the week divided by the number of such days, so days are compared fairly.")