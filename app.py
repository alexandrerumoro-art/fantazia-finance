import os
import json
import base64
import hashlib
import secrets
import html
from io import BytesIO
from typing import List, Dict, Optional, Tuple, Callable

import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

from sqlalchemy import create_engine, text


# =========================================================
# SECRETS / DB
# =========================================================
DB_URL = st.secrets.get("DB_URL", "").strip()

@st.cache_resource
def get_engine():
    if not DB_URL:
        return None

    url = DB_URL
    # Force psycopg v3
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    elif url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]

    return create_engine(url, pool_pre_ping=True)

engine = get_engine()


def db_init_schema():
    """
    Crée les tables si elles n'existent pas.
    IMPORTANT : ça évite les ProgrammingError quand tu fais SELECT sur une table inexistante.
    """
    if engine is None:
        return

    ddl = """
    CREATE TABLE IF NOT EXISTS app_users (
        id BIGSERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS watchlists (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        UNIQUE(user_id, name)
    );

    CREATE TABLE IF NOT EXISTS watchlist_items (
        id BIGSERIAL PRIMARY KEY,
        watchlist_id BIGINT NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
        ticker TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
        ticker TEXT NOT NULL,
        kind TEXT NOT NULL,
        cmp TEXT NOT NULL,
        threshold DOUBLE PRECISION NOT NULL,
        UNIQUE(user_id, ticker, kind, cmp)
    );

    CREATE TABLE IF NOT EXISTS notes (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
        ticker TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        UNIQUE(user_id, ticker)
    );

    CREATE TABLE IF NOT EXISTS news_subscriptions (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
        ticker TEXT NOT NULL,
        UNIQUE(user_id, ticker)
    );
    """

    try:
        with engine.begin() as conn:
            conn.execute(text(ddl))
    except Exception:
        # Streamlit cloud redacts details anyway; on ne casse pas l'app si ça échoue
        pass


# Initialise DB tables au démarrage
db_init_schema()


# =========================================================
# JSON FILES (fallback)
# =========================================================
USERS_FILE = "users.json"
WATCHLIST_FILE = "watchlists.json"
ALERTS_FILE = "alerts.json"
NOTES_FILE = "notes.json"
NEWS_SUB_FILE = "news_subscriptions.json"

USERS_JSON_B64 = st.secrets.get("USERS_JSON_B64", "")
WATCHLISTS_JSON_B64 = st.secrets.get("WATCHLISTS_JSON_B64", "")
ALERTS_JSON_B64 = st.secrets.get("ALERTS_JSON_B64", "")
NOTES_JSON_B64 = st.secrets.get("NOTES_JSON_B64", "")
NEWS_SUBSCRIPTIONS_JSON_B64 = st.secrets.get("NEWS_SUBSCRIPTIONS_JSON_B64", "")


def seed_file_from_b64(path: str, b64_value: str, default_json_obj):
    if os.path.exists(path):
        return

    if isinstance(b64_value, str) and b64_value.strip():
        try:
            raw = base64.b64decode(b64_value.encode("utf-8"))
            with open(path, "wb") as f:
                f.write(raw)
            return
        except Exception:
            pass

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_json_obj, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


seed_file_from_b64(USERS_FILE, USERS_JSON_B64, {})
seed_file_from_b64(WATCHLIST_FILE, WATCHLISTS_JSON_B64, {})
seed_file_from_b64(ALERTS_FILE, ALERTS_JSON_B64, {})
seed_file_from_b64(NOTES_FILE, NOTES_JSON_B64, {})
seed_file_from_b64(NEWS_SUB_FILE, NEWS_SUBSCRIPTIONS_JSON_B64, {})


def _json_read(path: str, default):
    if not os.path
# =========================================================
# PARTIE 2/2 — UI + FEATURES (watchlists/alerts/notes/news)
# =========================================================

