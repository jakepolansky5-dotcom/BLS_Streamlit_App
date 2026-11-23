# LA Top Jobs (demo)

A simple static site that shows K-12 students the top projected jobs in Louisiana, in kid-friendly language.

Open `index.html` in a browser. No server or build step is needed to view it.

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

## Adding a focus area

In `content.json`, replace one of the `"status": "soon"` placeholders with `"status": "live"`, a name and a tagline, and add jobs by SOC code. Then rerun the build.

## Still to verify

- Video links point to CareerOneStop career video pages by O*NET code. They could not be checked from the build environment, so click through each one before showing the site to students.
- Training links are sample Baton Rouge-area providers (top-level sites). Replace them with specific programs per region.
