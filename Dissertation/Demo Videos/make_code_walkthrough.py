"""
Builds the code walkthrough videos (voice + no voice) from the current code.

    python -m venv vt && vt/bin/pip install imageio-ffmpeg edge-tts pygments pillow
    vt/bin/python "Dissertation/Demo Videos/make_code_walkthrough.py" OUT_DIR

Code is read live from the repo; every highlight is located by an anchor
string, so the line numbers stay right after edits (a missing anchor fails).
Narration uses edge-tts (needs network); fonts come from Windows (WSL).
"""
import asyncio
import hashlib
import re
import subprocess
import sys
import wave
from pathlib import Path

import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont
from pygments.lexers import PythonLexer
from pygments.token import Token

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
WORK = OUT / "build"
FF = imageio_ffmpeg.get_ffmpeg_exe()
VOICE = "en-US-AndrewNeural"
W, H = 1920, 1080
WIN_FONTS = Path("/mnt/c/Windows/Fonts")

def font(name, size):
    return ImageFont.truetype(str(WIN_FONTS / name), size)

F_TITLE = font("segoeuib.ttf", 46)
F_BIG = font("segoeuib.ttf", 84)
F_SUB = font("segoeui.ttf", 34)
F_STEP = font("segoeui.ttf", 26)
F_STEP_B = font("segoeuib.ttf", 26)
F_CAP = font("segoeui.ttf", 31)
F_BADGE = font("segoeuib.ttf", 26)
F_CHIP = font("consola.ttf", 24)
F_CODE = font("consola.ttf", 22)
F_LINE = font("segoeui.ttf", 38)
F_LINE_MONO = font("consola.ttf", 40)
F_BOX = font("segoeuib.ttf", 27)
F_BOX_SUB = font("segoeui.ttf", 21)
F_GROUP = font("segoeuib.ttf", 20)

BG, PANEL, BORDER = "#0b1220", "#111a2e", "#24324d"
TEXT, MUTED, GREEN, GREEN_DARK = "#e6edf7", "#8b9ab3", "#34d399", "#166534"
AMBER, HL_BG, BLUE_CHIP = "#fbbf24", "#2d2a14", "#13234a"
TOKEN_COLORS = [
    (Token.Comment, "#7f8ea3"), (Token.Literal.String, "#98c379"), (Token.Literal.Number, "#d19a66"),
    (Token.Keyword, "#c678dd"), (Token.Name.Function, "#61afef"), (Token.Name.Class, "#e5c07b"),
    (Token.Name.Decorator, "#e5c07b"), (Token.Name.Builtin, "#56b6c2"), (Token.Operator, "#56b6c2"),
]


# ── Script ────────────────────────────────────────────────────────────────────
def code(title, file, steps, view=None):
    return dict(kind="code", title=title, file=file, steps=steps, view=view)

def reveal(title, lines, chip=""):
    return dict(kind="reveal", title=title, lines=lines, chip=chip)

def diagram(title, boxes, arrows, steps, groups=(), chip=""):
    return dict(kind="diagram", title=title, boxes=boxes, arrows=arrows, steps=steps, groups=groups, chip=chip)

