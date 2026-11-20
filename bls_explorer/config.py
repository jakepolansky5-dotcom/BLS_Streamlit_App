"""Static reference data and user-editable presets.

Everything a user is likely to want to tweak (watchlist presets, industry
bundles, release dates) lives at the bottom of this file.
"""

# ---------------------------------------------------------------------------
# States (FIPS -> (name, postal abbreviation))
# ---------------------------------------------------------------------------
STATES = {
    "01": ("Alabama", "AL"), "02": ("Alaska", "AK"), "04": ("Arizona", "AZ"),
    "05": ("Arkansas", "AR"), "06": ("California", "CA"), "08": ("Colorado", "CO"),
    "09": ("Connecticut", "CT"), "10": ("Delaware", "DE"), "11": ("District of Columbia", "DC"),
    "12": ("Florida", "FL"), "13": ("Georgia", "GA"), "15": ("Hawaii", "HI"),
    "16": ("Idaho", "ID"), "17": ("Illinois", "IL"), "18": ("Indiana", "IN"),
    "19": ("Iowa", "IA"), "20": ("Kansas", "KS"), "21": ("Kentucky", "KY"),
    "22": ("Louisiana", "LA"), "23": ("Maine", "ME"), "24": ("Maryland", "MD"),
    "25": ("Massachusetts", "MA"), "26": ("Michigan", "MI"), "27": ("Minnesota", "MN"),
    "28": ("Mississippi", "MS"), "29": ("Missouri", "MO"), "30": ("Montana", "MT"),
    "31": ("Nebraska", "NE"), "32": ("Nevada", "NV"), "33": ("New Hampshire", "NH"),
    "34": ("New Jersey", "NJ"), "35": ("New Mexico", "NM"), "36": ("New York", "NY"),
    "37": ("North Carolina", "NC"), "38": ("North Dakota", "ND"), "39": ("Ohio", "OH"),
    "40": ("Oklahoma", "OK"), "41": ("Oregon", "OR"), "42": ("Pennsylvania", "PA"),
    "44": ("Rhode Island", "RI"), "45": ("South Carolina", "SC"), "46": ("South Dakota", "SD"),
    "47": ("Tennessee", "TN"), "48": ("Texas", "TX"), "49": ("Utah", "UT"),
    "50": ("Vermont", "VT"), "51": ("Virginia", "VA"), "53": ("Washington", "WA"),
    "54": ("West Virginia", "WV"), "55": ("Wisconsin", "WI"), "56": ("Wyoming", "WY"),
    "72": ("Puerto Rico", "PR"),
}
STATE_BY_ABBR = {abbr: fips for fips, (_, abbr) in STATES.items()}

LA = "22"
LA_NEIGHBORS = ["48", "05", "28"]          # TX, AR, MS
SOUTHERN_PEERS = ["01", "05", "12", "13", "21", "28", "37", "40", "45", "47", "48", "51"]

# ---------------------------------------------------------------------------
# Louisiana parishes (names match BLS area titles)
# ---------------------------------------------------------------------------
LA_PARISHES = {
    "22001": "Acadia Parish", "22003": "Allen Parish", "22005": "Ascension Parish",
    "22007": "Assumption Parish", "22009": "Avoyelles Parish", "22011": "Beauregard Parish",
    "22013": "Bienville Parish", "22015": "Bossier Parish", "22017": "Caddo Parish",
    "22019": "Calcasieu Parish", "22021": "Caldwell Parish", "22023": "Cameron Parish",
    "22025": "Catahoula Parish", "22027": "Claiborne Parish", "22029": "Concordia Parish",
    "22031": "De Soto Parish", "22033": "East Baton Rouge Parish", "22035": "East Carroll Parish",
    "22037": "East Feliciana Parish", "22039": "Evangeline Parish", "22041": "Franklin Parish",
    "22043": "Grant Parish", "22045": "Iberia Parish", "22047": "Iberville Parish",
    "22049": "Jackson Parish", "22051": "Jefferson Parish", "22053": "Jefferson Davis Parish",
    "22055": "Lafayette Parish", "22057": "Lafourche Parish", "22059": "LaSalle Parish",
    "22061": "Lincoln Parish", "22063": "Livingston Parish", "22065": "Madison Parish",
    "22067": "Morehouse Parish", "22069": "Natchitoches Parish", "22071": "Orleans Parish",
    "22073": "Ouachita Parish", "22075": "Plaquemines Parish", "22077": "Pointe Coupee Parish",
    "22079": "Rapides Parish", "22081": "Red River Parish", "22083": "Richland Parish",
    "22085": "Sabine Parish", "22087": "St. Bernard Parish", "22089": "St. Charles Parish",
    "22091": "St. Helena Parish", "22093": "St. James Parish", "22095": "St. John the Baptist Parish",
    "22097": "St. Landry Parish", "22099": "St. Martin Parish", "22101": "St. Mary Parish",
    "22103": "St. Tammany Parish", "22105": "Tangipahoa Parish", "22107": "Tensas Parish",
    "22109": "Terrebonne Parish", "22111": "Union Parish", "22113": "Vermilion Parish",
    "22115": "Vernon Parish", "22117": "Washington Parish", "22119": "Webster Parish",
    "22121": "West Baton Rouge Parish", "22123": "West Carroll Parish", "22125": "West Feliciana Parish",
    "22127": "Winn Parish",
}
PARISH_BY_NAME = {v: k for k, v in LA_PARISHES.items()}


