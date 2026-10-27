# Everything the paper says. Edit freely, then run `python3 press/print.py`.
# Mirrors the copy on www.anirbandas.com so the two mastheads tell one story.

LOGIN = "anirban12d"
NAME = "Anirban Das"
PAPER = "The Daily Commit"
TAGLINE = "BUILT TO SHIP, SHIPPED TO LAST"
MOTTO = ("“All the Code That’s", "Fit to Ship.”")  # the left ear, two lines
FOUNDED = "2020-10-03"  # the day the GitHub account opened: Vol. I, No. 1
SITE = "https://www.anirbandas.com"
EMAIL = "anirbandashere@gmail.com"

# The working nav bar under the nameplate. Every segment is a real link.
# (label on the bar, link, name for screen readers)
NAV = [
    ("FRONT PAGE", SITE, "Front page"),
    ("CASE FILES", f"{SITE}/projects", "Case files"),
    ("BYLINE", f"{SITE}/about", "Byline"),
    ("LINKEDIN", "https://www.linkedin.com/in/anirban12d", "LinkedIn"),
    ("X", "https://twitter.com/anirban12d", "X"),
    ("DEV.TO", "https://dev.to/anirban12d", "DEV"),
    ("MEDIUM", "https://medium.com/@anirban12d", "Medium"),
    ("HIRE ME", f"mailto:{EMAIL}", "Hire me"),
]

# Breaking-news ticker. The press prepends two lines of live wire copy.
TICKER = [
    "BREAKING — DEVELOPER CENTERS DIV ON FIRST TRY, PHYSICISTS BAFFLED",
    "OPINION — 'IT WORKS ON MY MACHINE' RULED ADMISSIBLE IN COURT",
    "TECH — LOCAL DEV DELETES node_modules, RECLAIMS 3GB AND THE WILL TO LIVE",
    "MARKET — TYPESCRIPT any-TYPE HITS RECORD LOW AMID STRICT-MODE RALLY",
    "WEATHER — LIGHT MERGE CONFLICTS AT DAWN, HEAVY REBASES BY NOON",
    "SPORTS — TABS VS SPACES ENTERS 47TH SEASON, STILL NO WINNER",
    "OBITUARY — jQuery, STILL RUNNING HALF THE WEB, POLITELY REFUSES TO DIE",
]

LEAD = {
    "kicker": "MEET THE DEVELOPER",
    # U+2011 non-breaking hyphen keeps "Load-Bearing" on one line.
    "headline": "Full-Stack Engineer Ships the Boring, Load‑Bearing Parts — On Purpose.",
    "standfirst_lead": "Remote-first, filing from Kolkata",
    "standfirst": (
        " — Anirban Das is a full-stack developer who builds the boring-but-critical "
        "parts well: auth, data, real-time, and the AI features layered on top. He "
        "started chasing clean UIs; now he chases correctness under load."
    ),
    "teaser": (
        "Four years and four teams: document intelligence at Bau.ai in Berlin, "
        "AI-assisted diagnostics at Medecro.ai, an in-browser OS frontend at ProjectX, "
        "and legal-tech at Legabyte. The through-line never changes: own the data "
        "model, the API, and the frontend — then stay through the on-call."
    ),
    "caption": "ABOVE: THE EDITOR AT HIS DESK, SHIPPING THE DAY'S BUILD.",
}