# --- Complète les traductions utilisées dans la partie 2
TRANSLATIONS["fr"].update({
    "sidebar_user": "Connecté en tant que",
    "sidebar_logout": "Se déconnecter",
    "sidebar_lang": "Langue",
    "sidebar_nav": "Navigation",
    "nav_dashboard": "🏠 Dashboard",
    "nav_watchlists": "⭐ Watchlists",
    "nav_alerts": "🚨 Alertes",
    "nav_notes": "📝 Notes",
    "nav_news": "📰 News",
    "theme_title": "Apparence",
    "theme_compact": "Mode compact",
    "tickers": "Tickers",
    "save": "Sauvegarder",
    "saved_ok": "Sauvegardé ✅",
    "watchlists_title": "⭐ Watchlists",
    "wl_select": "Choisir une watchlist",
    "wl_new_name": "Nom de la nouvelle watchlist",
    "wl_create": "Créer",
    "wl_delete": "Supprimer cette watchlist",
    "wl_add_tickers": "Ajouter des tickers (séparés par des virgules)",
    "wl_apply_add": "Ajouter",
    "wl_current": "Tickers dans la watchlist",
    "wl_empty": "Aucune watchlist. Crée-en une.",
    "dash_title": "🏠 Dashboard",
    "dash_pick_wl": "Watchlist à afficher",
    "dash_refresh": "Rafraîchir",
    "alerts_title": "🚨 Alertes",
    "alerts_add": "Ajouter une alerte",
    "alerts_table": "Tes alertes",
    "alerts_none": "Aucune alerte pour le moment.",
    "alerts_ticker": "Ticker",
    "alerts_kind": "Type",
    "alerts_cmp": "Condition",
    "alerts_thr": "Seuil",
    "alerts_btn_add": "Ajouter l’alerte",
    "alerts_btn_save": "Sauvegarder toutes les alertes",
    "alerts_ribbon_info": "💡 Les alertes sont évaluées avec le dernier prix (yfinance).",
    "notes_title": "📝 Notes",
    "notes_pick": "Ticker",
    "notes_edit": "Ta note",
    "notes_save": "Sauvegarder la note",
    "news_title": "📰 News",
    "news_subs": "Tickers suivis",
    "news_add_ticker": "Ajouter un ticker aux news",
    "news_add_btn": "Ajouter",
    "news_remove": "Retirer",
    "news_fetch": "Afficher les news",
    "news_none": "Aucune news trouvée (ou API silencieuse).",
    "err_ticker_missing": "Ticker manquant.",
    "err_name_missing": "Nom manquant.",
})

TRANSLATIONS["en"].update({
    "sidebar_user": "Logged in as",
    "sidebar_logout": "Log out",
    "sidebar_lang": "Language",
    "sidebar_nav": "Navigation",
    "nav_dashboard": "🏠 Dashboard",
    "nav_watchlists": "⭐ Watchlists",
    "nav_alerts": "🚨 Alerts",
    "nav_notes": "📝 Notes",
    "nav_news": "📰 News",
    "theme_title": "Appearance",
    "theme_compact": "Compact mode",
    "tickers": "Tickers",
    "save": "Save",
    "saved_ok": "Saved ✅",
    "watchlists_title": "⭐ Watchlists",
    "wl_select": "Select a watchlist",
    "wl_new_name": "New watchlist name",
    "wl_create": "Create",
    "wl_delete": "Delete this watchlist",
    "wl_add_tickers": "Add tickers (comma-separated)",
    "wl_apply_add": "Add",
    "wl_current": "Tickers in watchlist",
    "wl_empty": "No watchlist yet. Create one.",
    "dash_title": "🏠 Dashboard",
    "dash_pick_wl": "Watchlist to display",
    "dash_refresh": "Refresh",
    "alerts_title": "🚨 Alerts",
    "alerts_add": "Add an alert",
    "alerts_table": "Your alerts",
    "alerts_none": "No alerts yet.",
    "alerts_ticker": "Ticker",
    "alerts_kind": "Type",
    "alerts_cmp": "Condition",
    "alerts_thr": "Threshold",
    "alerts_btn_add": "Add alert",
    "alerts_btn_save": "Save all alerts",
    "alerts_ribbon_info": "💡 Alerts are evaluated using latest price (yfinance).",
    "notes_title": "📝 Notes",
    "notes_pick": "Ticker",
    "notes_edit": "Your note",
    "notes_save": "Save note",
    "news_title": "📰 News",
    "news_subs": "Tracked tickers",
    "news_add_ticker": "Add ticker to news",
    "news_add_btn": "Add",
    "news_remove": "Remove",
    "news_fetch": "Show news",
    "news_none": "No news found (or API returned nothing).",
    "err_ticker_missing": "Missing ticker.",
    "err_name_missing": "Missing name.",
})


