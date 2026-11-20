# Louisiana BLS Data Explorer

A Streamlit app for exploring Bureau of Labor Statistics data, focused on Louisiana and its
parishes, metros and custom regions, with comparisons to other states and the U.S.

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Pages

| Page | What it does |
|---|---|
| **Latest Release** (home) | The newest QCEW quarter: Louisiana KPIs, parish map, metro growth, statewide industry movers, state ranking, and your watchlists. Detects new BLS releases automatically. |
| **Region Overview** | Lightcast-style economy overview for any geography: KPIs, monthly trend, industry table at any NAICS level (with LQ, YoY, wages), growth/decline, specialization bubble chart, shift-share, and a parish map. |
| **Industry Snapshot** | One industry (any NAICS code) across Louisiana parishes, metros, all states and the U.S., with maps, rankings, trend and drill-down. |
| **Compare Regions** | Louisiana vs. neighbors/peers, or any mix of parishes, metros, regions and states. Headline table, industry-mix heatmap (share/LQ/growth/wages), one-industry comparison, trends. |
| **Trend Builder** | Any QCEW series: monthly, quarterly or annual; employment, establishments, wages; level, index, change, or YoY; split regions into parishes; CSV export. |
| **Project Watch** | Tracks a group of parishes and industries against a pre-project baseline (preloaded: Richland Parish data center and neighbors). Monthly jobs, parish × industry change matrix, benchmarks vs. LA and U.S., wages, latest-quarter detail. Save your own watchlists. |
| **Labor Force & Jobs** | Monthly LAUS (unemployment, labor force) and CES (payroll jobs) from the BLS API, plus any BLS series ID. |
| **Data Notes & Help** | Definitions, suppression rules, metro definitions, setup. |

## Customize

Edit `bls_explorer/config.py`:
- `WATCHLIST_PRESETS`: named parish groups + industries + baseline for Project Watch
- `INDUSTRY_BUNDLES`: industry shortcuts (data centers, energy, manufacturing, ...)
- `RELEASE_SCHEDULE`: upcoming QCEW release dates shown in the app

Optional free BLS API key (raises monthly-series limits): add `BLS_API_KEY = "..."` to
`.streamlit/secrets.toml` or set the `BLS_API_KEY` environment variable.

## Code layout

```
app.py                     navigation + sidebar data status
bls_explorer/qcew.py       QCEW download, disk cache, suppression-aware aggregation, LQ
bls_explorer/geo.py        geographies (states, parishes, metros built from parishes, custom regions)
bls_explorer/blsapi.py     BLS Public Data API client (LAUS, CES, any series)
bls_explorer/ui.py         shared pickers, tables, charts, parish map
bls_explorer/views/        one module per page
```
