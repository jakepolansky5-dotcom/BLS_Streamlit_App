# LA Top Jobs (demo)

A simple static site that shows K-12 students the top projected jobs in Louisiana, in kid-friendly language.

Open `index.html` in a browser. No server or build step is needed to view it.

## Publishing on Streamlit Community Cloud

`top_jobs_app.py` (repo root) serves this page full-screen as its own Streamlit app, separate from the
BLS explorer (`app.py`). In share.streamlit.io: **Create app → Deploy a public app from GitHub**, pick this repo
and branch, set **Main file path** to `top_jobs_app.py`, and choose a URL. No secrets are needed: the app reads the
committed `data.js` and makes no API calls. To update numbers, run `build_data.py`, commit `data.js`, and the app
picks it up on the next push. Test locally with `streamlit run top_jobs_app.py`.

## Files

| File | What it is |
|---|---|
| `index.html` | The page: layout, styles and rendering. |
| `occupations.csv` | The 91 careers in "Browse all in-demand careers": group, sub-group, SOC code(s), education to start. Exported from the planning sheet. **Edit this** to add or move careers. |
| `content.json` | The words: focus areas, jobs, descriptions, "how to get there", video and training links. **Edit this.** |
| `build_data.py` | Pulls the latest numbers and merges them with `content.json` into `data.js`. |
| `data.js` | Generated. Don't edit by hand. |

## Updating the numbers

```bash
python top_jobs/build_data.py
```

- **Demand** comes from LA Works' statewide long-term occupational projections (2024–2034), downloaded from
  `laworks.net/Downloads/LMI/20242034Occupations_AllProjStatewide.xlsx`. The page shows a plain label instead of percentages:
  - Very high demand: 1,000+ openings a year statewide
  - High demand: 400+ openings a year
  - Growing fast: 10%+ growth by 2034
- **Pay** comes from the BLS OEWS Louisiana estimates (latest May release) through the BLS API: starting pay = 25th percentile, typical = median.

**Browse all careers:** each group shows its top 5 by annual openings; "See all N careers" opens the full list with
sorts (most jobs, highest pay, fastest training) and "How much school?" filters. Healthcare and Skilled Trades are listed
by sub-group when opened. Combined rows add up openings across their codes and use an openings-weighted average of the
median wage (BLS May release, falling back to the LA Works median where BLS has no published figure).

When LA Works publishes a new projection cycle, change `PROJ_YEARS` in `build_data.py`. Regional files (RLMA 1–8) use the same layout if you want regional versions later.

## Focus areas

Six focus areas, in this order: Skilled Trades, Healthcare, Tech & Engineering, Business, Transportation,
Teaching & Public Service. Each is a `sector` in `content.json` with a `group` that names its group in
`occupations.csv` (this also sets the order of "Browse all in-demand careers"). Spotlight jobs are listed by SOC
code; a job can list several codes (`"25-2012, 25-2021"`), which are combined: openings add up and pay is an
openings-weighted average. To add a focus area, add a sector with `"status": "live"` and rerun the build.

## Training near me

Under the videos in each focus area, "Find training near me" lets a student pick one of the 8 Louisiana Works
Regional Labor Market Areas (or their parish). Each job's "Training near you" cell then lists matching schools in
that region. The region list, parishes (from the LA Works projections page) and public community/technical colleges
and universities are in `content.json` under `regions`. Each job's `train_at` says what kind of training fits
(`college`, `university`, `apprenticeship`, `onjob`, `academy`) and `look_for` says which program to ask about.
The choice is remembered in the browser. Schools are listed by type, not by verified program, so check each one.

## When BLS is unavailable

The free BLS API allows a limited number of requests per day without a key. The build tries v2, then v1, and saves
what it gets to `wages_cache.json`, so later builds only ask for codes it hasn't seen (delete the cache to refresh).
If BLS refuses entirely, the build keeps the pay from the previous `data.js` and prints which spotlight jobs have no
starting pay yet; the page then shows typical pay for those. Rerun when BLS is reachable.

## Still to verify

- Video links point to CareerOneStop career video pages by O*NET code. They could not be checked from the build environment, so click through each one before showing the site to students.
- Training near me lists each region's public colleges and universities by type. Link to specific programs (and add private schools, apprenticeship sponsors, academies) as you confirm them.