SCENES = [
    dict(kind="title", title="How SPK Works", subtitle="A guided code walkthrough · Sistem Pemantauan Karbon", steps=[
        "Hi, and welcome. In this walkthrough I'll explain the code behind Sistem Pemantauan Karbon, or SPK, the way I'd explain it to a new teammate.",
        "We won't read every line. We'll follow the path data takes through the app, and stop at the ideas that matter. By the end, you should know why each file exists.",
    ]),
    reveal("What the system does", [
        ("1.  Input: activity data, e.g. litres of diesel, kWh of electricity",
         "Let's start with the problem. A company records activity data: things like litres of diesel burned, or kilowatt hours of electricity bought."),
        ("2.  Convert: CO₂e = quantity × emission factor (SEDG)",
         "The system turns each quantity into carbon dioxide equivalent, using the official Malaysian emission factors from the SEDG guide."),
        ("3.  Tax: tonnes CO₂e × MYR 15",
         "Then it prices those emissions with Malaysia's carbon tax of fifteen ringgit per tonne."),
        ("4.  Analyse: dashboard, STIRPAT forecast, what-if simulator, AI advisor",
         "On top of that sit the analysis tools: a dashboard, a six-month STIRPAT forecast, a what-if simulator and an AI advisor."),
        ("5.  Control: anomaly checks, approval queue, audit log, three roles",
         "And around everything are the controls a regulator needs: anomaly checks, an approval queue, an audit log, and three user roles."),
    ]),
    diagram("System architecture",
        boxes={
            "browser": (710, 150, 500, 80, "Web browser", "Company user · Government officer · IT admin"),
            "app": (500, 280, 420, 80, "app.py", "router · styles · database set-up · login wall"),
            "ui": (1000, 280, 420, 80, "utils/ui.py · Page", "base class: sidebar, navigation, chat"),
            "p1": (230, 430, 340, 80, "Main Dashboard", "KPIs · trend + forecast · tax"),
            "p2": (600, 430, 340, 80, "What-If Simulator", "8 reduction levers + AI"),
            "p3": (970, 430, 340, 80, "Sustainability", "data entry · approvals · audit log"),
            "p4": (1340, 430, 340, 80, "Data Centre", "ledger · CSV · PDF statement"),
            "u1": (70, 580, 210, 80, "auth", "roles · permissions"),
            "u2": (295, 580, 210, 80, "data_manager", "ledger · anomaly"),
            "u3": (520, 580, 210, 80, "analytics", "STIRPAT · z-score"),
            "u4": (745, 580, 210, 80, "carbon_calculator", "CO₂e · tax"),
            "u5": (970, 580, 210, 80, "simulation", "what-if levers"),
            "u6": (1195, 580, 210, 80, "ai_helper", "Groq client"),
            "u7": (1420, 580, 210, 80, "report", "PDF statement"),
            "u8": (1645, 580, 210, 80, "config", "constants"),
            "d1": (190, 730, 380, 80, "emissions.db (SQLite)", "ledger · queue · activity log"),
            "d2": (600, 730, 380, 80, "Carbon_Emission_Data.xlsx", "reported 2021–2025 + synthetic 2026"),
            "d3": (1010, 730, 340, 80, "emission_factors.py", "SEDG factors · MYR 15/t"),
            "d4": (1380, 730, 340, 80, "Groq API", "GPT-OSS 120B"),
        },
        groups=[("PAGES/ · EACH ONE A SUBCLASS OF Page", 412), ("UTILS/ · BUSINESS LOGIC, MOSTLY NO UI CODE", 562),
                ("DATA AND SERVICES", 712)],
        arrows=[("browser", "app"), ("app", "ui")],
        steps=[
            (set(), "Here is the whole system on one slide. It's built in layers, and each layer mostly talks to the layer below it."),
            ({"browser", "app", "ui"}, "At the top, app.py is the front door: every request passes through it. And ui.py gives every page the same frame: sidebar, navigation and the chat button."),
            ({"p1", "p2", "p3", "p4"}, "Next come the four pages. Each one is a small class that decides what to show, but does very little calculation itself."),
            ({f"u{i}" for i in range(1, 9)}, "The real work lives in utils: calculations, the database, forecasting, the simulator, the AI client and the PDF report. Most of these have no user-interface code, which makes them easy to unit test."),
            ({"d1", "d2", "d3", "d4"}, "At the bottom is the data: an SQLite ledger for submissions, the Excel workbook of reported company figures, the emission factors, and the Groq API for the chatbot."),
        ]),
    code("app.py: the front door", "app.py", [
        ("Imports only", "from utils.config import APP_NAME", 2,
         "This is the entire entry point: eighteen lines. It imports settings from config and one function from ui. app.py itself holds no logic."),
        ("Bootstrap", "init_app(APP_NAME", 1,
         "init_app runs on every request. It sets up the page, loads the styles, creates the database if needed, and shows the login wall to anyone who isn't signed in."),
        ("Register pages", "pages = [st.Page", 1,
         "Then it builds the list of pages from the PAGE_ROUTES table in config. The Main Dashboard is the default, so that's where users land after logging in."),
        ("Run the router", "st.navigation(pages", 1,
         "Finally, st.navigation runs whichever page was requested. Its menu is hidden, because we draw our own navigation box in the sidebar."),
    ], view=("import streamlit", "st.navigation(pages")),
    code("config.py: one place for settings", "utils/config.py", [
        ("Page routes", "PAGE_ROUTES = {", 9,
         "config.py is the project's single source of truth. This table maps each menu label to its page file. Add a page here, and it appears in both the router and the menu."),
        ("AI settings", "GROQ_API_KEY_ENV", 6,
         "The AI settings live here too. Notice the API key is read from an environment variable; it's never written in the code."),
        ("Anomaly rules", "ANOMALY_MIN_HISTORY = 5", 2,
         "These two numbers drive anomaly detection: a source needs five past records before it can be scored, and anything beyond two point five standard deviations is flagged."),
        ("Forecast settings", "FORECAST_MONTHS = 6", 3,
         "And these drive the forecast: six months ahead, an eighty-twenty split by time, and a ridge penalty of 0.005. Change a number here, and every page follows."),
    ], view=("PAGE_ROUTES = {", "DATA_TABLE_PAGE_SIZE")),
    code("ui.py: the Page base class", "utils/ui.py", [
        ("init_app()", "def init_app", 14,
         "Here's init_app. Look at its last two lines: init_db makes sure the tables exist, and require_login stops the run if nobody is signed in. So no page can render for an anonymous visitor."),
        ("class Page", "class Page:", 10,
         "Below it is the Page base class, the most important design idea in the UI. Every page inherits from it, and only sets a name, a menu label and an optional header."),
        ("run(): a fixed recipe", "    def run(self)", 13,
         "run is a fixed recipe: check login again, draw the brand, the navigation and the page's own sidebar, then the header, then render, then the chat widget. Every page gets this order for free."),
        ("Hooks to override", "    def sidebar(self)", 12,
         "Pages fill in the gaps by overriding these hooks: sidebar for filters, render for content, and chat_context to tell the chatbot what's on screen. This pattern is called a template method."),
    ], view=("def init_app", "raise NotImplementedError")),
    code("Anatomy of a page", "pages/What_If_Simulator.py", [
        ("Declare", "class WhatIfSimulator(Page)", 7,
         "Let's look at a real page. The What-If Simulator subclasses Page and declares its name, menu label and header. That's all the setup it needs."),
        ("Load allowed data", "    def render(self)", 2,
         "render starts by loading the emissions this user is allowed to see. If there's nothing, the page stops with a friendly message instead of crashing."),
        ("Hand off the maths", "df_sim = df.copy()", 7,
         "Then it hands the work to plain functions: simulate_emissions, scope_totals and carbon_tax. The page shows results, the utils compute them. Keep that split in mind as we go."),
    ], view=("class WhatIfSimulator(Page)", "self.render_scenario_analysis")),
    code("auth.py: who are you, what can you see", "utils/auth.py", [
        ("Demo accounts", "USERS = {", 22,
         "Now, logging in. USERS holds the demo accounts: admin for IT, user for the government officer, and one account per company, generated from the company list."),
        ("Permission matrix", "PERMISSIONS = {", 5,
         "This permission matrix is the heart of access control. Admin can do everything. Government sees every company and issues reports, but can't submit or approve. Companies submit and approve their own data."),
        ("Check the password", "def authenticate", 6,
         "authenticate compares passwords with hmac compare_digest, which takes the same time whether a guess is close or not, so timing can't leak the password."),
        ("Row-level filter", "def visible_rows", 10,
         "visible_rows is the data filter. Roles with all_companies see everything; a company user only gets their own company's rows. Pages load data through it, so a company never sees a competitor's figures."),
        ("Login wall", "def require_login", 6,
         "And require_login is the wall we saw earlier: if the session isn't signed in, show the login form and stop."),
    ], view=("USERS = {", "        st.stop()")),
    code("Emission factors", "data/emission_factors.py", [
        ("Where they come from", "#  Source: SEDG", 4,
         "Every calculation starts with this file. The factors come from the SEDG calculator guide: GHG Protocol factors for fuels, and Suruhanjaya Tenaga's grid factors for electricity."),
        ("Scope 1: fuels", '"Stationary – Diesel": ', 1,
         "Each source has a unit and a factor. Stationary diesel, for example, is 2.95 kilograms of CO₂e per litre."),
        ("Scope 2: electricity", '"Electricity – Peninsular', 4,
         "Electricity depends on the grid. Peninsular Malaysia is 0.774 kilograms per kilowatt hour, while Sarawak, with its hydropower, is only 0.199."),
        ("Carbon tax rate", "CARBON_TAX_RATE_MYR = 15.0", 1,
         "And the carbon tax rate: fifteen ringgit per tonne. Keeping these in one file means an updated factor is a one-line change."),
    ]),
    code("carbon_calculator.py", "utils/carbon_calculator.py", [
        ("Guard the input", "def _require_non_negative", 3,
         "carbon_calculator turns quantities into emissions. First, a guard: a negative number, infinity, or not-a-number is rejected with a clear error."),
        ("Quantity × factor", "def calculate_emission", 9,
         "calculate_emission is the core formula: look up the source, check the quantity, multiply by the factor. The result is kilograms of CO₂e."),
        ("Carbon tax", "def carbon_tax", 5,
         "carbon_tax converts kilograms to tonnes and multiplies by the rate, rounded to the sen."),
    ], view=("def _require_non_negative", "return round(kg_to_tonnes(kg_co2e)")),
    reveal("Worked example: one diesel entry", [
        ("Entry: 1,000 L of Stationary – Diesel",
         "Let's try it with real numbers. Suppose a company enters one thousand litres of stationary diesel."),
        ("`1,000 L × 2.95 kg/L = 2,950 kg CO₂e",
         "calculate_emission multiplies by 2.95, giving two thousand nine hundred and fifty kilograms of CO₂e."),
        ("`2,950 kg ÷ 1,000 = 2.95 t CO₂e",
         "Divide by a thousand, and that's 2.95 tonnes."),
        ("`2.95 t × MYR 15 = MYR 44.25",
         "Multiply by fifteen ringgit, and the tax is forty-four ringgit and twenty-five sen."),
        ("PDF: “Ringgit Malaysia Forty Four and Sen Twenty Five Only”",
         "Later, the PDF statement writes that amount in words, exactly like this, using a small function in report.py. We'll see it near the end."),
    ], chip="calculate_emission · carbon_tax · amount_in_words"),
    code("Where data is stored: three tables", "utils/data_manager.py", [
        ("emissions: the ledger", "CREATE TABLE IF NOT EXISTS emissions", 17,
         "Now, where data is stored. The SQLite file has three tables. emissions is the ledger: one row per entry, with who submitted it, its status, and whether it was flagged."),
        ("pending_submissions", "CREATE TABLE IF NOT EXISTS pending_submissions", 15,
         "pending_submissions is the approval queue. A flagged entry waits here, with the reason it was flagged, until someone approves or rejects it."),
        ("activity_log", "CREATE TABLE IF NOT EXISTS activity_log", 7,
         "And activity_log is the audit trail: a timestamp, a username, an action and details, for every submission, approval, login and logout."),
    ], view=("_SCHEMA = (", "def _now()")),
    code("submit_emission(): one entry, five steps", "utils/data_manager.py", [
        ("1  Validate", "_validate_submission(data, username)", 1,
         "This is the most important function in the project, so let's follow one entry through it. Step one: validate. An unknown company, wrong scope, bad date or negative quantity raises a ValueError straight away."),
        ("2  Calculate", 'source = data["source"]', 8,
         "Step two: calculate the CO₂e and build the row, stamping who submitted it and when."),
        ("3  Score vs history", "anomaly, reason = _score_submission(row)", 1,
         "Step three: score it against history. This returns whether it looks unusual, plus a reason we can show the user."),
        ("4  Duplicate month?", "with _connect() as conn:", 4,
         "Step four: a company may only have one entry per source per month. A second one is treated as an anomaly too, with an explanation."),
        ("5  Route and log", "if anomaly:", 7,
         "Step five: route it. Anomalies go to pending_submissions; normal entries go straight into the ledger. Either way, the action is written to the audit log in the same transaction."),
    ], view=("def submit_emission", 'return {"inserted": True')),
    code("detect_anomaly(): the z-score rule", "utils/analytics.py", [
        ("Enough history?", "if len(history) < ANOMALY_MIN_HISTORY", 2,
         "How do we decide what's unusual? With a z-score. First, if there are fewer than five past values, there isn't enough history to judge."),
        ("Mean and spread", "mean = float(np.mean(history))", 4,
         "Next, take the mean and standard deviation of the past values. If every past value is identical, the spread is zero and we can't score, so it passes."),
        ("How far off?", "z = abs(value - mean) / std", 3,
         "The z-score is how many standard deviations the new value sits from the mean. Above 2.5, it's flagged. With high_only, low values are ignored."),
        ("Explain why", 'direction = "high"', 6,
         "Finally, we build a human-readable reason. Users see exactly why their entry was held, instead of just being told no."),
    ], view=("def detect_anomaly", "return True, reason")),
    reveal("Worked example: the z-score", [
        ("Past diesel entries: mean 10,000 L, std 2,000 L",
         "A quick example. Say a company's past diesel entries average ten thousand litres, with a standard deviation of two thousand."),
        ("`14,000 L → z = 4,000 ÷ 2,000 = 2.0  → accepted",
         "A new entry of fourteen thousand litres is two standard deviations above the mean. That's within the limit, so it goes straight into the ledger."),
        ("`15,100 L → z = 5,100 ÷ 2,000 = 2.55 → approval queue",
         "But fifteen thousand one hundred litres gives two point five five. That crosses the line, so it goes to the approval queue."),
        ("Simple on purpose: anyone can check the arithmetic",
         "The rule is simple on purpose. Anyone can check the arithmetic, which matters when an auditor asks why an entry was held."),
    ], chip="ANOMALY_Z_THRESHOLD = 2.5"),
    code("Which history? Fallbacks and duplicates", "utils/data_manager.py", [
        ("Same source", 'history = _approved_values("quantity"', 3,
         "Which history do we compare against? Normally, the source's own approved quantities, in their native unit."),
        ("New source fallback", "scope_history = _approved_values", 2,
         "But a brand-new source has no history, so its first entry could be any size. To close that gap, we compare its CO₂e against the rest of its scope, flagging only high values."),
        ("Duplicate key", "def _same_month_key", 2,
         "For duplicates, the key is company, source and month: the first seven characters of the date. _duplicate_reason checks both the ledger and the queue for that key."),
    ], view=("def _score_submission", "per month is allowed; approving")),
    code("Approve and withdraw: nothing is deleted", "utils/data_manager.py", [
        ("Only if still pending", "row = _fetch_pending(conn, record_id)", 3,
         "Approving an entry. First, fetch it, but only if it's still pending. If two people click approve at once, the second simply gets False."),
        ("Replace, don't delete", "replaced = conn.execute(", 5,
         "Only one entry per month is allowed, so any existing entry is marked 'replaced'. Notice the word: replaced, not deleted."),
        ("Copy into the ledger", '_insert(conn, "emissions", {', 4,
         "The entry is copied into the ledger with the approver, the time, and is_anomaly set to one, so it stays visible that this entry was flagged."),
        ("Withdraw = undo", "def withdraw_submission", 22,
         "Withdraw lets users undo their own entry. It's marked 'withdrawn', and if it had replaced an older entry, that one comes back. No row is ever deleted, so every total can be traced."),
    ], view=("def approve_submission", "    return True\n\n\n# ── Activity log")),
    diagram("The life of an entry",
        boxes={
            "submit": (120, 330, 280, 100, "Submit", "Sustainability form"),
            "check": (500, 330, 300, 100, "Checks", "validate · z-score · duplicate"),
            "approved": (1000, 170, 330, 100, "approved", "in the ledger, counts in totals"),
            "pending": (1000, 480, 330, 100, "pending", "approval queue + reason"),
            "rejected": (1460, 480, 330, 100, "rejected", "kept, never counted"),
            "replaced": (1460, 120, 330, 100, "replaced", "older entry, same month"),
            "withdrawn": (1460, 290, 330, 100, "withdrawn", "undone by its submitter"),
            "log": (120, 640, 680, 100, "activity_log", "every arrow writes one audit row"),
        },
        arrows=[("submit", "check"), ("check", "approved"), ("check", "pending"), ("pending", "approved"),
                ("pending", "rejected"), ("approved", "replaced"), ("approved", "withdrawn")],
        steps=[
            ({"submit", "check", "approved"}, "Here's the whole lifecycle in one picture. A normal entry goes from submit, through the checks, straight to approved."),
            ({"submit", "check", "pending"}, "An unusual or duplicate entry stops at pending, in the approval queue, along with its reason."),
            ({"pending", "approved", "replaced", "rejected"}, "From there, a reviewer approves it, and any older entry for that month becomes replaced. Or the reviewer rejects it."),
            ({"approved", "withdrawn", "replaced"}, "An approved entry can be withdrawn by whoever submitted it, which brings back anything it replaced."),
            ({"log"}, "And every arrow on this slide writes one row to the activity log. That's what makes the ledger auditable."),
        ], chip="status values in the emissions table"),
    code("Reading the workbook", "utils/data_manager.py", [
        ("Cache per file version", "@lru_cache(maxsize=4)", 7,
         "Now the analytics side. The dashboard reads the Excel workbook of reported company data. Parsing Excel is slow, so it's cached, and the file's modified time is part of the key. Edit the file, and the cache refreshes itself."),
        ("Fail loudly", "missing = sorted(WORKBOOK_REQUIRED_COLUMNS", 5,
         "If a required column is missing, we raise a clear error naming it, instead of a confusing crash deep inside a chart."),
        ("STIRPAT panel", 'panel = workbook[["company", "date"]].assign(', 10,
         "The same read builds the forecasting panel: Scope 1, Scope 2, their total, and the three drivers. Synthetic 2026 rows are marked so the model never trains on them."),
        ("Pick the source", "def load_emissions()", 8,
         "And load_emissions picks the source the pages use: the workbook when it's there, otherwise the SQLite ledger."),
    ], view=("@lru_cache(maxsize=4)", "return load_database_emissions()\n\n\ndef _load_submissions")),
    code("Main Dashboard: filters and KPIs", "pages/Main_Dashboard.py", [
        ("Sidebar filters", "    def sidebar(self)", 12,
         "The Main Dashboard. Its sidebar hook draws the filters: year, company, scope and tax rate. The data comes from visible_emissions, so a company user's list only contains their own company."),
        ("Apply filters", "    def render(self)", 9,
         "render checks that something is ticked, then calls filter_emissions, a plain pandas function in analytics, which is unit tested."),
        ("Fair year-on-year", "pool = filter_emissions(self.df_all", 3,
         "For the year-on-year change, it compares the latest selected year with the same months one year earlier, so half a year is never compared with a full one."),
        ("Tax per year", 'months = self.df["month"].nunique()', 4,
         "The tax card divides by the number of selected months and multiplies by twelve, giving a fair yearly figure for any selection."),
    ], view=("    def sidebar(self)", "tax_card = (")),
    reveal("STIRPAT: the forecasting idea", [
        ("`ln I = ln α + a·ln P + b·ln A + c·ln T",
         "Time for the forecasting model. STIRPAT says emissions, I, depend on production P, affluence A, which here is revenue, and technology T, which is energy intensity."),
        ("Logs → every coefficient is an elasticity",
         "Because we take logs of everything, each coefficient is an elasticity: a one percent rise in that driver changes emissions by that many percent."),
        ("Ridge regression (λ = 0.005): the drivers move together",
         "The drivers rise and fall together, which makes ordinary regression unstable. So we use ridge regression, with a small penalty."),
        ("Train 2021–2024  →  test on 2025, never seen",
         "We split by time: train on 2021 to 2024, then test on 2025. The model never sees the test months, just like a real forecast."),
        ("Test error (WAPE): Total 1.51%  ·  Scope 1 1.45%  ·  Scope 2 11.12%",
         "On 2025, the total forecast was off by only one point five one percent. Scope 1, one point four five. Scope 2 is harder to predict, at about eleven percent."),
    ], chip="utils/analytics.py · stirpat_forecast"),
    code("stirpat_forecast() in code", "utils/analytics.py", [
        ("Design matrix", "def _stirpat_design", 15,
         "First, the model's inputs. We take the log of P, A and T, and add one dummy column per company, which gives each company its own constant, alpha."),
        ("Reported data only", 'reported = panel[~panel["synthetic"]]', 3,
         "Inside stirpat_forecast, synthetic months are dropped before fitting, and we need at least two years of history."),
        ("Split by time", "cut = months[int(len(months)", 2,
         "The cut point is eighty percent of the way through the months. Everything before it trains; everything after it tests."),
        ("Fit and test", "    def fit(frame", 6,
         "fit is a ridge regression on the log of the target. We predict the test months, then take the exponential to get back to million tonnes."),
        ("Project the drivers", "logs = np.log(panel.set_index", 7,
         "To forecast, we need future drivers. Each future month is last year's value, grown by its own year-on-year change, which keeps the seasonal pattern."),
        ("Refit and report", "final = fit(reported)", 2,
         "Then we refit on every reported month, predict six months ahead, and return the forecast together with its accuracy measures."),
    ], view=("def _stirpat_design", "test_wape_pct=float(")),
    code("simulation.py: the what-if levers", "utils/simulation.py", [
        ("Levers are data", "SCOPE1_LEVERS = (", 8,
         "Back to the What-If Simulator. The eight levers are just data: a key, a label and a summary. The page loops over them to draw the sliders."),
        ("Lever → fuel map", "LEVER_SOURCES: dict", 18,
         "This table says which levers act on each emission source. Mobile petrol, for example, is affected by both the petrol cut and fleet EV adoption."),
        ("Scope totals", "# Workbook rows", 7,
         "Our workbook only holds scope totals, so every lever counts as an equal share of its scope. Cutting diesel by fifty percent on its own reduces Scope 1 by ten percent. The comment marks this as a known simplification."),
        ("Average the levers", "def reduction_fractions", 11,
         "reduction_fractions averages the levers acting on each source. So petrol cut by forty percent, with no EVs, gives a twenty percent reduction."),
        ("Apply to every record", "def simulate_emissions", 4,
         "And simulate_emissions maps those fractions onto every record and scales its CO₂e, in one vectorised line, with no loops."),
    ], view=("SCOPE1_LEVERS = (", "return df[\"co2e_kg\"] * (1 - fractions)")),
    diagram("AI advisor: grounded in the page",
        boxes={
            "role": (90, 200, 380, 110, "visible_rows()", "only data this role may see"),
            "page": (90, 420, 380, 110, "Page on screen", "filters + charts"),
            "ctx": (560, 420, 400, 110, "chat_context()", "plain-text brief of the figures"),
            "msg": (1050, 420, 380, 110, "Message", "Page data + question + rules"),
            "llm": (1520, 420, 330, 110, "Groq API", "GPT-OSS 120B"),
            "ans": (1050, 680, 380, 110, "Answer", "quotes real figures"),
            "fail": (1520, 680, 330, 110, "Offline?", "polite message, no crash"),
        },
        arrows=[("role", "page"), ("page", "ctx"), ("ctx", "msg"), ("msg", "llm"), ("llm", "ans")],
        steps=[
            ({"page", "ctx"}, "Now the AI advisor. The big risk with chatbots is that they invent numbers. The fix here is grounding: with every question, we send the exact figures the user is looking at."),
            ({"role", "page"}, "Those figures come from data already filtered by role, so a company user's chatbot cannot reveal another company's numbers."),
            ({"msg", "llm"}, "Each question is wrapped with that page data and a short reminder of the answer rules, then sent to GPT-OSS on Groq."),
            ({"ans", "fail"}, "The model answers with real figures. If the API is down or not configured, the user gets a polite message instead of an error."),
        ], chip="utils/ui.py → utils/analytics.py → utils/ai_helper.py"),
    code("ai_helper.py: a careful API client", "utils/ai_helper.py", [
        ("No key, no crash", "if not is_api_configured()", 2,
         "Here's the client. Without an API key, it returns a helpful message straight away."),
        ("One request", "    def post()", 8,
         "Each request sends the system instructions first, then the conversation, in the OpenAI-compatible chat format, with a timeout so the page never hangs."),
        ("Retry on 429", "if response.status_code == 429", 4,
         "If Groq says we're sending too fast, status 429, we wait as told, up to ten seconds, and retry once."),
        ("Fail safely", "    except Exception:", 4,
         "Any other failure is logged for operators, and the user sees a calm message without technical details."),
        ("Attach page data", "def chat_response", 9,
         "chat_response is what the chat widget calls. It puts the page data before the question and the answer rules after it, because models follow rules that sit close to the question."),
    ], view=("def _complete", '"The AI chatbot")')),
    code("report.py: the carbon tax statement", "utils/report.py", [
        ("Pick the months", "def statement_months", 8,
         "The carbon tax statement. statement_months picks the company's months for the chosen year or quarter, reusing the same monthly summary the Data Centre table uses."),
        ("Amount in words", "def _words(n: int)", 17,
         "This small recursive function writes numbers in words: ones, tens, hundreds, then thousands, millions and billions. It's what turns 44.25 into forty-four ringgit and twenty-five sen."),
        ("Build the PDF", "def build_statement", 15,
         "build_statement refuses an empty period, sets the thirty-day due date, and builds reference and invoice numbers from the company and the months."),
        ("Totals and tax", 'months["Total"] = months[S1_COL]', 4,
         "Then it adds the scopes, applies the tax rate, and lays out the three parts of the PDF with ReportLab. The Data Centre only builds it when the download button is clicked."),
    ], view=("def statement_months", 'payable = total * tax_rate')),
    code("Small details that protect users", "utils/analytics.py", [
        ("CSV formula injection", "def to_safe_csv", 10,
         "Some small details protect users. A text cell starting with an equals sign can run as a formula when a CSV file opens in Excel. to_safe_csv neutralises those cells."),
        ("One-character fix", "def _neutralise_formula", 4,
         "The fix is one character: an apostrophe in front, which tells the spreadsheet to treat the cell as text. In the same spirit, text placed into HTML is escaped, and all SQL uses placeholders."),
    ], view=("def to_safe_csv", "    return value")),
    reveal("Tests: 79 unit tests, all passing", [
        ("analytics 30 · data_manager 19 · simulation 9 · report 7 · core 7 · auth 4 · ai_helper 3",
         "Finally, tests. There are seventy-nine unit tests across seven files, covering the calculations, the ledger, the forecast, the simulator, the PDF, access control and the AI client."),
        ("`Ran 79 tests ... OK",
         "Data manager tests point the database at a temporary file, so they never touch the real ledger. I ran the full suite for this video, and all seventy-nine pass."),
    ], chip="python -m unittest"),
    reveal("Recap: follow one entry", [
        ("auth → who are you, and which rows may you see?",
         "Let's recap by following one entry. auth decides who you are, and which rows you may see."),
        ("carbon_calculator → quantity × factor → CO₂e → tax",
         "carbon_calculator turns your quantity into CO₂e and carbon tax."),
        ("data_manager → validate, score, route, log",
         "data_manager validates it, scores it, routes it to the ledger or the queue, and logs every step."),
        ("analytics → filter, totals, STIRPAT forecast",
         "analytics filters, totals, and forecasts it."),
        ("pages show it · ai_helper explains it · report bills it",
         "And the pages show it, the AI advisor explains it, and the report turns it into a tax statement. If you remember one thing: pages show, utils compute, and the ledger never forgets. Thanks for watching."),
    ]),
]


