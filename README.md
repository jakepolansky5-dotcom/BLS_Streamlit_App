# Louisiana BLS Data Explorer

A Streamlit app for exploring Bureau of Labor Statistics data, focused on Louisiana and its
parishes, metros and custom regions, with comparisons to other states and the U.S.

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Pages

**Where we are today (monthly LAUS & CES):** these lead the app.

| Page | What it does |
|---|---|
| **Monthly Snapshot** (home) | Latest LAUS + CES: LA unemployment vs. U.S., nonfarm jobs by sector, parish unemployment map, metro jobs and unemployment, all-state rankings, watchlist parishes. |
| **Monthly Data Explorer** | Payroll jobs (CES) for many regions × many industries at once; unemployment/labor force (LAUS) for any regions (custom regions are summed from parishes); any BLS series ID. Level, index, 12-month change or %. |
| **Project Watch** | A parish group vs. a baseline (preloaded: Richland Parish data center and neighbors). Opens with current LAUS/CES conditions, then QCEW jobs, wages and industry detail. Baseline picker on the page; saveable watchlists. |

**Detailed jobs & wages (QCEW):** full industry and parish detail, about 5–6 months behind.

| Page | What it does |
|---|---|
| **Latest QCEW Release** | The newest QCEW quarter: Louisiana KPIs, parish map, metro growth, industry movers, state ranking, watchlists. Detects new releases automatically. |
| **Region Overview** | Current monthly conditions, then a Lightcast-style QCEW overview: industry table at any NAICS level (LQ, YoY, wages), growth/decline, specialization, shift-share, parish map. |
| **Industry Snapshot** | One NAICS industry across parishes, metros, all states and the U.S. |
| **Compare Regions** | Monthly conditions side by side, then QCEW headline table, industry-mix heatmap and trends. |
| **Trend Builder** | Any QCEW series: monthly, quarterly or annual; index, change or YoY; CSV export. |
| **Data Notes & Help** | Definitions, suppression rules, metro definitions, setup. |

## Customize

Edit `bls_explorer/config.py`:
- `WATCHLIST_PRESETS`: named parish groups + industries + baseline for Project Watch
- `INDUSTRY_BUNDLES`: industry shortcuts (data centers, energy, manufacturing, ...)
- `RELEASE_SCHEDULE`: upcoming QCEW release dates shown in the app

**BLS API key** (strongly recommended, free at data.bls.gov/registrationEngine): on Streamlit Community Cloud,
add `BLS_API_KEY = "your-key"` under the app's **Settings → Secrets**. Locally, put the same line in
`.streamlit/secrets.toml` (git-ignored). Never commit the key to the code.

## Code layout

```
app.py                     navigation + sidebar data status
bls_explorer/qcew.py       QCEW download, disk cache, suppression-aware aggregation, LQ
bls_explorer/geo.py        geographies (states, parishes, metros built from parishes, custom regions)
bls_explorer/blsapi.py     BLS Public Data API client (LAUS, CES, any series)
bls_explorer/ui.py         shared pickers, tables, charts, parish map
bls_explorer/views/        one module per page
```
