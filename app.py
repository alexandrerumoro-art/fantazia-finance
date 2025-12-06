import json
import os
import base64
import hashlib
import secrets
from typing import Dict, List, Tuple, Optional, Callable

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import requests


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Fantazia Finance — Comparateur V3 (comptes)",
    layout="wide"
)


# =========================================================
# OPTIONAL AUTO-REFRESH SUPPORT
# =========================================================
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except Exception:
    HAS_AUTOREFRESH = False


# =========================================================
# THEME LIGHT FANTAZIA (PAS DE FOND NOIR GLOBAL)
# =========================================================
def apply_fantazia_theme():
    accent = "#f5c400"        # jaune
    accent_soft = "#ffdd55"

    lines = [
        "<style>",

        # Boutons principaux
        ".stButton>button {",
        f"background: {accent};",
        "color: #0a0a0a;",
        "border: 0px solid transparent;",
        "border-radius: 10px;",
        "font-weight: 700;",
        "padding: 0.45rem 0.9rem;",
        "box-shadow: 0 4px 12px rgba(0,0,0,0.15);",
        "}",

        ".stButton>button:hover {",
        f"background: {accent_soft};",
        "color: #000;",
        "}",

        # Onglet sélectionné avec un petit soulignement jaune
        "button[data-baseweb='tab'][aria-selected='true'] {",
        f"border-bottom: 2px solid {accent};",
        "}",

        # Metrics (Prix actuels etc.)
        "[data-testid='stMetric'] {",
        "padding: 10px 12px;",
        "border-radius: 12px;",
        "background: rgba(245,245,245,0.9);",
        "border: 1px solid rgba(0,0,0,0.06);",
        "}",

        "</style>",
    ]
    st.markdown("\n".join(lines), unsafe_allow_html=True)


apply_fantazia_theme()