# ── Helpers ───────────────────────────────────────────────────────────────────
_SPOKEN = [
    ("CO₂e", "C O 2 equivalent"), ("CO₂", "C O 2"), ("SPK", "S P K"), ("STIRPAT", "STIR-pat"),
    ("SQLite", "S Q Lite"), ("app.py", "app dot pie"), ("ui.py", "U I dot pie"), ("report.py", "report dot pie"),
    ("config.py", "config dot pie"), ("hmac", "H mac"), ("st.navigation", "S T dot navigation"),
    ("SEDG", "S E D G"), ("GPT-OSS", "G P T O S S"), ("ValueError", "value error"), ("eighty-twenty", "eighty twenty"),
]

def spoken(text):
    for a, b in _SPOKEN:
        text = text.replace(a, b)
    return text.replace("_", " ")

def strip_emoji(s):
    return "".join(c for c in s if ord(c) < 0x2600 or 0x27C0 <= ord(c) <= 0xFFFF and c != "️")

def find_line(lines, anchor, start=0):
    if "\n" in anchor:  # multi-line anchor: match on the joined text
        text = "\n".join(lines[start:])
        pos = text.find(anchor)
        if pos < 0:
            raise SystemExit(f"anchor not found: {anchor!r}")
        return start + text[:pos].count("\n")
    for i in range(start, len(lines)):
        if anchor in lines[i]:
            return i
    raise SystemExit(f"anchor not found: {anchor!r}")