# =========================================================
# THEME / CSS
# =========================================================
def apply_css(compact: bool = False):
    pad = "0.35rem" if compact else "0.75rem"
    st.markdown(
        f"""
        <style>
          .block-container {{ padding-top: {pad}; padding-bottom: {pad}; }}
          [data-testid="stSidebar"] .block-container {{ padding-top: {pad}; }}
          div[data-testid="stMetricValue"] {{ font-size: 1.25rem; }}
          .ff-card {{
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            padding: 12px 14px;
            background: rgba(255,255,255,0.02);
          }}
          .ff-muted {{ opacity: 0.75; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


if "compact" not in st.session_state:
    st.session_state["compact"] = False

apply_css(st.session_state["compact"])


# =========================================================
# USER STATE INIT
# =========================================================
def init_user_state(user: str):
    if "watchlists" not in st.session_state:
        st.session_state["watchlists"] = load_watchlists(user)
    if "alerts" not in st.session_state:
        st.session_state["alerts"] = load_alerts(user)
    if "notes" not in st.session_state:
        st.session_state["notes"] = load_notes(user)
    if "news_subs" not in st.session_state:
        st.session_state["news_subs"] = load_news_subscriptions(user)

    # default watchlist si vide
    if not st.session_state["watchlists"]:
        st.session_state["watchlists"] = {"Main": ["AAPL", "MSFT", "NVDA"]}
        save_watchlists(user, st.session_state["watchlists"])

init_user_state(CURRENT_USER)


# =========================================================
# MARKET DATA (yfinance)
# =========================================================
@st.cache_data(ttl=60)
def get_last_price(ticker: str) -> Optional[float]:
    try:
        t = yf.Ticker(ticker)
        # fast_info souvent ok
        fi = getattr(t, "fast_info", None)
        if fi and isinstance(fi, dict):
            p = fi.get("lastPrice") or fi.get("last_price")
            if p is not None:
                return float(p)
        # fallback
        hist = t.history(period="1d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        return None
    return None


@st.cache_data(ttl=300)
def get_history(ticker: str, period: str = "6mo") -> Optional[pd.DataFrame]:
    try:
        df = yf.Ticker(ticker).history(period=period)
        if df is None or df.empty:
            return None
        df = df.reset_index()
        return df
    except Exception:
        return None


@st.cache_data(ttl=300)
def get_news_yf(ticker: str) -> List[Dict]:
    try:
        t = yf.Ticker(ticker)
        news = getattr(t, "news", None)
        if not news:
            return []
        out = []
        for n in news[:20]:
            # yfinance: title/link/publisher/providerPublishTime
            out.append({
                "title": str(n.get("title", "")),
                "link": str(n.get("link", "")),
                "publisher": str(n.get("publisher", "")),
                "time": n.get("providerPublishTime", None),
            })
        return out
    except Exception:
        return []


# =========================================================
# ALERT EVAL
# =========================================================
def alert_triggered(last_price: Optional[float], cmp_: str, thr: float) -> bool:
    if last_price is None:
        return False
    try:
        if cmp_ in (">", "gt"):
            return last_price > thr
        if cmp_ in (">=", "gte"):
            return last_price >= thr
        if cmp_ in ("<", "lt"):
            return last_price < thr
        if cmp_ in ("<=", "lte"):
            return last_price <= thr
        if cmp_ in ("==", "eq"):
            return abs(last_price - thr) < 1e-9
    except Exception:
        return False
    return False


def run_alerts_ribbon(alerts: List[Dict]):
    triggered = []
    for a in alerts or []:
        t = str(a.get("ticker", "")).upper().strip()
        cmp_ = str(a.get("cmp", "")).strip()
        thr = float(a.get("threshold", 0.0))
        lp = get_last_price(t)
        if alert_triggered(lp, cmp_, thr):
            triggered.append((t, cmp_, thr, lp))

    if triggered:
        st.sidebar.markdown("### 🚨 Alertes déclenchées")
        for t, cmp_, thr, lp in triggered[:10]:
            st.sidebar.warning(f"{t}: {lp:.4g} {cmp_} {thr:.4g}")


# =========================================================
# SIDEBAR NAV
# =========================================================
st.sidebar.markdown(f"**{tr('sidebar_user')}**: `{CURRENT_USER}`")

lang_choice = st.sidebar.selectbox(
    tr("sidebar_lang"),
    ["fr", "en"],
    index=0 if st.session_state["lang"] == "fr" else 1,
)
st.session_state["lang"] = lang_choice

st.session_state["compact"] = st.sidebar.checkbox(tr("theme_compact"), value=st.session_state["compact"])
apply_css(st.session_state["compact"])

st.sidebar.divider()

page = st.sidebar.radio(
    tr("sidebar_nav"),
    [tr("nav_dashboard"), tr("nav_watchlists"), tr("nav_alerts"), tr("nav_notes"), tr("nav_news")],
)

# Ribbon alertes
run_alerts_ribbon(st.session_state.get("alerts", []))

st.sidebar.divider()
if st.sidebar.button(tr("sidebar_logout")):
    st.session_state.pop("user", None)
    # optionnel: vider caches user
    for k in ["watchlists", "alerts", "notes", "news_subs"]:
        st.session_state.pop(k, None)
    rerun_app()


# =========================================================
# PAGE: DASHBOARD
# =========================================================
def page_dashboard():
    st.title(tr("dash_title"))

    wls = st.session_state.get("watchlists", {})
    wl_names = list(wls.keys())
    if not wl_names:
        st.info(tr("wl_empty"))
        return

    colA, colB = st.columns([2, 1])
    with colA:
        chosen = st.selectbox(tr("dash_pick_wl"), wl_names, index=0)
    with colB:
        if st.button(tr("dash_refresh")):
            st.cache_data.clear()
            rerun_app()

    tickers = wls.get(chosen, []) or []
    if not tickers:
        st.info(tr("wl_current") + ": (vide)")
        return

    # Table prices
    rows = []
    for t in tickers[:60]:
        lp = get_last_price(t)
        rows.append({"Ticker": t, "Last": lp})
    df = pd.DataFrame(rows)

    st.markdown("#### " + tr("tickers"))
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Mini chart sur un ticker
    st.markdown("#### Chart")
    pick = st.selectbox("Ticker", tickers, index=0)
    hist = get_history(pick, "6mo")
    if hist is None:
        st.info("Pas de data.")
    else:
        fig = px.line(hist, x="Date", y="Close", title=f"{pick} — 6mo")
        st.plotly_chart(fig, use_container_width=True)


# =========================================================
# PAGE: WATCHLISTS
# =========================================================
def page_watchlists():
    st.title(tr("watchlists_title"))

    wls = st.session_state.get("watchlists", {})
    wl_names = list(wls.keys())

    if not wl_names:
        st.info(tr("wl_empty"))

    col1, col2 = st.columns([2, 1])

    with col1:
        selected = st.selectbox(tr("wl_select"), wl_names if wl_names else ["Main"], index=0)

    with col2:
        new_name = st.text_input(tr("wl_new_name"))
        if st.button(tr("wl_create")):
            name = (new_name or "").strip()
            if not name:
                st.error(tr("err_name_missing"))
            else:
                if name not in wls:
                    wls[name] = []
                    st.session_state["watchlists"] = wls
                    save_watchlists(CURRENT_USER, wls)
                    st.success(tr("saved_ok"))
                    rerun_app()

    st.divider()

    if selected not in wls:
        wls[selected] = []
        st.session_state["watchlists"] = wls

    add_txt = st.text_input(tr("wl_add_tickers"))
    if st.button(tr("wl_apply_add")):
        to_add = parse_tickers(add_txt or "")
        cur = set(wls.get(selected, []) or [])
        for t in to_add:
            cur.add(t)
        wls[selected] = sorted(list(cur))
        st.session_state["watchlists"] = wls
        save_watchlists(CURRENT_USER, wls)
        st.success(tr("saved_ok"))
        rerun_app()

    st.markdown("#### " + tr("wl_current"))

    tickers = wls.get(selected, []) or []
    if not tickers:
        st.info("Vide.")
    else:
        # édition simple: multiselect = la vérité
        chosen_set = st.multiselect("",
                                   options=tickers,
                                   default=tickers)
        # Permet de retirer en décochant
        if st.button(tr("save")):
            wls[selected] = sorted(list({t.upper().strip() for t in chosen_set if t.strip()}))
            st.session_state["watchlists"] = wls
            save_watchlists(CURRENT_USER, wls)
            st.success(tr("saved_ok"))
            rerun_app()

    st.divider()
    if st.button(tr("wl_delete")):
        if selected in wls and len(wls) > 1:
            wls.pop(selected, None)
            st.session_state["watchlists"] = wls
            save_watchlists(CURRENT_USER, wls)
            st.success(tr("saved_ok"))
            rerun_app()
        else:
            st.warning("Garde au moins une watchlist.")


# =========================================================
# PAGE: ALERTS
# =========================================================
def page_alerts():
    st.title(tr("alerts_title"))
    st.caption(tr("alerts_ribbon_info"))

    alerts = st.session_state.get("alerts", []) or []

    st.markdown("### " + tr("alerts_add"))
    c1, c2, c3, c4 = st.columns([1.2, 1.0, 1.0, 1.0])
    with c1:
        t = st.text_input(tr("alerts_ticker")).upper().strip()
    with c2:
        kind = st.selectbox(tr("alerts_kind"), ["price"], index=0)
    with c3:
        cmp_ = st.selectbox(tr("alerts_cmp"), [">", ">=", "<", "<=", "=="], index=0)
    with c4:
        thr = st.number_input(tr("alerts_thr"), value=0.0, step=0.5)

    if st.button(tr("alerts_btn_add")):
        if not t:
            st.error(tr("err_ticker_missing"))
        else:
            alerts.append({"ticker": t, "kind": kind, "cmp": cmp_, "threshold": float(thr)})
            st.session_state["alerts"] = alerts
            save_alerts(CURRENT_USER, alerts)
            st.success(tr("saved_ok"))
            rerun_app()

    st.divider()

    st.markdown("### " + tr("alerts_table"))
    if not alerts:
        st.info(tr("alerts_none"))
        return

    # tableau éditable via dataframe
    df = pd.DataFrame(alerts)
    df = df[["ticker", "kind", "cmp", "threshold"]].copy()
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    if st.button(tr("alerts_btn_save")):
        clean = []
        for _, r in edited.iterrows():
            ticker = str(r.get("ticker", "")).upper().strip()
            if not ticker:
                continue
            clean.append({
                "ticker": ticker,
                "kind": str(r.get("kind", "price")).strip() or "price",
                "cmp": str(r.get("cmp", ">")).strip() or ">",
                "threshold": float(r.get("threshold", 0.0) or 0.0),
            })
        st.session_state["alerts"] = clean
        save_alerts(CURRENT_USER, clean)
        st.success(tr("saved_ok"))
        rerun_app()


# =========================================================
# PAGE: NOTES
# =========================================================
def page_notes():
    st.title(tr("notes_title"))

    notes = st.session_state.get("notes", {}) or {}
    wls = st.session_state.get("watchlists", {}) or {}

    # suggestions tickers depuis watchlists
    all_tickers = []
    for _, arr in wls.items():
        all_tickers.extend(arr or [])
    all_tickers = sorted(list({t.upper().strip() for t in all_tickers if t.strip()}))

    col1, col2 = st.columns([1, 2])
    with col1:
        ticker = st.selectbox(tr("notes_pick"), all_tickers if all_tickers else ["AAPL"], index=0)
        ticker = (ticker or "").upper().strip()

    with col2:
        existing = notes.get(ticker, "")
        txt = st.text_area(tr("notes_edit"), value=existing, height=180)

    if st.button(tr("notes_save")):
        if not ticker:
            st.error(tr("err_ticker_missing"))
            return
        notes[ticker] = txt
        st.session_state["notes"] = notes
        save_notes(CURRENT_USER, notes)
        st.success(tr("saved_ok"))
        rerun_app()


# =========================================================
# PAGE: NEWS
# =========================================================
def page_news():
    st.title(tr("news_title"))

    subs = st.session_state.get("news_subs", []) or []

    st.markdown("### " + tr("news_subs"))
    if subs:
        st.write(", ".join(subs))
    else:
        st.info("Aucun ticker suivi.")

    col1, col2 = st.columns([1.4, 1])
    with col1:
        t = st.text_input(tr("news_add_ticker")).upper().strip()
    with col2:
        if st.button(tr("news_add_btn")):
            if not t:
                st.error(tr("err_ticker_missing"))
            else:
                subs = sorted(list(set(subs + [t])))
                st.session_state["news_subs"] = subs
                save_news_subscriptions(CURRENT_USER, subs)
                st.success(tr("saved_ok"))
                rerun_app()

    if subs:
        to_remove = st.selectbox(tr("news_remove"), [""] + subs, index=0)
        if st.button(tr("news_remove")):
            if to_remove:
                subs = [x for x in subs if x != to_remove]
                st.session_state["news_subs"] = subs
                save_news_subscriptions(CURRENT_USER, subs)
                st.success(tr("saved_ok"))
                rerun_app()

    st.divider()

    if st.button(tr("news_fetch")):
        if not subs:
            st.info("Ajoute d’abord un ticker.")
            return

        # Affiche les news pour le 1er ticker (simple et propre)
        pick = st.selectbox("Ticker", subs, index=0, key="news_pick_show")
        news = get_news_yf(pick)
        if not news:
            st.info(tr("news_none"))
            return

        for n in news[:15]:
            title = n.get("title", "").strip()
            link = n.get("link", "").strip()
            pub = n.get("publisher", "").strip()
            if link:
                st.markdown(f"- **{html.escape(title)}**  \n  <span class='ff-muted'>{html.escape(pub)}</span>  \n  {link}", unsafe_allow_html=True)
            else:
                st.markdown(f"- **{html.escape(title)}**  \n  <span class='ff-muted'>{html.escape(pub)}</span>", unsafe_allow_html=True)


# =========================================================
# ROUTER
# =========================================================
if page == tr("nav_dashboard"):
    page_dashboard()
elif page == tr("nav_watchlists"):
    page_watchlists()
elif page == tr("nav_alerts"):
    page_alerts()
elif page == tr("nav_notes"):
    page_notes()
elif page == tr("nav_news"):
    page_news()
else:
    page_dashboard()