# =========================================================
# WATERMARK LOGO (SUR FOND CLAIR)
# =========================================================
def set_watermark_logo(paths: List[str], opacity: float = 0.06, size_px: int = 320):
    found = None
    for p in paths:
        if p and os.path.exists(p):
            found = p
            break

    if not found:
        return

    try:
        with open(found, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()

        ext = os.path.splitext(found)[1].lower()
        mime = "png" if ext == ".png" else "jpg"

        lines = [
            "<style>",
            "[data-testid='stAppViewContainer']::after {",
            "content: '';",
            "position: fixed;",
            f"width: {size_px}px;",
            f"height: {size_px}px;",
            "right: 24px;",
            "bottom: 24px;",
            f"background-image: url('data:image/{mime};base64,{b64}');",
            "background-repeat: no-repeat;",
            "background-position: center;",
            "background-size: contain;",
            f"opacity: {opacity};",
            "pointer-events: none;",
            "z-index: 0;",
            "}",
            "[data-testid='stAppViewContainer'] > .main {",
            "position: relative;",
            "z-index: 1;",
            "}",
            "</style>",
        ]
        st.markdown("\n".join(lines), unsafe_allow_html=True)
    except Exception:
        return


BG_PATHS = [
    r"C:\bourse-dashboard\Fantazia finance logo chatgpt.png",
    r"Fantazia finance logo chatgpt.png",
]

set_watermark_logo(BG_PATHS, opacity=0.06, size_px=320)


# =========================================================
# PETITE FONCTION DE RERUN
# =========================================================
def rerun_app():
    try:
        st.experimental_rerun()
    except Exception:
        try:
            st.rerun()
        except Exception:
            pass


# =========================================================
# FICHIERS LOCAUX
# =========================================================
USERS_FILE = "users.json"          # comptes utilisateurs
WATCHLIST_FILE = "watchlists.json" # watchlists par utilisateur
CONFIG_FILE = "config.json"        # clés API


# =========================================================
# GESTION UTILISATEURS (COMPTES)
# =========================================================
def load_users() -> Dict[str, Dict[str, str]]:
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_users(users: Dict[str, Dict[str, str]]) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def ensure_authenticated() -> str:
    """
    Affiche un écran Login / Signup tant que l'utilisateur n'est pas connecté.
    Retourne le pseudo (en lowercase) quand connecté.
    """
    if "user" in st.session_state and st.session_state["user"]:
        return st.session_state["user"]

    st.title("🔐 Fantazia Finance — Connexion")
    st.write("Crée un compte ou connecte-toi pour utiliser le terminal Fantazia Finance.")

    mode = st.radio("Je veux :", ["Se connecter", "Créer un compte"], horizontal=True)

    username_input = st.text_input("Pseudo (min. 3 caractères)")
    password_input = st.text_input("Mot de passe (min. 6 caractères)", type="password")
    msg = st.empty()

    users = load_users()

    if mode == "Créer un compte":
        password_confirm = st.text_input("Confirmer le mot de passe", type="password")
        if st.button("Créer mon compte"):
            username = username_input.strip().lower()
            pwd = password_input
            pwd2 = password_confirm

            if not username or len(username) < 3:
                msg.error("Pseudo trop court (min. 3 caractères).")
            elif username in users:
                msg.error("Ce pseudo existe déjà.")
            elif not pwd or len(pwd) < 6:
                msg.error("Mot de passe trop court (min. 6 caractères).")
            elif pwd != pwd2:
                msg.error("Les mots de passe ne correspondent pas.")
            else:
                salt = secrets.token_hex(16)
                pwd_hash = hash_password(pwd, salt)
                users[username] = {"password_hash": pwd_hash, "salt": salt}
                save_users(users)
                st.session_state["user"] = username
                msg.success("Compte créé et connecté ✅")
                rerun_app()
    else:
        if st.button("Se connecter"):
            username = username_input.strip().lower()
            pwd = password_input

            if not username or not pwd:
                msg.error("Entre un pseudo et un mot de passe.")
            elif username not in users:
                msg.error("Utilisateur introuvable.")
            else:
                user_rec = users[username]
                salt = user_rec.get("salt", "")
                expected = user_rec.get("password_hash", "")
                if not salt or not expected:
                    msg.error("Compte corrompu dans users.json.")
                else:
                    if hash_password(pwd, salt) == expected:
                        st.session_state["user"] = username
                        msg.success("Connexion réussie ✅")
                        rerun_app()
                    else:
                        msg.error("Mot de passe incorrect.")

    # Tant qu'on n'est pas connecté, on stoppe l'app ici.
    st.stop()


# =========================================================
# UTILISATEUR COURANT (OBLIGATOIRE AVANT DE CONTINUER)
# =========================================================
CURRENT_USER = ensure_authenticated()


# =========================================================
# PRESETS SECTEURS
# =========================================================
SECTORS = {
    "Mega Tech US": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"],
    "Semi-conducteurs": ["NVDA", "AMD", "INTC", "TSM", "ASML"],
    "Banques US": ["JPM", "BAC", "WFC", "C", "GS", "MS"],
    "Pétrole & Énergie": ["XOM", "CVX", "SHEL", "TTE", "BP"],
    "Luxe (Europe)": ["MC.PA", "RMS.PA", "KER.PA", "PRU.L", "BRBY.L"],
}


# =========================================================
# CONFIG API KEYS
# =========================================================
def load_config() -> Dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


CONFIG = load_config()
TWELVE_API_KEY = str(CONFIG.get("TWELVE_API_KEY", "")).strip()
FINNHUB_API_KEY = str(CONFIG.get("FINNHUB_API_KEY", "")).strip()
POLYGON_API_KEY = str(CONFIG.get("POLYGON_API_KEY", "")).strip()


# =========================================================
# WATCHLISTS (PAR UTILISATEUR)
# =========================================================
def load_watchlists(user: str) -> Dict[str, List[str]]:
    """
    Structure attendue dans watchlists.json :
    {
      "alex": {
        "Tech US": ["AAPL", "MSFT"],
        "Banques": ["JPM", "BAC"]
      },
      "autre_user": { ... }
    }

    Si ancien format (dict simple de watchlists), on le prend pour l'utilisateur courant.
    """
    if not os.path.exists(WATCHLIST_FILE):
        return {}

    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    if isinstance(data, dict):
        # Nouveau format par utilisateur
        if user in data and isinstance(data[user], dict):
            base = data[user]
        # Ancien format global : { "Tech": [...], "Banques": [...] }
        elif all(isinstance(v, list) for v in data.values()):
            base = data
        else:
            base = {}
    else:
        base = {}

    clean = {}
    for name, vals in base.items():
        if isinstance(vals, list):
            clean[name] = [str(x).upper().strip() for x in vals if str(x).strip()]
    return clean


def save_watchlists(user: str, wl: Dict[str, List[str]]) -> None:
    """
    On charge l'ancien fichier, on remplace uniquement la clé de l'utilisateur courant,
    et on réécrit le JSON.
    """
    data = {}
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                tmp = json.load(f)
            if isinstance(tmp, dict):
                data = tmp
        except Exception:
            data = {}

    data[user] = wl
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_tickers(text: str) -> List[str]:
    return [t.strip().upper() for t in text.split(",") if t.strip()]


# =========================================================
# DISPLAY HELPERS — SOURCES + BADGES + ROW COLOR
# =========================================================
def pretty_source_name(s: str) -> str:
    s = (s or "").lower().strip()
    if s == "yfinance":
        return "🟡 Yahoo"
    if s == "twelve data":
        return "🔵 Twelve"
    if s == "finnhub":
        return "🟢 Finnhub"
    if s == "polygon":
        return "🟣 Polygon"
    if s == "none":
        return "⚪ N/A"
    return s


def source_badge_style(val: str) -> str:
    v = str(val)
    if "Yahoo" in v:
        return "background-color: rgba(245,196,0,0.18); color: #b18800; font-weight: 700;"
    if "Twelve" in v:
        return "background-color: rgba(80,140,255,0.18); color: #2f59b7; font-weight: 700;"
    if "Finnhub" in v:
        return "background-color: rgba(60,200,120,0.18); color: #218850; font-weight: 700;"
    if "Polygon" in v:
        return "background-color: rgba(170,120,255,0.18); color: #6c3ec2; font-weight: 700;"
    if "N/A" in v:
        return "background-color: rgba(0,0,0,0.04); color: #555;"
    return ""


def row_color_by_score(row: pd.Series) -> List[str]:
    """
    Colore la ligne en fonction du Score Global :
    - > 1.0 : vert fort
    - > 0 : vert léger
    - < -1.0 : rouge fort
    - < 0 : rouge léger
    Sinon neutre.
    """
    score = row.get("Score Global", np.nan)
    base_style = ""
    if pd.isna(score):
        return [base_style] * len(row)

    if score > 1.0:
        bg = "rgba(0, 200, 100, 0.18)"
    elif score > 0:
        bg = "rgba(0, 180, 80, 0.10)"
    elif score < -1.0:
        bg = "rgba(230, 60, 60, 0.18)"
    elif score < 0:
        bg = "rgba(230, 80, 80, 0.10)"
    else:
        bg = "rgba(0,0,0,0)"

    style = f"background-color: {bg};"
    return [style] * len(row)


# =========================================================
# METRICS HELPERS
# =========================================================
def safe_numeric(df, col):
    return pd.to_numeric(df.get(col), errors="coerce")


def zscore(s: pd.Series):
    s = s.astype(float)
    s_clean = s.dropna()
    if s_clean.empty:
        return s * np.nan
    std = s_clean.std(ddof=0)
    if std == 0 or np.isnan(std):
        return s * 0
    return (s - s_clean.mean()) / std


def rolling_return(prices: pd.DataFrame, days: int):
    if prices.empty or len(prices) <= days:
        return pd.Series(index=prices.columns, dtype=float)
    return prices.iloc[-1] / prices.iloc[-days] - 1.0


def calendar_return_years(prices: pd.DataFrame, years: int = 1):
    if prices.empty:
        return pd.Series(index=prices.columns, dtype=float)

    out = {}
    last_date = prices.index[-1]
    target_date = last_date - pd.DateOffset(years=years)

    for col in prices.columns:
        s = prices[col].dropna()
        if s.empty:
            out[col] = np.nan
            continue

        s_after = s.loc[s.index >= target_date]
        if s_after.empty:
            out[col] = np.nan
            continue

        start = s_after.iloc[0]
        end = s.iloc[-1]
        out[col] = (end / start) - 1.0

    return pd.Series(out)


def annualized_vol(prices: pd.DataFrame):
    if prices.empty or len(prices) < 20:
        return pd.Series(index=prices.columns, dtype=float)
    rets = prices.pct_change().dropna()
    return rets.std() * np.sqrt(252)


def max_drawdown(prices: pd.DataFrame):
    if prices.empty:
        return pd.Series(index=prices.columns, dtype=float)
    dd = {}
    for col in prices.columns:
        s = prices[col].dropna()
        if s.empty:
            dd[col] = np.nan
            continue
        cummax = s.cummax()
        draw = (s / cummax) - 1.0
        dd[col] = draw.min()
    return pd.Series(dd)


def normalize_cols(df: pd.DataFrame):
    df = df.copy()
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df


def filter_period_series(s: pd.Series, period: str) -> pd.Series:
    if s is None or s.empty:
        return pd.Series(dtype=float)

    s = s.sort_index()
    last_date = s.index.max()

    start = None
    if period == "1d":
        start = last_date - pd.Timedelta(days=1)
    elif period == "5d":
        start = last_date - pd.Timedelta(days=5)
    elif period == "1mo":
        start = last_date - pd.DateOffset(months=1)
    elif period == "3mo":
        start = last_date - pd.DateOffset(months=3)
    elif period == "1y":
        start = last_date - pd.DateOffset(years=1)
    elif period == "3y":
        start = last_date - pd.DateOffset(years=3)
    elif period == "5y":
        start = last_date - pd.DateOffset(years=5)

    if start is not None:
        s = s.loc[s.index >= start]

    return s


def filter_period_df(df: pd.DataFrame, period: str) -> pd.DataFrame:
    if df.empty:
        return df
    out = []
    for col in df.columns:
        s = df[col].dropna()
        s = filter_period_series(s, period)
        if not s.empty:
            out.append(s.rename(col))
    if not out:
        return pd.DataFrame()
    return pd.concat(out, axis=1).dropna(how="all")


# =========================================================
# PRICE PROVIDERS (SINGLE)
# =========================================================
def fetch_yfinance_single(ticker: str, period: str, auto_adjust: bool) -> pd.Series:
    try:
        data = yf.download([ticker], period=period, auto_adjust=auto_adjust, progress=False)
        if data is None or data.empty:
            return pd.Series(dtype=float)

        close = data["Close"] if "Close" in data else data
        if isinstance(close, pd.DataFrame):
            if ticker in close.columns:
                s = close[ticker]
            else:
                s = close.iloc[:, 0]
        else:
            s = close

        s = pd.to_numeric(s, errors="coerce").dropna()
        s.name = ticker.upper()
        return s
    except Exception:
        return pd.Series(dtype=float)


def fetch_twelve_single(ticker: str, period: str) -> pd.Series:
    if not TWELVE_API_KEY:
        return pd.Series(dtype=float)
    try:
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": ticker,
            "interval": "1day",
            "outputsize": 5000,
            "apikey": TWELVE_API_KEY,
            "format": "JSON",
        }
        r = requests.get(url, params=params, timeout=20)
        if r.status_code == 429:
            return pd.Series(dtype=float)

        data = r.json() if r.content else {}
        if isinstance(data, dict) and data.get("status") == "error":
            return pd.Series(dtype=float)

        values = data.get("values", []) if isinstance(data, dict) else []
        if not values:
            return pd.Series(dtype=float)

        df = pd.DataFrame(values)
        if "datetime" not in df.columns or "close" not in df.columns:
            return pd.Series(dtype=float)

        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        df = df.dropna(subset=["datetime"]).sort_values("datetime").set_index("datetime")

        s = pd.to_numeric(df["close"], errors="coerce").dropna()
        s.name = ticker.upper()
        return filter_period_series(s, period)
    except Exception:
        return pd.Series(dtype=float)