def wrap(draw, text, fnt, width):
    out, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width:
            line = trial
        else:
            out.append(line)
            line = word
    return out + [line]

def rbox(d, xy, fill=None, outline=None, r=14, w=2):
    d.rounded_rectangle(xy, r, fill=fill, outline=outline, width=w)

def blend(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))

def token_color(ttype):
    for t, c in TOKEN_COLORS:
        if ttype in t:
            return c
    return "#c8d1df"


# ── Frame drawing ─────────────────────────────────────────────────────────────
def frame_base(idx, total, title, chip, caption, progress):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 96), fill="#0f1830")
    d.line((0, 96, W, 96), fill=BORDER, width=2)
    badge = f"{idx:02d} / {total:02d}"
    bw = d.textlength(badge, font=F_BADGE) + 36
    rbox(d, (40, 26, 40 + bw, 72), fill="#16a34a", r=23, w=0)
    d.text((58, 31), badge, font=F_BADGE, fill="white")
    d.text((70 + bw, 20), title, font=F_TITLE, fill=TEXT)
    if chip:
        cw = d.textlength(chip, font=F_CHIP) + 36
        rbox(d, (W - 40 - cw, 26, W - 40, 72), fill=BLUE_CHIP, outline="#2b4a8a", r=10, w=1)
        d.text((W - 22 - cw, 35), chip, font=F_CHIP, fill="#bcd3ff")
    if caption:
        lines = wrap(d, caption, F_CAP, 1700)
        fnt = F_CAP
        if len(lines) > 3:
            fnt = font("segoeui.ttf", 27)
            lines = wrap(d, caption, fnt, 1720)
        lh = fnt.size + 11
        top = 1040 - len(lines) * lh - 30
        rbox(d, (90, top, W - 90, 1040), fill="#0a1433", outline="#2b4a8a", r=16, w=2)
        for i, ln in enumerate(lines):
            x = (W - d.textlength(ln, font=fnt)) / 2
            d.text((x, top + 16 + i * lh), ln, font=fnt, fill=TEXT)
    d.rectangle((0, H - 8, W, H), fill="#101a30")
    d.rectangle((0, H - 8, int(W * progress), H), fill=GREEN)
    return img, d