def _p(*names):
    return tuple(PARISH_BY_NAME[n + " Parish"] for n in names)


# ---------------------------------------------------------------------------
# Louisiana metro / micro / combined areas, CURRENT (2023 OMB) definitions.
#
# Each list was verified against published QCEW totals: the sum of the
# parishes equals the published area total exactly for every quarter from
# 2024 Q1 onward (BLS adopted the 2023 delineations with 2024 data).
# Building areas from parishes gives a consistent history back to 2014,
# unlike BLS's published MSA series, which change definition in 2024.
# ---------------------------------------------------------------------------
LA_METROS = {
    "C1078": ("Alexandria MSA", _p("Grant", "Rapides")),
    "C1294": ("Baton Rouge MSA", _p("Ascension", "Assumption", "East Baton Rouge", "East Feliciana",
                                    "Iberville", "Livingston", "Pointe Coupee", "St. Helena",
                                    "West Baton Rouge", "West Feliciana")),
    "C2522": ("Hammond MSA", _p("Tangipahoa")),
    "C2638": ("Houma-Bayou Cane-Thibodaux MSA", _p("Lafourche", "Terrebonne")),
    "C2918": ("Lafayette MSA", _p("Acadia", "Lafayette", "St. Martin", "Vermilion")),
    "C2934": ("Lake Charles MSA", _p("Calcasieu", "Cameron", "Jefferson Davis")),
    "C3374": ("Monroe MSA", _p("Morehouse", "Ouachita", "Richland", "Union")),
    "C3538": ("New Orleans-Metairie MSA", _p("Jefferson", "Orleans", "Plaquemines", "St. Bernard",
                                             "St. Charles", "St. James", "St. John the Baptist")),
    "C4334": ("Shreveport-Bossier City MSA", _p("Bossier", "Caddo", "De Soto")),
    "C4364": ("Slidell-Mandeville-Covington MSA", _p("St. Tammany")),
}
LA_MICROS = {
    "C1422": ("Bogalusa MicroSA", _p("Washington")),
    "C1976": ("DeRidder MicroSA", _p("Beauregard")),
    "C3338": ("Minden MicroSA", _p("Webster")),
    "C3402": ("Morgan City MicroSA", _p("St. Mary")),
    "C3506": ("Natchitoches MicroSA", _p("Natchitoches")),
    "C3534": ("New Iberia MicroSA", _p("Iberia")),
    "C3666": ("Opelousas MicroSA", _p("St. Landry")),
    "C4082": ("Ruston MicroSA", _p("Lincoln")),
}
LA_CSAS = {
    "CS132": ("Baton Rouge-Hammond CSA", LA_METROS["C1294"][1] + LA_METROS["C2522"][1]),
    "CS318": ("Lafayette-New Iberia-Opelousas CSA",
              LA_METROS["C2918"][1] + LA_MICROS["C3534"][1] + LA_MICROS["C3666"][1]),
    "CS324": ("Lake Charles-DeRidder CSA", LA_METROS["C2934"][1] + LA_MICROS["C1976"][1]),
    "CS384": ("Monroe-Ruston CSA", LA_METROS["C3374"][1] + LA_MICROS["C4082"][1]),
    "CS406": ("New Orleans-Metairie-Slidell CSA (incl. Pearl River Co., MS)",
              LA_METROS["C3538"][1] + LA_METROS["C4364"][1] + LA_MICROS["C1422"][1] + ("28109",)),
    "CS508": ("Shreveport-Bossier City-Minden CSA", LA_METROS["C4334"][1] + LA_MICROS["C3338"][1]),
}