def fetch_finnhub_single(ticker: str, period: str) -> pd.Series:
    if not FINNHUB_API_KEY:
        return pd.Series(dtype=float)
    try:
        now = pd.Timestamp.utcnow()

        if period == "1d":
            start = now - pd.DateOffset(days=3)
        elif period == "5d":
            start = now - pd.DateOffset(days=10)
        elif period == "1mo":
            start = now - pd.DateOffset(months=2)
        elif period == "3mo":
            start = now - pd.DateOffset(months=4)
        elif period == "1y":
            start = now - pd.DateOffset(years=1)
        elif period == "3y":
            start = now - pd.DateOffset(years=3)
        else:
            start = now - pd.DateOffset(years=5)

        start_unix = int(start.timestamp())
        end_unix = int(now.timestamp())

        url = "https://finnhub.io/api/v1/stock/candle"
        params = {
            "symbol": ticker,
            "resolution": "D",
            "from": start_unix,
            "to": end_unix,
            "token": FINNHUB_API_KEY,
        }

        r = requests.get(url, params=params, timeout=20)
        if r.status_code == 429:
            return pd.Series(dtype=float)

        data = r.json() if r.content else {}
        if not isinstance(data, dict) or data.get("s") != "ok":
            return pd.Series(dtype=float)

        closes = data.get("c", [])
        times = data.get("t", [])
        if not closes or not times or len(closes) != len(times):
            return pd.Series(dtype=float)

        idx = pd.to_datetime(pd.Series(times, dtype="int64"), unit="s", utc=True).dt.tz_convert(None)
        s = pd.Series(closes, index=idx).astype(float).sort_index().dropna()
        s.name = ticker.upper()
        return filter_period_series(s, period)
    except Exception:
        return pd.Series(dtype=float)


# =========================================================
# REALTIME POLYGON
# =========================================================
def fetch_realtime_polygon_last(ticker: str) -> Optional[Tuple[float, pd.Timestamp]]:
    if not POLYGON_API_KEY:
        return None

    t = ticker.upper()
    url = f"https://api.polygon.io/v2/last/trade/{t}"
    params = {"apiKey": POLYGON_API_KEY}

    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 429:
            return None
        data = r.json() if r.content else {}
        last = data.get("last", {})
        price = last.get("p", None)
        ts = last.get("t", None)

        if price is None:
            return None

        dt = pd.to_datetime(int(ts), unit="ms", utc=True).tz_convert(None) if ts is not None else pd.Timestamp.utcnow()
        return float(price), dt
    except Exception:
        return None


def fetch_realtime_polygon_batch(tickers: List[str]) -> Dict[str, Tuple[float, pd.Timestamp]]:
    out: Dict[str, Tuple[float, pd.Timestamp]] = {}
    for t in tickers:
        res = fetch_realtime_polygon_last(t)
        if res:
            out[t.upper()] = res
    return out