def caption_top(d, caption):
    if not caption:
        return 1050
    lines = wrap(d, caption, F_CAP, 1700)
    n, size = (len(lines), F_CAP.size) if len(lines) <= 3 else (len(wrap(d, caption, font("segoeui.ttf", 27), 1720)), 27)
    return 1040 - n * (size + 11) - 30

def draw_code(scene, step_i, img, d):
    src = (ROOT / scene["file"]).read_text().splitlines()
    steps = scene["steps"]
    view = scene["view"]
    v0 = find_line(src, view[0]) if view else None
    spans = []
    for _, anchor, n, _ in steps:
        s = find_line(src, anchor, v0 or 0)
        spans.append((s, s + n - 1))
    if view:
        v1 = find_line(src, view[1], v0)
        v1 = max(v1, max(e for _, e in spans))
    else:
        v0, v1 = max(0, min(s for s, _ in spans) - 2), min(len(src) - 1, max(e for _, e in spans) + 2)
    hs, he = spans[step_i]
    # Step list
    y = 128
    for i, (label, *_rest) in enumerate(steps):
        active = i == step_i
        rbox(d, (40, y, 470, y + 64), fill=GREEN_DARK if active else PANEL,
             outline=GREEN if active else BORDER, r=12, w=2)
        if active:
            d.rectangle((40, y + 8, 46, y + 56), fill=GREEN)
        d.text((64, y + 16), label, font=F_STEP_B if active else F_STEP, fill="white" if active else MUTED)
        y += 76
    return src, v0, v1, hs, he