# Selected work. `link` is where the card goes; `repo` (if any) is where the
# press reads the live star count from.
WORK = [
    {
        "slug": "txt-launcher",
        "kicker": "ANDROID · LAUNCHER",
        "year": "2026",
        "title": "An Android Home Screen Where the App Name Is the Icon",
        "summary": "A text-only Android launcher, live on Google Play — app names set in type instead of icons, every swipe reassignable, and a widget stack driven by broadcasts rather than polling.",
        "stack": ["KOTLIN", "JETPACK COMPOSE", "DATASTORE"],
        "link": "https://play.google.com/store/apps/details?id=com.txt.launcher",
        "cta": "ON GOOGLE PLAY",
    },
    {
        "slug": "bluekeys",
        "kicker": "DEVELOPER TOOLS · CLI",
        "year": "2025",
        "title": "A Terminal Typing Trainer That Ships on Homebrew",
        "summary": "Monkeytype, but it lives in your terminal — 15+ themes, a 25-lesson touch-typing curriculum, and an error heatmap, rendered with React's Ink and shipped via Homebrew and npm.",
        "stack": ["TYPESCRIPT", "REACT INK", "HOMEBREW"],
        "repo": "bluekeys",
        "cta": "READ THE SOURCE",
    },
    {
        "slug": "reporadar",
        "kicker": "ANALYTICS · WEB APP",
        "year": "2025",
        "title": "A GitHub Analytics Dashboard for the Numbers-Curious",
        "summary": "Point it at any username and it draws the picture: contribution heatmaps, language charts, and a composite profile score — all cached hard with TanStack Query.",
        "stack": ["NEXT.JS 15", "REACT 19", "RECHARTS"],
        "repo": "repo-radar",
        "cta": "READ THE SOURCE",
    },
    {
        "slug": "profilepulse",
        "kicker": "AI · WEB APP",
        "year": "2025",
        "title": "A Privacy-First ATS Resume Analyzer",
        "summary": "Upload a resume, get an ATS-style report across five dimensions and 170+ skills. The engine runs entirely in memory — files never touch a disk — wired end-to-end with tRPC.",
        "stack": ["NEXT.JS 15", "TRPC", "TANSTACK QUERY"],
        "repo": "profile-pulse",
        "cta": "READ THE SOURCE",
    },
    {
        "slug": "blogzilla",
        "kicker": "FULL-STACK · AI",
        "year": "2024",
        "title": "A Notion-Style Blogging Platform with AI On Tap",
        "summary": "A blogging platform that feels like Notion and writes like a co-author: slash commands, AI generation via the Vercel AI SDK, Better Auth, and Drizzle over Postgres.",
        "stack": ["NEXT.JS", "VERCEL AI SDK", "DRIZZLE"],
        "repo": "blogzilla",
        "cta": "READ THE SOURCE",
    },
    {
        "slug": "moviez",
        "kicker": "FRONTEND",
        "year": "2024",
        "title": "A Real-Time Movie Database, State Managed",
        "summary": "Built to get the fundamentals right: Redux for predictable global state, real-time fetching, and error handling that fails gracefully instead of white-screening.",
        "stack": ["NEXT.JS", "REDUX", "REST"],
        "repo": "Moviez",
        "cta": "READ THE SOURCE",
    },
]

# Developer Stock Exchange — self-assessed, closes whenever the editor says so.
MARKETS = [
    ("TS", "TYPESCRIPT", "312.40", "+1.4%", [4, 5, 4, 6, 7, 6, 8]),
    ("RCT", "REACT / NEXT", "298.10", "+0.7%", [5, 5, 6, 5, 6, 7, 7]),
    ("NODE", "NODE / APIS", "205.60", "+0.7%", [5, 6, 5, 6, 6, 7, 7]),
    ("PG", "POSTGRES / SQL", "188.75", "+0.5%", [4, 4, 5, 5, 5, 6, 6]),
    ("AI", "AI / ML", "241.30", "+1.5%", [3, 4, 4, 5, 6, 7, 8]),
    ("KT", "KOTLIN / COMPOSE", "96.20", "+4.8%", [1, 2, 2, 3, 5, 6, 8]),
    ("JQ", "JQUERY (LEGACY)", "12.05", "-6.6%", [6, 5, 4, 4, 3, 3, 2]),
]

PRACTICE = [
    ("Full-stack, end-to-end",
     "From schema to pixel. I design the data model, build the API, wire the frontend, and stay through the on-call. PMs get estimates that hold; users get features that don't flake."),
    ("AI features that actually ship",
     "X-ray analysis, transcription, document auto-fill, RAG. I make the model useful inside a real product — with guardrails, evals, and a sane fallback for when it's confidently wrong."),
    ("The un-glamorous core",
     "RBAC, multi-tenancy, WebSockets, PDF pipelines, migrations. The parts nobody demos but everybody depends on at 2 a.m. My natural habitat."),
]

CLASSIFIEDS = {
    "display": ("FOR HIRE", "Full-stack dev, 4+ yrs, TypeScript end-to-end. Brings own keyboard and strong opinions on state management. Reply within the day."),
    "columns": [
        [
            ("WANTED", [
                "One (1) product team that reviews PRs the same day. Must value shipping over ceremony. Box No. 01.",
                "Fast CI pipeline, under ten minutes cold. Flaky stages need not apply.",
            ]),
        ],
        [
            ("LOST & FOUND", [
                "LOST — One (1) semicolon, last seen in a JSON file. Answers to SyntaxError. Reward.",
                "FOUND — 3GB of node_modules. Owner must collect by Friday or they will be rm -rf'd without further notice.",
            ]),
            ("PUBLIC NOTICES", [
                "NOTICE OF DEPRECATION — jQuery is hereby removed from the editor's résumé, effective immediately. Objections in writing.",
            ]),
        ],
        [
            ("FOR SALE", [
                "Strong opinions on state management, barely used. Will trade for a code review with teeth.",
            ]),
            ("PERSONAL", [
                "To the flaky E2E test that passed locally and failed in CI three times: I know it was you. We are no longer on speaking terms.",
            ]),
        ],
    ],
}

COLOPHON = {
    "blurb": "One engineer, one repository, one very opinionated build pipeline. A new issue every morning.",
    "corrections": "In our last release we shipped a console.log to production. We regret the error. We do not regret the three-hour debugging session that built character.",
    "printing": "Set in Newsreader, Libre Franklin & IBM Plex Mono. Typeset in Python, printed by GitHub Actions every morning at 06:00 IST.",
}