# =========================================================
# FALLBACK PAR TICKER
# =========================================================
ProviderFn = Callable[[str, str, bool], pd.Series]


def provider_yahoo(ticker: str, period: str, auto_adjust: bool) -> pd.Series:
    return fetch_yfinance_single(ticker, period, auto_adjust)


def provider_twelve(ticker: str, period: str, auto_adjust: bool) -> pd.Series:
    _ = auto_adjust
    return fetch_twelve_single(ticker, period)


def provider_finnhub(ticker: str, period: str, auto_adjust: bool) -> pd.Series:
    _ = auto_adjust
    return fetch_finnhub_single(ticker, period)


def get_provider_chain(source_mode: str) -> List[Tuple[str, ProviderFn]]:
    if source_mode == "Yahoo Finance (yfinance)":
        return [("yfinance", provider_yahoo)]
    if source_mode == "Twelve Data":
        return [("twelve data", provider_twelve)]
    if source_mode == "Finnhub":
        return [("finnhub", provider_finnhub)]

    return [
        ("yfinance", provider_yahoo),
        ("twelve data", provider_twelve),
        ("finnhub", provider_finnhub),
    ]


@st.cache_data
def load_prices_per_ticker(
    tickers: List[str],
    period: str,
    auto_adjust: bool,
    source_mode: str,
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    tickers = [t.upper() for t in tickers if str(t).strip()]
    source_map: Dict[str, str] = {}
    series_list: List[pd.Series] = []

    chain = get_provider_chain(source_mode)

    for t in tickers:
        used = "none"
        s_final = pd.Series(dtype=float)

        for name, fn in chain:
            try:
                s = fn(t, period, auto_adjust)
                if s is not None and not s.empty:
                    s_final = s
                    used = name
                    break
            except Exception:
                continue

        source_map[t] = used
        if s_final is not None and not s_final.empty:
            series_list.append(s_final.rename(t))

    if not series_list:
        return pd.DataFrame(), source_map

    df = pd.concat(series_list, axis=1).dropna(how="all")
    df = normalize_cols(df)
    df = filter_period_df(df, period)
    df = normalize_cols(df)

    source_map = {t: source_map.get(t, "none") for t in df.columns}
    return df, source_map


# =========================================================
# FUNDAMENTALS (PRO)
# =========================================================
@st.cache_data
def load_fundamentals(tickers: List[str]) -> pd.DataFrame:
    rows = []
    for t in tickers:
        try:
            info = yf.Ticker(t).info
        except Exception:
            info = {}

        rows.append({
            "Ticker": t,
            "Nom": info.get("shortName") or info.get("longName") or "",
            "Secteur (API)": info.get("sector") or "",
            "Industrie (API)": info.get("industry") or "",
            "Pays": info.get("country") or "",
            "Devise": info.get("currency") or "",
            "Market Cap": info.get("marketCap"),
            "P/E (trailing)": info.get("trailingPE"),
            "P/B": info.get("priceToBook"),
            "ROE": info.get("returnOnEquity"),
            "Marge nette": info.get("profitMargins"),
            "Dette/Capitaux": info.get("debtToEquity"),
            "Div. Yield": info.get("dividendYield"),
            "Beta": info.get("beta"),
            "EPS (trailing)": info.get("trailingEps"),
            "52w High": info.get("fiftyTwoWeekHigh"),
            "52w Low": info.get("fiftyTwoWeekLow"),
            "Exchange": info.get("exchange"),
        })

    return pd.DataFrame(rows).set_index("Ticker")


# =========================================================
# TITRE / HEADER PRINCIPAL
# =========================================================
st.title("📈 Comparateur d'actions par secteur, Fait par Fantazia Finance ( Alexandre) — V3")
st.caption(f"Outil d'analyse perso local. Comptes utilisateurs + watchlists séparées. Connecté : **{CURRENT_USER}**.")


# =========================================================
# SIDEBAR
# =========================================================

# Logo en haut de la barre à gauche
try:
    st.sidebar.image(
        "Fantazia finance logo chatgpt.png",
        width=140
    )
except Exception:
    pass

st.sidebar.markdown("### Fantazia Finance")
st.sidebar.markdown(f"👤 Connecté : **{CURRENT_USER}**")

if st.sidebar.button("Se déconnecter"):
    st.session_state.clear()
    rerun_app()

st.sidebar.markdown("---")

st.sidebar.header("Mode de sélection")

watchlists_sidebar = load_watchlists(CURRENT_USER)

mode = st.sidebar.radio(
    "Choisis une source de tickers",
    ["Secteur (preset)", "Liste personnalisée", "Watchlist"],
    index=0
)

tickers: List[str] = []
sector_label = ""

if mode == "Secteur (preset)":
    sector_label = st.sidebar.selectbox("Secteur", list(SECTORS.keys()))
    tickers = SECTORS[sector_label]

elif mode == "Liste personnalisée":
    sector_label = "Liste perso"
    txt = st.sidebar.text_area("Tickers (séparés par virgules)", value="AAPL, MSFT, NVDA", height=80)
    tickers = parse_tickers(txt)

else:
    sector_label = "Watchlist"
    if watchlists_sidebar:
        wl_name = st.sidebar.selectbox("Choisis une watchlist", list(watchlists_sidebar.keys()))
        tickers = watchlists_sidebar.get(wl_name, [])
    else:
        st.sidebar.info("Aucune watchlist enregistrée pour ce compte.")
        tickers = []

st.sidebar.divider()

# Nouveaux historiques
history_period = st.sidebar.selectbox(
    "Historique à charger",
    ["1d", "5d", "1mo", "3mo", "1y", "3y", "5y"],
    index=4
)
use_auto_adjust = st.sidebar.checkbox("Prix ajustés (Yahoo)", value=True)

price_source_mode = st.sidebar.selectbox(
    "Source historique (fallback par action)",
    [
        "Auto (Yahoo → Twelve → Finnhub)",
        "Yahoo Finance (yfinance)",
        "Twelve Data",
        "Finnhub"
    ],
    index=0
)

use_realtime = st.sidebar.checkbox(
    "Activer prix temps réel (Premium Polygon)",
    value=False
)

refresh_seconds = st.sidebar.selectbox(
    "Auto-refresh (optionnel)",
    [0, 10, 20, 30, 60],
    index=0,
    help="Nécessite streamlit-autorefresh."
)

st.sidebar.divider()

# Message dynamique sur les clés API
api_status = []
if TWELVE_API_KEY:
    api_status.append("Twelve Data")
if FINNHUB_API_KEY:
    api_status.append("Finnhub")
if POLYGON_API_KEY:
    api_status.append("Polygon")

if api_status:
    st.sidebar.caption("Clés API détectées : " + ", ".join(api_status))
else:
    st.sidebar.caption("Aucune clé API détectée : mode Auto = Yahoo uniquement.")

if not tickers:
    st.warning("Aucun ticker sélectionné.")
    st.stop()

tickers = [t.upper() for t in tickers]


# =========================================================
# OPTIONAL AUTOREFRESH
# =========================================================
if refresh_seconds and HAS_AUTOREFRESH:
    st_autorefresh(interval=refresh_seconds * 1000, key="auto_refresh_key")


# =========================================================
# LOAD PRICES & FUNDAMENTALS AVANT TABS
# =========================================================
prices, source_map = load_prices_per_ticker(
    tickers=tickers,
    period=history_period,
    auto_adjust=use_auto_adjust,
    source_mode=price_source_mode
)

if prices.empty:
    st.error("Impossible de charger l'historique pour ces tickers.")
    st.stop()

fund = load_fundamentals(list(prices.columns)).reindex(prices.columns)


# =========================================================
# TABS
# =========================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard",
    "⭐ Watchlists",
    "💼 Simulateur",
    "📄 Fiche action",
    "ℹ️ Aide"
])