def render_code_panel(img, d, src, v0, v1, hs, he, bottom):
    x0, y0, x1 = 500, 120, W - 40
    rbox(d, (x0, y0, x1, bottom), fill="#0d1526", outline=BORDER, r=14, w=2)
    lh = 30
    rows = (bottom - y0 - 24) // lh
    total = v1 - v0 + 1
    if total <= rows:
        first = v0
    else:  # scroll so the highlight sits a third of the way down
        first = min(max(v0, hs - rows // 3), v1 - rows + 1)
        if he - first >= rows:
            first = hs - 1
    lexer = PythonLexer()
    full = "\n".join(src) + "\n"
    # Tokenise whole file once, then split per line, so multi-line strings colour correctly.
    per_line = [[]]
    for ttype, value in lexer.get_tokens(full):
        parts = value.split("\n")
        for k, part in enumerate(parts):
            if k:
                per_line.append([])
            if part:
                per_line[-1].append((ttype, part))
    max_chars = int((x1 - x0 - 110) / d.textlength("M", font=F_CODE))
    for r in range(rows):
        ln = first + r
        if ln >= len(src) or ln > v1 + 0:
            break
        ty = y0 + 12 + r * lh
        hl = hs <= ln <= he
        if hl:
            d.rectangle((x0 + 2, ty - 2, x1 - 2, ty + lh - 2), fill=HL_BG)
            d.rectangle((x0 + 2, ty - 2, x0 + 8, ty + lh - 2), fill=AMBER)
        num = str(ln + 1)
        d.text((x0 + 70 - d.textlength(num, font=F_CODE), ty), num, font=F_CODE,
               fill=AMBER if hl else "#4a5875")
        x = x0 + 92
        used = 0
        for ttype, text in per_line[ln] if ln < len(per_line) else []:
            text = strip_emoji(text)
            if used + len(text) > max_chars:
                text = text[:max(0, max_chars - used - 1)] + "…"
            color = token_color(ttype)
            if not hl:
                color = blend(color, "#0d1526", 0.45)
            d.text((x, ty), text, font=F_CODE, fill=color)
            x += d.textlength(text, font=F_CODE)
            used += len(text)
            if used >= max_chars:
                break

def draw_reveal(scene, step_i, d, bottom):
    lines = scene["lines"]
    n = len(lines)
    gap = min(120, (bottom - 170) // max(n, 1))
    top = 140 + max(0, (bottom - 140 - gap * n) // 2)
    for i, (text, _) in enumerate(lines[:step_i + 1]):
        y = top + i * gap
        active = i == step_i
        mono = text.startswith("`")
        text = text.lstrip("`")
        fnt = F_LINE_MONO if mono else F_LINE
        while d.textlength(text, font=fnt) > 1600:
            fnt = ImageFont.truetype(fnt.path, fnt.size - 2)
        rbox(d, (140, y, W - 140, y + gap - 22), fill="#12301f" if active else PANEL,
             outline=GREEN if active else BORDER, r=14, w=2)
        color = "white" if active else blend(TEXT, PANEL, 0.25)
        th = fnt.size
        d.text((180, y + (gap - 22 - th) / 2 - 6), text, font=fnt, fill=AMBER if (mono and active) else color)

def draw_diagram(scene, step_i, d):
    lit = scene["steps"][step_i][0]
    dim_all = not lit
    for label, gy in scene["groups"]:
        tw = d.textlength(label, font=F_GROUP)
        d.text(((W - tw) / 2, gy - 6), label, font=F_GROUP, fill="#6ee7b7")
    boxes = scene["boxes"]

    def center(b):
        x, y, w, h = boxes[b][:4]
        return x + w / 2, y + h / 2

    def edge(box, cx, cy, tx, ty):
        """Where the line from the box centre towards (tx, ty) leaves the box."""
        _, _, w, h = boxes[box][:4]
        dx, dy = tx - cx, ty - cy
        t = min((w / 2) / abs(dx) if dx else 9e9, (h / 2) / abs(dy) if dy else 9e9)
        return cx + dx * t, cy + dy * t

    for a, b in scene["arrows"]:
        (ax, ay), (bx, by) = center(a), center(b)
        sx, sy = edge(a, ax, ay, bx, by)
        ex, ey = edge(b, bx, by, ax, ay)
        on = a in lit and b in lit
        col = GREEN if on else "#3a4a68"
        d.line((sx, sy, ex, ey), fill=col, width=4 if on else 3)
        import math
        ang = math.atan2(ey - sy, ex - sx)
        for s in (2.6, -2.6):
            d.line((ex, ey, ex - 18 * math.cos(ang + s / 6), ey - 18 * math.sin(ang + s / 6)), fill=col, width=4)
    for key, (x, y, w, h, t, sub) in boxes.items():
        on = key in lit or dim_all
        rbox(d, (x, y, x + w, y + h), fill="#12301f" if key in lit else PANEL,
             outline=GREEN if key in lit else BORDER, r=14, w=3 if key in lit else 2)
        tf = F_BOX
        while d.textlength(t, font=tf) > w - 20:
            tf = ImageFont.truetype(tf.path, tf.size - 1)
        sf = F_BOX_SUB
        while d.textlength(sub, font=sf) > w - 16:
            sf = ImageFont.truetype(sf.path, sf.size - 1)
        tc = "white" if on else blend(TEXT, PANEL, 0.55)
        sc = MUTED if on else blend(MUTED, PANEL, 0.55)
        d.text((x + (w - d.textlength(t, font=tf)) / 2, y + h / 2 - tf.size - 2), t, font=tf, fill=tc)
        d.text((x + (w - d.textlength(sub, font=sf)) / 2, y + h / 2 + 6), sub, font=sf, fill=sc)

def draw_title(scene, step_i, d):
    t = scene["title"]
    d.text(((W - d.textlength(t, font=F_BIG)) / 2, 330), t, font=F_BIG, fill="white")
    s = scene["subtitle"]
    d.text(((W - d.textlength(s, font=F_SUB)) / 2, 460), s, font=F_SUB, fill="#6ee7b7")
    if step_i >= 1:
        items = "Architecture  ·  Roles  ·  CO₂e & tax  ·  Ledger & anomalies  ·  STIRPAT  ·  What-if  ·  AI  ·  PDF  ·  Tests"
        d.text(((W - d.textlength(items, font=F_STEP)) / 2, 560), items, font=F_STEP, fill=MUTED)


def steps_of(scene):
    if scene["kind"] == "code":
        return [s[3] for s in scene["steps"]]
    if scene["kind"] == "reveal":
        return [s[1] for s in scene["lines"]]
    if scene["kind"] == "diagram":
        return [s[1] for s in scene["steps"]]
    return scene["steps"]

def render_frame(si, step_i, caption, progress):
    scene = SCENES[si]
    chip = scene.get("chip", "")
    if scene["kind"] == "code":
        chip = scene["file"]
    title = "" if scene["kind"] == "title" else scene["title"]
    img, d = frame_base(si + 1, len(SCENES), title, chip, caption, progress)
    bottom = caption_top(d, caption) - 24
    if scene["kind"] == "code":
        src, v0, v1, hs, he = draw_code(scene, step_i, img, d)
        render_code_panel(img, d, src, v0, v1, hs, he, bottom)
        d.text((40, bottom - 4 - 26), f"lines {hs + 1}–{he + 1}", font=F_CHIP, fill=AMBER)
    elif scene["kind"] == "reveal":
        draw_reveal(scene, step_i, d, bottom)
    elif scene["kind"] == "diagram":
        draw_diagram(scene, step_i, d)
    else:
        draw_title(scene, step_i, d)
    return img


# ── Audio ─────────────────────────────────────────────────────────────────────
async def tts_all(texts):
    sem = asyncio.Semaphore(2)
    async def one(text):
        path = WORK / "tts" / (hashlib.sha1((VOICE + text).encode()).hexdigest()[:16] + ".mp3")
        async with sem:
            for attempt in range(6):  # the free service throttles bursts; back off and retry
                if path.exists() and path.stat().st_size > 1000:
                    break
                try:
                    await edge_tts.Communicate(spoken(text), VOICE, rate="+0%").save(str(path))
                except edge_tts.exceptions.EdgeTTSException:
                    path.unlink(missing_ok=True)
                    await asyncio.sleep(3 * (attempt + 1))
            else:
                raise SystemExit(f"TTS failed: {text[:60]}")
        return path
    return await asyncio.gather(*(one(t) for t in texts))

def to_pcm(mp3):
    wav = mp3.with_suffix(".wav")
    if not wav.exists():
        subprocess.run([FF, "-v", "error", "-y", "-i", str(mp3), "-ar", "24000", "-ac", "1", str(wav)], check=True)
    with wave.open(str(wav)) as w:
        return w.readframes(w.getnframes())


def build(voice: bool):
    plan = [(si, k, text) for si, sc in enumerate(SCENES) for k, text in enumerate(steps_of(sc))]
    if voice:
        pcms = [to_pcm(p) for p in asyncio.run(tts_all([t for *_, t in plan]))]
        durs = [len(p) / 2 / 24000 + 0.8 + (0.6 if k == 0 else 0) for p, (_, k, _) in zip(pcms, plan)]
    else:
        durs = [max(4.5, len(t.split()) / 3.2 + 1.8) + (0.8 if k == 0 else 0) for _, k, t in plan]
    total = sum(durs)
    name = "voice" if voice else "novoice"
    fdir = WORK / f"frames_{name}"
    fdir.mkdir(parents=True, exist_ok=True)
    listing, elapsed = [], 0.0
    for n, ((si, k, text), dur) in enumerate(zip(plan, durs)):
        path = fdir / f"{n:03d}.png"
        render_frame(si, k, text, (elapsed + dur) / total).save(path)
        listing += [f"file '{path}'", f"duration {dur:.3f}"]
        elapsed += dur
    listing.append(f"file '{fdir / f'{len(plan) - 1:03d}.png'}'")
    (WORK / f"{name}.txt").write_text("\n".join(listing) + "\n")
    cmd = [FF, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(WORK / f"{name}.txt")]
    if voice:
        audio = bytearray()
        for (si, k, _), pcm, dur in zip(plan, pcms, durs):
            lead = int((0.6 if k == 0 else 0) * 24000) * 2
            body = bytes(lead) + pcm
            audio += body + bytes(max(0, int(dur * 24000) * 2 - len(body)))
        with wave.open(str(WORK / "voice.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(bytes(audio))
        cmd += ["-i", str(WORK / "voice.wav"), "-c:a", "aac", "-b:a", "128k"]
    out = OUT / ("Demo_4_Code_Walkthrough_Voice.mp4" if voice else "Demo_4_Code_Walkthrough_NoVoice.mp4")
    cmd += ["-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-tune", "stillimage", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    print(f"{out.name}: {total / 60:.1f} min, {len(plan)} steps")


if __name__ == "__main__":
    (WORK / "tts").mkdir(parents=True, exist_ok=True)
    if "--preview" in sys.argv:  # one PNG per scene (first and last step) for checking layout
        pv = WORK / "preview"
        pv.mkdir(exist_ok=True)
        for si, sc in enumerate(SCENES):
            texts = steps_of(sc)
            for k in sorted({0, len(texts) - 1}):
                render_frame(si, k, texts[k], 0.5).save(pv / f"{si:02d}_{k}.png")
        sys.exit()
    build(voice=False)
    build(voice=True)