# ---------------------------------------------------------------------------
# QCEW codes
# ---------------------------------------------------------------------------
OWNERSHIPS = {
    "0": "All ownerships",
    "5": "Private",
    "8": "Total government",
    "1": "Federal government",
    "2": "State government",
    "3": "Local government",
}
# Ownership rows that add up to a combined ownership. QCEW only publishes
# own_code 0/8 for the all-industry total, so detailed industries are summed.
OWNERSHIP_PARTS = {"0": ("1", "2", "3", "4", "5"), "8": ("1", "2", "3")}

SUPERSECTORS = {
    "1011": "Natural resources and mining", "1012": "Construction", "1013": "Manufacturing",
    "1021": "Trade, transportation, and utilities", "1022": "Information",
    "1023": "Financial activities", "1024": "Professional and business services",
    "1025": "Education and health services", "1026": "Leisure and hospitality",
    "1027": "Other services", "1028": "Public administration", "1029": "Unclassified",
}

INDUSTRY_LEVELS = {
    "Supersector": "super",
    "NAICS sector (2-digit)": 2,
    "NAICS subsector (3-digit)": 3,
    "Industry group (4-digit)": 4,
    "NAICS industry (5-digit)": 5,
    "National industry (6-digit)": 6,
}

# ---------------------------------------------------------------------------
# USER PRESETS (edit freely)
# ---------------------------------------------------------------------------

# Industry bundles that show up in industry pickers and the Project Watch page.
INDUSTRY_BUNDLES = {
    "Data center construction & operations": [
        "23",      # Construction
        "236220",  # Commercial and institutional building construction
        "2371",    # Utility system construction
        "237130",  # Power and communication line construction
        "237990",  # Other heavy and civil engineering construction
        "238",     # Specialty trade contractors
        "238212",  # Nonresidential electrical contractors
        "238222",  # Nonresidential plumbing and HVAC contractors
        "2211",    # Electric power generation, transmission and distribution
        "518210",  # Computing infrastructure providers, data processing, hosting
        "5613",    # Employment services (staffing)
        "721",     # Accommodation (worker housing)
        "722",     # Food services and drinking places
    ],
    "Energy & petrochemicals": [
        "211", "213111", "213112", "2212", "237120", "324110", "325110", "3251", "486",
    ],
    "Advanced manufacturing": ["31-33", "325", "331", "332", "333", "334", "335", "336"],
    "Health care": ["62", "621", "622", "623", "624"],
    "Tourism & hospitality": ["71", "721", "722", "7225"],
    "Ports, logistics & warehousing": ["48-49", "483", "484", "488", "493", "4931"],
}

# Watchlists: named groups of parishes + industries for the Project Watch page.
# Additional watchlists you save in the app are stored in watchlists.json.
WATCHLIST_PRESETS = {
    "North LA data center (Richland Parish & neighbors)": {
        "parishes": list(_p("Richland", "Franklin", "Madison", "Ouachita", "Morehouse", "West Carroll")),
        "industries": INDUSTRY_BUNDLES["Data center construction & operations"],
        "baseline": "2024Q1",
        "notes": "Meta's Hyperion data center site is in Richland Parish (Holly Ridge). "
                 "Neighboring parishes capture commuting, lodging and supply-chain effects.",
    },
}

# Known upcoming QCEW release dates (County Employment and Wages news release).
# Add new rows as BLS publishes its schedule: (YYYY-MM-DD, "data period").
RELEASE_SCHEDULE = [
    ("2026-12-02", "2026 Q2"),
]