# =========================================================
# TAB 1 — DASHBOARD
# =========================================================
with tab1:
    # -------------------------
    # SOURCES PAR ACTION
    # -------------------------
    st.subheader("🧩 Sources historiques utilisées par action")
    src_df = pd.DataFrame(
        [{"Ticker": t, "Source historique": pretty_source_name(source_map.get(t, "none"))} for t in prices.columns]
    )
    try:
        styled_src = src_df.style.applymap(source_badge_style, subset=["Source historique"])
        st.dataframe(styled_src, use_container_width=True)
    except Exception:
        st.dataframe(src_df, use_container_width=True)

    # -------------------------
    # REALTIME
    # -------------------------
    rt_data: Dict[str, Tuple[float, pd.Timestamp]] = {}
    if use_realtime and POLYGON_API_KEY:
        rt_data = fetch_realtime_polygon_batch(list(prices.columns))

    if st.button("🔄 Refresh prix temps réel"):
        if use_realtime and POLYGON_API_KEY:
            rt_data = fetch_realtime_polygon_batch(list(prices.columns))

    # -------------------------
    # PRIX ACTUELS
    # -------------------------
    st.subheader("⚡ Prix actuels")
    cols = st.columns(min(4, len(prices.columns)))
    first_cols = list(prices.columns)[:len(cols)]

    for i, t in enumerate(first_cols):
        last_close = prices[t].dropna().iloc[-1]
        if t in rt_data:
            rt_price, _ = rt_data[t]
            delta_pct = (rt_price / last_close - 1.0) * 100 if last_close else None
            cols[i].metric(
                label=f"{t} (Realtime premium)",
                value=f"{rt_price:.2f}",
                delta=f"{delta_pct:.2f}% vs last close" if delta_pct is not None else None
            )
        else:
            cols[i].metric(label=f"{t} (Last close)", value=f"{last_close:.2f}")

    if len(prices.columns) > len(cols):
        with st.expander("Voir tous les prix actuels"):
            grid_cols = st.columns(4)
            for j, t in enumerate(list(prices.columns)):
                c = grid_cols[j % 4]
                last_close = prices[t].dropna().iloc[-1]
                if t in rt_data:
                    rt_price, _ = rt_data[t]
                    delta_pct = (rt_price / last_close - 1.0) * 100 if last_close else None
                    c.metric(
                        label=f"{t} (Realtime)",
                        value=f"{rt_price:.2f}",
                        delta=f"{delta_pct:.2f}% vs close" if delta_pct is not None else None
                    )
                else:
                    c.metric(label=f"{t} (Close)", value=f"{last_close:.2f}")

    # -------------------------
    # GRAPHIQUES
    # -------------------------
    st.subheader("📉 Graphiques")

    prices_display = prices.copy()
    if rt_data:
        for t, (p, _) in rt_data.items():
            if t in prices_display.columns and not prices_display[t].dropna().empty:
                prices_display.loc[prices_display.index[-1], t] = p

    graph_mode = st.radio(
        "Type de graphique",
        ["Comparaison (base 100)", "Prix réel (style plateforme)", "Spread entre 2 actions"],
        horizontal=True
    )

    if graph_mode == "Comparaison (base 100)":
        norm = prices_display / prices_display.iloc[0] * 100
        fig = px.line(norm, title=f"Performance normalisée (base 100) — {sector_label}")
        st.plotly_chart(fig, use_container_width=True)

    elif graph_mode == "Prix réel (style plateforme)":
        selected = st.selectbox(
            "Choisir une action",
            list(prices_display.columns),
            key="price_graph_select"
        )
        price_one = prices_display[[selected]].dropna()
        log_scale = st.checkbox("Échelle logarithmique", value=False)

        fig = px.line(price_one, title=f"{selected} — Prix réel sur la période ({history_period})")
        fig.update_yaxes(title="Prix", type="log" if log_scale else "linear")
        fig.update_xaxes(title="Date")
        st.plotly_chart(fig, use_container_width=True)

    else:
        # Spread entre 2 actions
        col_sp1, col_sp2 = st.columns(2)
        with col_sp1:
            t1 = st.selectbox("Action A (numérateur)", list(prices_display.columns), index=0)
        with col_sp2:
            t2 = st.selectbox(
                "Action B (dénominateur)",
                list(prices_display.columns),
                index=min(1, len(prices_display.columns) - 1)
            )

        if t1 == t2:
            st.info("Choisis deux actions différentes pour le spread.")
        else:
            sub = prices_display[[t1, t2]].dropna(how="any")
            if sub.empty:
                st.warning("Pas assez de données pour calculer le spread entre ces deux actions.")
            else:
                base = sub.iloc[0]
                norm_sp = sub / base * 100.0
                spread_series = norm_sp[t1] - norm_sp[t2]
                df_spread = pd.DataFrame({
                    f"{t1} (base 100)": norm_sp[t1],
                    f"{t2} (base 100)": norm_sp[t2],
                    "Spread (A - B)": spread_series,
                })
                fig_sp = px.line(df_spread[["Spread (A - B)"]], title=f"Spread base 100 = {t1} - {t2}")
                fig_sp.add_hline(y=0, line_dash="dash")
                st.plotly_chart(fig_sp, use_container_width=True)

                with st.expander("ℹ️ Comment lire le spread ?"):
                    st.markdown(
                        f"- Si la courbe **monte** → {t1} surperforme {t2} sur la période.\n"
                        f"- Si la courbe **descend** → {t1} sous-performe {t2}.\n"
                        "- Spread = différence entre leurs courbes en base 100."
                    )

    # -------------------------
    # PERFORMANCES / RISQUE / SCORES
    # -------------------------
    perf_1m = rolling_return(prices, 21)
    perf_3m = rolling_return(prices, 63)
    perf_6m = rolling_return(prices, 126)
    perf_1y = calendar_return_years(prices, years=1)

    vol = annualized_vol(prices)
    mdd = max_drawdown(prices)

    table = fund.copy()
    table["Perf 1M"] = perf_1m
    table["Perf 3M"] = perf_3m
    table["Perf 6M"] = perf_6m
    table["Perf 1Y"] = perf_1y
    table["Vol annualisée"] = vol
    table["Max Drawdown"] = mdd

    pe = safe_numeric(table, "P/E (trailing)")
    pb = safe_numeric(table, "P/B")
    roe = safe_numeric(table, "ROE")
    margin = safe_numeric(table, "Marge nette")
    de = safe_numeric(table, "Dette/Capitaux")

    mom6 = safe_numeric(table, "Perf 6M")
    mom1y = safe_numeric(table, "Perf 1Y")

    v = safe_numeric(table, "Vol annualisée")
    dd = safe_numeric(table, "Max Drawdown")

    value_score = (-zscore(pe).fillna(0) + -zscore(pb).fillna(0)) / 2
    quality_score = (zscore(roe).fillna(0) + zscore(margin).fillna(0) + -zscore(de).fillna(0)) / 3
    momentum_score = (zscore(mom6).fillna(0) + zscore(mom1y).fillna(0)) / 2
    risk_score = (-zscore(v).fillna(0) + zscore(dd).fillna(0)) / 2

    table["Score Value"] = value_score
    table["Score Quality"] = quality_score
    table["Score Momentum"] = momentum_score
    table["Score Risk"] = risk_score
    table["Score Global"] = (
        0.28 * table["Score Value"] +
        0.30 * table["Score Quality"] +
        0.27 * table["Score Momentum"] +
        0.15 * table["Score Risk"]
    )

    ranked = table.sort_values("Score Global", ascending=False)

    # -------------------------
    # TOP 3
    # -------------------------
    st.subheader("🏁 Top du classement (Score Global)")
    cols_top = st.columns(3)
    for i in range(min(3, len(ranked))):
        t = ranked.index[i]
        name = ranked.loc[t, "Nom"] if "Nom" in ranked.columns else ""
        score = ranked.loc[t, "Score Global"]
        p1y = ranked.loc[t, "Perf 1Y"]
        with cols_top[i]:
            st.metric(
                label=f"{t} {('- ' + name) if name else ''}",
                value=f"{score:.2f}" if pd.notna(score) else "n/a",
                delta=f"{p1y*100:.1f}% sur 1Y" if pd.notna(p1y) else None
            )

    # -------------------------
    # GRAND TABLEAU + BADGE SOURCE + COULEUR LIGNE
    # -------------------------
    display_cols = [
        "Nom", "Secteur (API)", "Industrie (API)", "Pays", "Devise",
        "Market Cap",
        "P/E (trailing)", "P/B",
        "ROE", "Marge nette", "Dette/Capitaux", "Div. Yield",
        "Perf 1M", "Perf 3M", "Perf 6M", "Perf 1Y",
        "Vol annualisée", "Max Drawdown",
        "Score Value", "Score Quality", "Score Momentum", "Score Risk", "Score Global"
    ]
    display_df = ranked.reindex(columns=display_cols)

    display_df.insert(
        0,
        "Source historique",
        [pretty_source_name(source_map.get(t, "none")) for t in display_df.index]
    )

    st.subheader("📌 Comparaison complète")
    try:
        styled = (
            display_df
            .style
            .applymap(source_badge_style, subset=["Source historique"])
            .apply(row_color_by_score, axis=1)
        )
        st.dataframe(styled, use_container_width=True)
    except Exception:
        st.dataframe(display_df, use_container_width=True)

    # -------------------------
    # HEATMAP (version lisible)
    # -------------------------
    st.subheader("🔥 Heatmap performances")

    heat = display_df[["Perf 1M", "Perf 3M", "Perf 6M", "Perf 1Y"]].copy()
    heat = heat.apply(pd.to_numeric, errors="coerce")
    heat.index.name = "Ticker"

    heat_pct = heat * 100.0
    heat_mat = heat_pct.copy()

    values = heat_mat.values
    text = np.empty(values.shape, dtype=object)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            v = values[i, j]
            if pd.isna(v):
                text[i, j] = ""
            else:
                text[i, j] = f"{v:+.1f}%"

    fig2 = px.imshow(
        heat_mat,
        x=heat_mat.columns,
        y=heat_mat.index,
        color_continuous_scale="RdYlGn",
        aspect="auto",
        labels={"x": "Horizon", "y": "Ticker", "color": "Performance (%)"},
        title="Performances par horizon (en %)"
    )

    fig2.update_traces(
        text=text,
        texttemplate="%{text}",
        textfont_size=10
    )

    fig2.update_coloraxes(colorbar_title="%")

    st.plotly_chart(fig2, use_container_width=True)

    # -------------------------
    # EXPORT CSV
    # -------------------------
    csv = display_df.to_csv().encode("utf-8")
    st.download_button(
        "⬇️ Télécharger le tableau (CSV)",
        data=csv,
        file_name=f"comparateur_{sector_label.lower().replace(' ', '_')}.csv",
        mime="text/csv"
    )

    # -------------------------
    # ENCARt EXPLICATION FANTAZIA SCORE
    # -------------------------
    with st.expander("🧮 Détails du Fantazia Score"):
        lines_score = [
            "- **Score Value (28%)** :",
            "  > But : savoir si l’action est chère ou pas vs les autres (P/E, P/B).",
            "",
            "- **Score Quality (30%)** :",
            "  > But : mesurer la qualité de la boîte (ROE, marge nette, dette).",
            "",
            "- **Score Momentum (27%)** :",
            "  > But : voir la dynamique récente (Perf 6M + Perf 1Y).",
            "",
            "- **Score Risk (15%)** :",
            "  > But : regarder si le parcours a été violent ou propre (volatilité, drawdown).",
            "",
            "Les scores sont **relatifs au panier** d’actions affiché (comparaison intra-secteur).",
        ]
        st.markdown("\n".join(lines_score))

    note_lines = [
        "### Notes techniques",
        f"- Source historique choisie : **{price_source_mode}**",
        "- ✅ Fallback par action actif.",
        "- Realtime Polygon : **activé**" if use_realtime else "- Realtime Polygon : **désactivé**",
        "- Perf 1M/3M/6M : approximation en séances.",
        "- ✅ Perf 1Y : calculée en calendrier (1 an réel).",
        f"- Période d'historique actuelle : **{history_period}**.",
    ]
    with st.expander("ℹ️ Notes techniques"):
        st.markdown("\n".join(note_lines))


# =========================================================
# TAB 2 — WATCHLISTS (PAR UTILISATEUR)
# =========================================================
with tab2:
    st.subheader("⭐ Gérer tes watchlists (locales, liées à ton compte)")
    st.caption(f"Enregistrées dans {WATCHLIST_FILE} sous la clé '{CURRENT_USER}'.")

    watchlists = load_watchlists(CURRENT_USER)
    colA, colB = st.columns([1, 2])

    with colA:
        st.markdown("### Créer / Remplacer")
        new_name = st.text_input("Nom de la watchlist", value="")
        new_tickers_txt = st.text_area("Tickers (séparés par virgules)", value="", height=80)

        if st.button("Enregistrer"):
            name = new_name.strip()
            if name:
                tick_list = parse_tickers(new_tickers_txt)
                watchlists[name] = tick_list
                save_watchlists(CURRENT_USER, watchlists)
                st.success(f"Watchlist '{name}' enregistrée ({len(tick_list)} tickers) pour {CURRENT_USER}.")
            else:
                st.warning("Donne un nom à la watchlist.")

    with colB:
        st.markdown("### Watchlists existantes")
        if not watchlists:
            st.info("Aucune watchlist pour l'instant sur ce compte.")
        else:
            rows = [{"Watchlist": n, "Tickers": ", ".join(v)} for n, v in watchlists.items()]
            df_wl = pd.DataFrame(rows)
            st.dataframe(df_wl, use_container_width=True)

            st.markdown("### Supprimer")
            del_name = st.selectbox("Choisis une watchlist à supprimer", list(watchlists.keys()))
            if st.button("Supprimer"):
                watchlists.pop(del_name, None)
                save_watchlists(CURRENT_USER, watchlists)
                st.success(f"Watchlist '{del_name}' supprimée pour {CURRENT_USER}.")

    st.divider()
    if watchlists:
        export_json = json.dumps(watchlists, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            "⬇️ Télécharger mes watchlists (JSON)",
            data=export_json,
            file_name=f"watchlists_{CURRENT_USER}.json",
            mime="application/json"
        )


# =========================================================
# TAB 3 — SIMULATEUR SIMPLE
# =========================================================
with tab3:
    st.subheader("💼 Simulateur simple de portefeuille")
    st.caption("Hypothèse : achat au début de l'historique chargé, valeur actuelle = dernier prix.")

    if prices.shape[0] < 2:
        st.warning("Pas assez d'historique pour simuler (au moins 2 dates nécessaires).")
    else:
        start_date = prices.index[0]
        end_date = prices.index[-1]
        st.markdown(f"- Début de l'historique : **{start_date.date()}**")
        st.markdown(f"- Fin de l'historique : **{end_date.date()}**")

        capital = st.number_input("Capital initial (€)", min_value=100.0, value=10000.0, step=500.0)

        mode_alloc = st.radio(
            "Mode d'allocation",
            ["Poids égaux", "Poids personnalisés (%)"],
            horizontal=True
        )

        tick_list = list(prices.columns)
        weights = {}

        if mode_alloc == "Poids égaux":
            n = len(tick_list)
            for t in tick_list:
                weights[t] = 1.0 / n
        else:
            st.markdown("Indique un poids pour chaque action (en %, on normalisera automatiquement).")
            total_input = 0.0
            raw_vals = {}
            for t in tick_list:
                val = st.number_input(f"Poids {t} (%)", min_value=0.0, value=100.0 / len(tick_list), step=5.0)
                raw_vals[t] = val
                total_input += val

            if total_input <= 0:
                st.warning("Somme des poids <= 0 : on repasse en poids égaux.")
                n = len(tick_list)
                for t in tick_list:
                    weights[t] = 1.0 / n
            else:
                for t in tick_list:
                    weights[t] = raw_vals[t] / total_input

        start_prices = prices.iloc[0]
        last_prices = prices.iloc[-1]

        sim_rows = []
        total_value = 0.0

        for t in tick_list:
            p0 = start_prices.get(t, np.nan)
            p1 = last_prices.get(t, np.nan)
            w = weights.get(t, 0.0)

            if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
                shares = 0.0
                val_now = 0.0
                perf = np.nan
            else:
                invest = capital * w
                shares = invest / p0
                val_now = shares * p1
                perf = (p1 / p0 - 1.0)

            total_value += val_now
            sim_rows.append({
                "Ticker": t,
                "Poids (%)": w * 100.0,
                "Prix entrée": p0,
                "Prix actuel": p1,
                "Nombre d'actions": shares,
                "Valeur actuelle (€)": val_now,
                "Perf depuis entrée (%)": perf * 100.0 if not pd.isna(perf) else np.nan,
            })

        sim_df = pd.DataFrame(sim_rows).set_index("Ticker")
        pl_abs = total_value - capital
        pl_pct = (total_value / capital - 1.0) * 100.0

        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("Capital initial", f"{capital:,.2f} €")
        with col_s2:
            st.metric("Valeur actuelle", f"{total_value:,.2f} €", delta=f"{pl_abs:,.2f} €")
        with col_s3:
            st.metric("Performance globale", f"{pl_pct:+.2f} %")

        st.markdown("### Détail par ligne")
        st.dataframe(sim_df, use_container_width=True)


# =========================================================
# TAB 4 — FICHE ACTION
# =========================================================
with tab4:
    st.subheader("📄 Fiche détaillée par action")

    t_selected = st.selectbox(
        "Choisir une action",
        list(prices.columns),
        key="detail_select"
    )

    info_row = fund.loc[t_selected] if t_selected in fund.index else None
    last_price = prices[t_selected].dropna().iloc[-1]
    start_price = prices[t_selected].dropna().iloc[0]
    perf_total = (last_price / start_price - 1.0) * 100.0 if start_price > 0 else np.nan

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    if info_row is not None:
        with col_f1:
            st.metric("Nom", info_row.get("Nom", ""))
            st.write(f"Secteur : {info_row.get('Secteur (API)', '')}")
            st.write(f"Industrie : {info_row.get('Industrie (API)', '')}")
        with col_f2:
            st.metric("Pays / Devise", f"{info_row.get('Pays', '')} / {info_row.get('Devise', '')}")
            st.write(f"Exchange : {info_row.get('Exchange', '')}")
        with col_f3:
            st.metric("Prix actuel", f"{last_price:.2f}")
            if not pd.isna(perf_total):
                st.metric("Perf sur la période", f"{perf_total:+.2f}%")
        with col_f4:
            st.write(f"Market Cap : {info_row.get('Market Cap', 'n/a')}")
            st.write(f"P/E (trailing) : {info_row.get('P/E (trailing)', 'n/a')}")
            st.write(f"P/B : {info_row.get('P/B', 'n/a')}")
            st.write(f"ROE : {info_row.get('ROE', 'n/a')}")
            st.write(f"Marge nette : {info_row.get('Marge nette', 'n/a')}")
            st.write(f"Dette/Capitaux : {info_row.get('Dette/Capitaux', 'n/a')}")
            st.write(f"Div. Yield : {info_row.get('Div. Yield', 'n/a')}")

    st.markdown("---")

    col_g1, col_g2 = st.columns(2)

    # Graphique prix simple
    with col_g1:
        st.markdown("#### Prix historique")
        s_price = prices[t_selected].dropna()
        figp = px.line(s_price, title=f"{t_selected} — Prix sur la période ({history_period})")
        figp.update_yaxes(title="Prix")
        figp.update_xaxes(title="Date")
        st.plotly_chart(figp, use_container_width=True)

    # Graphique P/E approximatif dans le temps
    with col_g2:
        st.markdown("#### P/E approximatif dans le temps")
        eps = info_row.get("EPS (trailing)") if info_row is not None else None
        if eps is None or pd.isna(eps) or eps == 0:
            st.info("EPS (trailing) indisponible → impossible de tracer un P/E approximatif.")
        else:
            s_price2 = prices[t_selected].dropna()
            pe_series = s_price2 / eps
            pe_series.name = "P/E approx"
            figpe = px.line(pe_series, title=f"{t_selected} — P/E recalculé avec EPS actuel (approximation)")
            figpe.update_yaxes(title="P/E approx")
            figpe.update_xaxes(title="Date")
            st.plotly_chart(figpe, use_container_width=True)
            st.caption(
                "Approximation : P/E(t) = Prix(t) / EPS_actuel. "
                "Ce n'est pas un vrai historique de P/E, mais une vision de la valorisation "
                "si l'EPS restait constant."
            )

    st.markdown("### Données brutes (fondamentaux)")
    if info_row is not None:
        st.dataframe(info_row.to_frame(name="Valeur"), use_container_width=True)


# =========================================================
# TAB 5 — AIDE
# =========================================================
with tab5:
    st.subheader("ℹ️ Aide rapide — V3 (comptes)")

    help_lines = [
        "### Comptes utilisateurs",
        "- Chaque pseudo possède ses **propres watchlists**.",
        f"- Les watchlists sont stockées dans `{WATCHLIST_FILE}` sous la clé du pseudo.",
        "- Les mots de passe sont **hashés** (SHA-256 + sel aléatoire) dans `users.json`.",
        "",
        "### Apparence",
        "- Thème clair de base Streamlit.",
        "- Logo Fantazia en watermark discret en bas à droite.",
        "- Logo Fantazia en haut de la barre de gauche.",
        "- Boutons jaunes Fantazia.",
        "",
        "### Moteurs de données",
        "- Historique : Yahoo Finance (yfinance), Twelve Data, Finnhub.",
        "- Fallback par action : chaque ticker choisit la première source dispo.",
        "- Temps réel optionnel via Polygon (si POLYGON_API_KEY présente).",
        "",
        "### Fantazia Score",
        "- Combine Value, Quality, Momentum, Risk.",
        "- Score **relatif au panier** d'actions affiché.",
        "",
        "### Périodes d'historique",
        "- 1d, 5d, 1mo, 3mo, 1y, 3y, 5y.",
        "- Certaines métriques (Perf 1Y, etc.) n'ont de sens que sur des périodes longues.",
        "",
        "### config.json (dans C:\\bourse-dashboard)",
        "```json",
        "{",
        '  \"TWELVE_API_KEY\": \"TA_CLE_TWELVE\",',
        '  \"FINNHUB_API_KEY\": \"TA_CLE_FINNHUB\",',
        '  \"POLYGON_API_KEY\": \"TA_CLE_POLYGON\"',
        "}",
        "```",
        "",
        "### Auto-refresh",
        "- Optionnel : pip install streamlit-autorefresh",
    ]

    st.markdown("\n".join(help_lines))

    st.divider()
    st.markdown("### Statut des clés API")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write("Twelve Data :", "✅ détectée" if TWELVE_API_KEY else "⚠️ absente")
    with c2:
        st.write("Finnhub :", "✅ détectée" if FINNHUB_API_KEY else "⚠️ absente")
    with c3:
        st.write("Polygon :", "✅ détectée" if POLYGON_API_KEY else "⚠️ absente")

    st.divider()
    st.write("Auto-refresh lib :", "✅ disponible" if HAS_AUTOREFRESH else "⚠️ non installée")
