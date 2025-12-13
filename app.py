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
import streamlit as st
from sqlalchemy import create_engine, text

DB_URL = st.secrets.get("DB_URL", "").strip()

@st.cache_resource
def get_engine():
    if not DB_URL:
        return None

    url = DB_URL

    # Si ton URL commence par postgresql://, SQLAlchemy va souvent chercher psycopg2 par défaut.
    # On force psycopg (v3) :
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    elif url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]

    return create_engine(url, pool_pre_ping=True)

engine = get_engine()
def db_init_schema():
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_users (
                id BIGSERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS watchlists (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                UNIQUE(user_id, name)
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS watchlist_items (
                id BIGSERIAL PRIMARY KEY,
                watchlist_id BIGINT NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
                ticker TEXT NOT NULL
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alerts (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                ticker TEXT NOT NULL,
                kind TEXT NOT NULL,
                cmp TEXT NOT NULL,
                threshold DOUBLE PRECISION NOT NULL
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS notes (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                ticker TEXT NOT NULL,
                note TEXT NOT NULL,
                UNIQUE(user_id, ticker)
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS news_subscriptions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                ticker TEXT NOT NULL,
                UNIQUE(user_id, ticker)
            );
        """))

# Appel safe (ne doit JAMAIS casser l'app)
try:
    db_init_schema()
except Exception:
    pass

def db_init_schema():
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS app_users (
            id BIGSERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS watchlists (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
            name TEXT NOT NULL
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
            threshold DOUBLE PRECISION NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notes (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
            ticker TEXT NOT NULL,
            note TEXT NOT NULL,
            UNIQUE(user_id, ticker)
        );

        CREATE TABLE IF NOT EXISTS news_subscriptions (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
            ticker TEXT NOT NULL
        );
        """))

# appelle l’init une seule fois au démarrage
db_init_schema()

from sqlalchemy import text

def db_get_user_id(username: str):
    username = (username or "").strip().lower()
    if not username or engine is None:
        return None
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT id FROM app_users WHERE username = :u"),
                {"u": username},
            ).scalar()
    except Exception:
        # Si la table n'existe pas / souci DB => on désactive juste le DB pour cet appel
        return None


# -------- USERS (login/signup) --------
def db_get_user_record(username: str):
    username = (username or "").strip().lower()
    if not username or engine is None:
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT username, password_hash, salt FROM app_users WHERE username = :u"),
            {"u": username},
        ).mappings().first()
    return dict(row) if row else None

def db_create_user(username: str, password_hash: str, salt: str) -> bool:
    username = (username or "").strip().lower()
    if engine is None or not username:
        return False
    try:
        with engine.begin() as conn:
            # refuse si existe déjà
            exists = conn.execute(
                text("SELECT 1 FROM app_users WHERE username = :u"),
                {"u": username},
            ).scalar()
            if exists:
                return False
            conn.execute(
                text("""
                    INSERT INTO app_users (username, password_hash, salt)
                    VALUES (:u, :ph, :s)
                """),
                {"u": username, "ph": password_hash, "s": salt},
            )
        return True
    except Exception:
        return False
def db_load_watchlists(username: str) -> Dict[str, List[str]]:
    uid = db_get_user_id(username)
    if uid is None or engine is None:
        return {}

    out: Dict[str, List[str]] = {}
    with engine.connect() as conn:
        wls = conn.execute(
            text("SELECT id, name FROM watchlists WHERE user_id = :uid ORDER BY id"),
            {"uid": uid},
        ).mappings().all()

        for wl in wls:
            items = conn.execute(
                text("""
                    SELECT ticker
                    FROM watchlist_items
                    WHERE watchlist_id = :wid
                    ORDER BY id
                """),
                {"wid": wl["id"]},
            ).scalars().all()

            out[wl["name"]] = [str(t).upper().strip() for t in items if str(t).strip()]

    return out

def db_save_watchlists(username: str, wl: dict):
    uid = db_get_user_id(username)
    if uid is None or engine is None:
        return
    wl = wl or {}
    with engine.begin() as conn:
        # delete tout pour simplifier
        conn.execute(
            text("""
                DELETE FROM watchlist_items
                WHERE watchlist_id IN (SELECT id FROM watchlists WHERE user_id = :uid)
            """),
            {"uid": uid},
        )
        conn.execute(text("DELETE FROM watchlists WHERE user_id = :uid"), {"uid": uid})

        # reinsert
        for name, tickers in wl.items():
            name = (name or "").strip()
            if not name:
                continue
            wid = conn.execute(
                text("INSERT INTO watchlists (user_id, name) VALUES (:uid, :name) RETURNING id"),
                {"uid": uid, "name": name},
            ).scalar()
            for t in (tickers or []):
                t = str(t).upper().strip()
                if t:
                    conn.execute(
                        text("INSERT INTO watchlist_items (watchlist_id, ticker) VALUES (:wid, :t)"),
                        {"wid": wid, "t": t},
                    )

# -------- ALERTS --------
def db_load_alerts(username: str):
    uid = db_get_user_id(username)
    if uid is None or engine is None:
        return []
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT ticker, kind, cmp, threshold
                FROM alerts
                WHERE user_id = :uid
                ORDER BY id
            """),
            {"uid": uid},
        ).mappings().all()
    return [dict(r) for r in rows]

def db_save_alerts(username: str, alerts: list):
    uid = db_get_user_id(username)
    if uid is None or engine is None:
        return
    alerts = alerts or []
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alerts WHERE user_id = :uid"), {"uid": uid})
        for a in alerts:
            conn.execute(
                text("""
                    INSERT INTO alerts (user_id, ticker, kind, cmp, threshold)
                    VALUES (:uid, :t, :k, :c, :thr)
                """),
                {
                    "uid": uid,
                    "t": str(a.get("ticker","")).upper().strip(),
                    "k": a.get("kind"),
                    "c": a.get("cmp"),
                    "thr": float(a.get("threshold", 0.0)),
                },
            )

# -------- NOTES --------
def db_load_notes(username: str):
    uid = db_get_user_id(username)
    if uid is None or engine is None:
        return {}
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT ticker, note FROM notes WHERE user_id = :uid"),
            {"uid": uid},
        ).mappings().all()
    return {str(r["ticker"]).upper(): str(r["note"] or "") for r in rows}

def db_save_notes(username: str, notes: dict):
    uid = db_get_user_id(username)
    if uid is None or engine is None:
        return
    notes = notes or {}
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM notes WHERE user_id = :uid"), {"uid": uid})
        for t, note in notes.items():
            t = str(t).upper().strip()
            if not t:
                continue
            conn.execute(
                text("INSERT INTO notes (user_id, ticker, note) VALUES (:uid, :t, :n)"),
                {"uid": uid, "t": t, "n": str(note or "")},
            )

# -------- NEWS SUBSCRIPTIONS --------
def db_load_news_subscriptions(username: str):
    uid = db_get_user_id(username)
    if uid is None or engine is None:
        return []
    with engine.connect() as conn:
        tickers = conn.execute(
            text("SELECT ticker FROM news_subscriptions WHERE user_id = :uid ORDER BY id"),
            {"uid": uid},
        ).scalars().all()
    return sorted(list({str(t).upper().strip() for t in tickers if str(t).strip()}))

def db_save_news_subscriptions(username: str, subs: list):
    uid = db_get_user_id(username)
    if uid is None or engine is None:
        return
    subs = subs or []
    clean = sorted(list({str(t).upper().strip() for t in subs if str(t).strip()}))
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM news_subscriptions WHERE user_id = :uid"), {"uid": uid})
        for t in clean:
            conn.execute(
                text("INSERT INTO news_subscriptions (user_id, ticker) VALUES (:uid, :t)"),
                {"uid": uid, "t": t},
            )
# =========================================================
# STORAGE WRAPPERS (DB si dispo, sinon JSON fallback)
# =========================================================

# --- WATCHLISTS ---


def save_watchlists(user: str, wl: dict) -> None:
    # DB si dispo
    if engine is not None and db_get_user_id(user) is not None:
        db_save_watchlists(user, wl or {})
        return
    # fallback JSON
    json_save_watchlists(user, wl or {})


def load_watchlists(user: str) -> dict:
    # DB si dispo
    if engine is not None and db_get_user_id(user) is not None:
        return db_load_watchlists(user)
    # fallback JSON
    return json_load_watchlists(user)


# --- ALERTS ---
def json_save_alerts(user: str, alerts: list) -> None:
    if engine is not None and db_get_user_id(user) is not None:
        db_save_alerts(user, alerts or [])
        return
    json_save_alerts(user, alerts or [])


def json_load_alerts(user: str) -> list:
    if engine is not None and db_get_user_id(user) is not None:
        return db_load_alerts(user)
    return json_load_alerts(user)


# --- NOTES ---
def json_save_notes(user: str, notes: dict) -> None:
    if engine is not None and db_get_user_id(user) is not None:
        db_save_notes(user, notes or {})
        return
    json_save_notes(user, notes or {})


def json_load_notes(user: str) -> dict:
    if engine is not None and db_get_user_id(user) is not None:
        return db_load_notes(user)
    return json_load_notes(user)


# --- NEWS SUBSCRIPTIONS ---
def json_save_news_subscriptions(user: str, subs: list) -> None:
    if engine is not None and db_get_user_id(user) is not None:
        db_save_news_subscriptions(user, subs or [])
        return
    json_save_news_subscriptions(user, subs or [])


def json_load_news_subscriptions(user: str) -> list:
    if engine is not None and db_get_user_id(user) is not None:
        return db_load_news_subscriptions(user)
    return json_load_news_subscriptions(user)

# DEBUG
if st.sidebar.checkbox("DEBUG DB", value=False):
    if engine is None:
        st.sidebar.error("DB_URL manquant")
        st.sidebar.write("Clés disponibles :", list(st.secrets.keys()))
    else:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            st.sidebar.success("✅ DB connectée")

            try:
                uid = db_get_user_id(CURRENT_USER)
                st.sidebar.write("DB user id =", uid)
            except Exception as e:
                st.sidebar.error(f"db_get_user_id crash: {e}")

        except Exception as e:
            st.sidebar.error(f"❌ DB KO: {e}")





# --- Clés API (depuis Streamlit Secrets / secrets.toml local) ---
TWELVE_API_KEY = st.secrets.get("TWELVE_API_KEY", "")
FINNHUB_API_KEY = st.secrets.get("FINNHUB_API_KEY", "")
ALPHAVANTAGE_API_KEY = st.secrets.get("ALPHAVANTAGE_API_KEY", "")
POLYGON_API_KEY = st.secrets.get("POLYGON_API_KEY", "")

USERS_JSON_B64 = st.secrets.get("USERS_JSON_B64", "")
WATCHLISTS_JSON_B64 = st.secrets.get("WATCHLISTS_JSON_B64", "")
ALERTS_JSON_B64 = st.secrets.get("ALERTS_JSON_B64", "")
NOTES_JSON_B64 = st.secrets.get("NOTES_JSON_B64", "")
NEWS_SUBSCRIPTIONS_JSON_B64 = st.secrets.get("NEWS_SUBSCRIPTIONS_JSON_B64", "")





# Optionnel : PDF export
try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    HAVE_REPORTLAB = True
except Exception:
    HAVE_REPORTLAB = False


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Fantazia Finance — Comparateur V3.9",
    layout="wide"
)

# Langue par défaut
if "lang" not in st.session_state:
    st.session_state["lang"] = "fr"


# =========================================================
# TRANSLATIONS (BASIC UI)
# =========================================================
TRANSLATIONS = {
    "fr": {
        "app_title": "📈 Comparateur d'actions par secteur, Fait par Fantazia Finance ( Alexandre) — V3.9",
        "app_caption": "Outil d'analyse personnel. Aucun conseil financier. Connecté : {user}.",
        "login_title": "🔐 Fantazia Finance — Connexion",
        "login_subtitle": "Crée un compte ou connecte-toi pour utiliser le terminal Fantazia Finance.",
        "login_mode_login": "Se connecter",
        "login_mode_signup": "Créer un compte",
        "login_username": "Pseudo (min. 3 caractères)",
        "login_password": "Mot de passe (min. 6 caractères)",
        "login_password_confirm": "Confirmer le mot de passe",
        "login_btn_signup": "Créer mon compte",
        "login_btn_login": "Se connecter",
        "login_err_short_user": "Pseudo trop court (min. 3 caractères).",
        "login_err_exists": "Ce pseudo existe déjà.",
        "login_err_short_pwd": "Mot de passe trop court (min. 6 caractères).",
        "login_err_pwd_mismatch": "Les mots de passe ne correspondent pas.",
        "login_ok_signup": "Compte créé et connecté ✅",
        "login_err_missing": "Entre un pseudo et un mot de passe.",
        "login_err_not_found": "Utilisateur introuvable.",
        "login_err_corrupt": "Compte corrompu dans users.json.",
        "login_err_wrong_pwd": "Mot de passe incorrect.",
        "login_ok_login": "Connexion réussie ✅",
        "sidebar_title": "Fantazia Finance",
        "sidebar_logged_in": "👤 Connecté : {user}",
        "sidebar_logout": "Se déconnecter",
        "sidebar_mode_title": "Mode de sélection",
        "sidebar_sector": "Secteur (preset)",
        "sidebar_custom": "Liste personnalisée",
        "sidebar_watchlist": "Watchlist",
        "sidebar_select_sector": "Secteur",
        "sidebar_custom_tickers": "Tickers (séparés par virgules)",
        "sidebar_watchlist_select": "Choisis une watchlist",
        "sidebar_history": "Historique à charger",
        "sidebar_auto_adjust": "Prix ajustés (Yahoo)",
        "sidebar_source": "Source historique (fallback par action)",
        "sidebar_rt": "Activer prix temps réel (Premium Polygon)",
        "sidebar_refresh": "Auto-refresh (optionnel)",
        "sidebar_no_tickers": "Aucun ticker sélectionné.",
        "sidebar_api_detected": "Clés API détectées : ",
        "sidebar_api_none": "Aucune clé API détectée : mode Auto = Yahoo uniquement.",
        "sidebar_benchmark": "Benchmark (indice de référence)",
        "tab_dashboard": "📊 Dashboard",
        "tab_watchlists": "⭐ Watchlists",
        "tab_simulator": "💼 Simulateur",
        "tab_stock": "📄 Fiche action",
        "tab_help": "ℹ️ Aide",
        "tab_assistant": "🤖 Assistant",
        "alerts_of_day": "🚨 Alertes du jour",
        "alerts_none": "Aucune alerte déclenchée pour l'instant.",
        "alerts_config_title": "⚙️ Configurer mes alertes",
        "alerts_config_caption": "Alertes liées à ce compte. Stockées dans alerts.json.",
        "alerts_existing": "#### Alertes existantes",
        "alerts_none_for_user": "Aucune alerte définie pour l'instant.",
        "alerts_new": "#### Nouvelle alerte",
        "alerts_ticker": "Ticker",
        "alerts_type": "Type d'alerte",
        "alerts_type_pct": "Variation % journalière",
        "alerts_type_price": "Seuil de prix",
        "alerts_cond": "Condition",
        "alerts_cond_drop": "Chute ≤",
        "alerts_cond_rise": "Hausse ≥",
        "alerts_cond_price_le": "Prix ≤",
        "alerts_cond_price_ge": "Prix ≥",
        "alerts_threshold": "Seuil (en % ou en prix selon le type)",
        "alerts_save": "Ajouter / mettre à jour cette alerte",
        "alerts_saved": "Alerte enregistrée. Recharge pour prise en compte.",
        "alerts_delete_title": "#### Supprimer une alerte",
        "alerts_delete_select": "Choisir l'ID de l'alerte à supprimer",
        "alerts_delete_btn": "Supprimer cette alerte",
        "alerts_deleted": "Alerte supprimée.",
        "alerts_ribbon_info": "🔔 Le ruban affiche uniquement les alertes déjà déclenchées (variation % ou seuil de prix définis plus bas). S’il est vide, aucune alerte n'a été atteinte.",
        "sources_title": "🧩 Sources historiques utilisées par action",
        "prices_title": "⚡ Prix actuels",
        "graph_title": "📉 Graphiques",
        "graph_mode_base100": "Comparaison (base 100)",
        "graph_mode_price": "Prix réel (style plateforme)",
        "graph_mode_spread": "Spread entre 2 actions",
        "graph_choose_stock": "Choisir une action",
        "graph_log_scale": "Échelle logarithmique",
        "graph_spread_info": "Choisis deux actions différentes pour le spread.",
        "graph_spread_how": "- Si la courbe **monte** → {a} surperforme {b}.\n- Si la courbe **descend** → {a} sous-performe {b}.\n- Spread = différence entre leurs courbes en base 100.",
        "scores_top_title": "🏁 Top du classement (Fantazia Score)",
        "table_title": "📌 Comparaison complète",
        "table_filters": "🎛️ Filtres & tri du tableau",
        "table_min_score": "Fantazia Score minimum (%)",
        "table_hide_neg1y": "Masquer les actions avec Perf 1Y négative",
        "table_sort_by": "Trier par",
        "table_sort_desc": "Descendant (meilleurs en haut)",
        "table_sort_asc": "Ascendant",
        "table_mode": "Mode d'affichage du tableau",
        "table_mode_simple": "Simple",
        "table_mode_advanced": "Avancé",
        "heatmap_title": "🔥 Heatmap performances",
        "heatmap_legend": "Légende : Vert = performance positive, Rouge = performance négative, intensité = force du mouvement. Colonnes = horizons (1M, 3M, 6M, 1Y), lignes = tickers.",
        "corr_title": "🔗 Corrélation des rendements (journalier)",
        "corr_caption": "La corrélation mesure à quel point les actions bougent ensemble : 1 = très corrélées, 0 = indépendant, -1 = sens opposé.",
        "export_csv": "⬇️ Télécharger le tableau (CSV)",
        "score_details_title": "🧮 Détails du Fantazia Score",
        "custom_score_title": "⚙️ Fantazia Score personnalisé",
        "custom_score_enable": "Activer le Fantazia Score personnalisé",
        "custom_score_info": "Si activé, les classements et filtres utilisent ton Fantazia Score perso (basé sur les poids ci-dessous). Le score officiel reste visible pour référence.",
        "tech_notes_title": "ℹ️ Notes techniques",
        "mynews_title": "📰 Mes news suivies (abonnements)",
        "mynews_no_key": "Aucune clé Finnhub configurée → impossible de charger les news. Ajoute `FINNHUB_API_KEY` dans Streamlit Secrets.",
        "mynews_no_subs": "Tu n'es abonné aux news d'aucune action pour l'instant. Va dans l'onglet **📄 Fiche action** et coche *\"Suivre les news de TICKER\"*.",
        "mynews_none_recent": "Aucune news récente trouvée pour tes abonnements, ou bien rafraîchissez la page.",
        "watchlists_title": "⭐ Gérer tes watchlists (locales, liées à ton compte)",
        "watchlists_caption": "Enregistrées dans {file} sous la clé '{user}'.",
        "watchlists_create": "### Créer / Remplacer",
        "watchlists_name": "Nom de la watchlist",
        "watchlists_tickers": "Tickers (séparés par virgules)",
        "watchlists_save": "Enregistrer",
        "watchlists_saved": "Watchlist '{name}' enregistrée ({n} tickers) pour {user}.",
        "watchlists_existing": "### Watchlists existantes",
        "watchlists_none": "Aucune watchlist pour l'instant sur ce compte.",
        "watchlists_delete_title": "### Supprimer",
        "watchlists_delete_select": "Choisis une watchlist à supprimer",
        "watchlists_delete_btn": "Supprimer",
        "watchlists_deleted": "Watchlist '{name}' supprimée pour {user}.",
        "watchlists_export": "⬇️ Télécharger mes watchlists (JSON)",
        "sim_title": "💼 Simulateur simple de portefeuille",
        "sim_caption": "Hypothèse : achat au début de l'historique chargé, valeur actuelle = dernier prix.",
        "sim_not_enough": "Pas assez d'historique pour simuler (au moins 2 dates nécessaires).",
        "sim_capital": "Capital initial (€)",
        "sim_alloc_mode": "Mode d'allocation",
        "sim_alloc_equal": "Poids égaux",
        "sim_alloc_custom": "Poids personnalisés (%)",
        "sim_weight_for": "Poids {ticker} (%)",
        "sim_warn_weights": "Somme des poids <= 0 : on repasse en poids égaux.",
        "sim_capital_init": "Capital initial",
        "sim_current_value": "Valeur actuelle",
        "sim_global_perf": "Performance globale",
        "sim_detail": "Détail par ligne",
        "stock_title": "📄 Fiche détaillée par action",
        "stock_follow_news": "Suivre les news de {ticker}",
        "stock_follow_added": "Tu es maintenant abonné aux news de {ticker}.",
        "stock_follow_removed": "Abonnement aux news de {ticker} supprimé.",
        "stock_price_history": "#### Prix historique",
        "stock_pe_history": "#### P/E approximatif dans le temps",
        "stock_pe_unavailable": "EPS (trailing) indisponible → impossible de tracer un P/E approximatif.",
        "stock_pe_caption": "Approximation : P/E(t) = Prix(t) / EPS_actuel. Ce n'est pas un vrai historique de P/E, mais une vision de la valorisation si l'EPS restait constant.",
        "stock_raw_data": "### Données brutes (fondamentaux)",
        "stock_news_title": "### 📰 Actualités récentes sur l'action",
        "stock_news_none": "Aucune news récente trouvée pour ce ticker (ou limite API atteinte).",
        "stock_note_label": "📝 Note personnelle pour {ticker}",
        "stock_note_saved": "Note enregistrée pour {ticker}.",
        "stock_pdf_btn": "📄 Exporter la fiche en PDF",
        "stock_pdf_no_lib": "Export PDF indisponible (librairie `reportlab` non installée).",
        "help_title": "ℹ️ Aide rapide — V3.9 (comptes, Fantazia Score %, alertes, news & assistant)",
        "help_api_status": "### Statut des clés API",
        "help_glossary": "📚 Glossaire rapide (termes financiers)",
        "assistant_title": "🤖 Assistant Fantazia (FAQ)",
        "assistant_caption": "Pose tes questions sur le fonctionnement du site : Fantazia Score, graphiques, watchlists, alertes, simulateur, benchmark, corrélation, news, etc.",
        "assistant_input": "Ta question sur Fantazia Finance...",
    },
    "en": {
        "app_title": "📈 Sector Stock Comparator, made by Fantazia Finance (Alexandre) — V3.9",
        "app_caption": "Personal analysis tool. No financial advice. Logged in as: {user}.",
        "login_title": "🔐 Fantazia Finance — Login",
        "login_subtitle": "Create an account or log in to use the Fantazia Finance terminal.",
        "login_mode_login": "Log in",
        "login_mode_signup": "Sign up",
        "login_username": "Username (min. 3 characters)",
        "login_password": "Password (min. 6 characters)",
        "login_password_confirm": "Confirm password",
        "login_btn_signup": "Create my account",
        "login_btn_login": "Log in",
        "login_err_short_user": "Username too short (min. 3 characters).",
        "login_err_exists": "This username already exists.",
        "login_err_short_pwd": "Password too short (min. 6 characters).",
        "login_err_pwd_mismatch": "Passwords do not match.",
        "login_ok_signup": "Account created and logged in ✅",
        "login_err_missing": "Enter a username and a password.",
        "login_err_not_found": "User not found.",
        "login_err_corrupt": "Account corrupted in users.json.",
        "login_err_wrong_pwd": "Incorrect password.",
        "login_ok_login": "Login successful ✅",
        "sidebar_title": "Fantazia Finance",
        "sidebar_logged_in": "👤 Logged in as: {user}",
        "sidebar_logout": "Log out",
        "sidebar_mode_title": "Selection mode",
        "sidebar_sector": "Sector (preset)",
        "sidebar_custom": "Custom list",
        "sidebar_watchlist": "Watchlist",
        "sidebar_select_sector": "Sector",
        "sidebar_custom_tickers": "Tickers (comma-separated)",
        "sidebar_watchlist_select": "Choose a watchlist",
        "sidebar_history": "History to load",
        "sidebar_auto_adjust": "Adjusted prices (Yahoo)",
        "sidebar_source": "Historical source (per-stock fallback)",
        "sidebar_rt": "Enable real-time prices (Premium Polygon)",
        "sidebar_refresh": "Auto-refresh (optional)",
        "sidebar_no_tickers": "No ticker selected.",
        "sidebar_api_detected": "API keys detected: ",
        "sidebar_api_none": "No API key detected: Auto mode = Yahoo only.",
        "sidebar_benchmark": "Benchmark (reference index)",
        "tab_dashboard": "📊 Dashboard",
        "tab_watchlists": "⭐ Watchlists",
        "tab_simulator": "💼 Simulator",
        "tab_stock": "📄 Stock sheet",
        "tab_help": "ℹ️ Help",
        "tab_assistant": "🤖 Assistant",
        "alerts_of_day": "🚨 Alerts of the day",
        "alerts_none": "No alerts triggered yet.",
        "alerts_config_title": "⚙️ Configure my alerts",
        "alerts_config_caption": "Alerts are linked to this account. Stored in alerts.json.",
        "alerts_existing": "#### Existing alerts",
        "alerts_none_for_user": "No alert defined yet.",
        "alerts_new": "#### New alert",
        "alerts_ticker": "Ticker",
        "alerts_type": "Alert type",
        "alerts_type_pct": "Daily % change",
        "alerts_type_price": "Price threshold",
        "alerts_cond": "Condition",
        "alerts_cond_drop": "Drop ≤",
        "alerts_cond_rise": "Rise ≥",
        "alerts_cond_price_le": "Price ≤",
        "alerts_cond_price_ge": "Price ≥",
        "alerts_threshold": "Threshold (in % or price)",
        "alerts_save": "Add / update this alert",
        "alerts_saved": "Alert saved. Reload to take effect.",
        "alerts_delete_title": "#### Delete an alert",
        "alerts_delete_select": "Choose the alert ID to delete",
        "alerts_delete_btn": "Delete this alert",
        "alerts_deleted": "Alert deleted.",
        "alerts_ribbon_info": "🔔 The ribbon only shows alerts that have already been triggered (daily % change or price threshold you configured below). If empty, no alert has been hit.",
        "sources_title": "🧩 Historical sources used per stock",
        "prices_title": "⚡ Current prices",
        "graph_title": "📉 Charts",
        "graph_mode_base100": "Comparison (base 100)",
        "graph_mode_price": "Real price (platform style)",
        "graph_mode_spread": "Spread between 2 stocks",
        "graph_choose_stock": "Choose a stock",
        "graph_log_scale": "Log scale",
        "graph_spread_info": "Pick two different stocks for the spread.",
        "graph_spread_how": "- If the curve **goes up** → {a} outperforms {b}.\n- If the curve **goes down** → {a} underperforms {b}.\n- Spread = difference between their base 100 curves.",
        "scores_top_title": "🏁 Ranking top (Fantazia Score)",
        "table_title": "📌 Full comparison",
        "table_filters": "🎛️ Table filters & sorting",
        "table_min_score": "Minimum Fantazia Score (%)",
        "table_hide_neg1y": "Hide stocks with negative 1Y performance",
        "table_sort_by": "Sort by",
        "table_sort_desc": "Descending (best on top)",
        "table_sort_asc": "Ascending",
        "table_mode": "Table display mode",
        "table_mode_simple": "Simple",
        "table_mode_advanced": "Advanced",
        "heatmap_title": "🔥 Performance heatmap",
        "heatmap_legend": "Legend: Green = positive performance, Red = negative performance, intensity = strength of move. Columns = horizons (1M, 3M, 6M, 1Y), rows = tickers.",
        "corr_title": "🔗 Correlation of returns (daily)",
        "corr_caption": "Correlation measures how much stocks move together: 1 = highly correlated, 0 = independent, -1 = opposite moves.",
        "export_csv": "⬇️ Download table (CSV)",
        "score_details_title": "🧮 Fantazia Score details",
        "custom_score_title": "⚙️ Custom Fantazia Score",
        "custom_score_enable": "Enable custom Fantazia Score",
        "custom_score_info": "If enabled, rankings and filters use your custom Fantazia Score (based on the weights below). The official score remains visible for reference.",
        "tech_notes_title": "ℹ️ Technical notes",
        "mynews_title": "📰 My followed news (subscriptions)",
        "mynews_no_key": "No Finnhub key configured → cannot load news. Add `FINNHUB_API_KEY` in Streamlit Secrets.",
        "mynews_no_subs": "You are not subscribed to any stock news yet. Go to **📄 Stock sheet** and check *\"Follow news of TICKER\"*.",
        "mynews_none_recent": "No recent news found for your subscriptions, or please refresh the page.",
        "watchlists_title": "⭐ Manage your watchlists (local, account-linked)",
        "watchlists_caption": "Stored in {file} under key '{user}'.",
        "watchlists_create": "### Create / Replace",
        "watchlists_name": "Watchlist name",
        "watchlists_tickers": "Tickers (comma-separated)",
        "watchlists_save": "Save",
        "watchlists_saved": "Watchlist '{name}' saved ({n} tickers) for {user}.",
        "watchlists_existing": "### Existing watchlists",
        "watchlists_none": "No watchlist yet for this account.",
        "watchlists_delete_title": "### Delete",
        "watchlists_delete_select": "Choose a watchlist to delete",
        "watchlists_delete_btn": "Delete",
        "watchlists_deleted": "Watchlist '{name}' deleted for {user}.",
        "watchlists_export": "⬇️ Download my watchlists (JSON)",
        "sim_title": "💼 Simple portfolio simulator",
        "sim_caption": "Assumption: buy at the beginning of loaded history, current value = last price.",
        "sim_not_enough": "Not enough history to simulate (need at least 2 dates).",
        "sim_capital": "Initial capital (€)",
        "sim_alloc_mode": "Allocation mode",
        "sim_alloc_equal": "Equal weights",
        "sim_alloc_custom": "Custom weights (%)",
        "sim_weight_for": "Weight {ticker} (%)",
        "sim_warn_weights": "Sum of weights <= 0: fallback to equal weights.",
        "sim_capital_init": "Initial capital",
        "sim_current_value": "Current value",
        "sim_global_perf": "Global performance",
        "sim_detail": "Details per line",
        "stock_title": "📄 Detailed stock sheet",
        "stock_follow_news": "Follow news of {ticker}",
        "stock_follow_added": "You are now subscribed to news for {ticker}.",
        "stock_follow_removed": "Subscription to news for {ticker} removed.",
        "stock_price_history": "#### Price history",
        "stock_pe_history": "#### Approximate P/E over time",
        "stock_pe_unavailable": "EPS (trailing) unavailable → cannot plot approximate P/E.",
        "stock_pe_caption": "Approximation: P/E(t) = Price(t) / current EPS. Not a real historical P/E, but a view of valuation if EPS stayed constant.",
        "stock_raw_data": "### Raw data (fundamentals)",
        "stock_news_title": "### 📰 Recent news on this stock",
        "stock_news_none": "No recent news found for this ticker (or API limit reached).",
        "stock_note_label": "📝 Personal note for {ticker}",
        "stock_note_saved": "Note saved for {ticker}.",
        "stock_pdf_btn": "📄 Export sheet to PDF",
        "stock_pdf_no_lib": "PDF export unavailable (`reportlab` library not installed).",
        "help_title": "ℹ️ Quick help — V3.9 (accounts, Fantazia Score %, alerts, news & assistant)",
        "help_api_status": "### API keys status",
        "help_glossary": "📚 Quick glossary (financial terms)",
        "assistant_title": "🤖 Fantazia Assistant (FAQ)",
        "assistant_caption": "Ask questions about how the site works: Fantazia Score, charts, watchlists, alerts, simulator, benchmark, correlation, news, etc.",
        "assistant_input": "Your question about Fantazia Finance...",
    },
}


def tr(key: str) -> str:
    lang = st.session_state.get("lang", "fr")
    return TRANSLATIONS.get(lang, {}).get(key, TRANSLATIONS["fr"].get(key, key))


# =========================================================
# OPTIONAL AUTO-REFRESH SUPPORT
# =========================================================
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except Exception:
    HAS_AUTOREFRESH = False


# =========================================================
# THEME LIGHT FANTAZIA + 52w RANGE
# =========================================================
def apply_fantazia_theme():
    accent = "#f5c400"
    accent_soft = "#ffdd55"

    lines = [
        "<style>",
        "/* ---- Boutons Fantazia ---- */",
        ".stButton>button {",
        f"  background: {accent};",
        "  color: #0a0a0a;",
        "  border: 0px solid transparent;",
        "  border-radius: 10px;",
        "  font-weight: 700;",
        "  padding: 0.45rem 0.9rem;",
        "  box-shadow: 0 4px 12px rgba(0,0,0,0.15);",
        "  transition: all 0.15s ease-out;",
        "}",
        ".stButton>button:hover {",
        f"  background: {accent_soft};",
        "  color: #000;",
        "  transform: translateY(-1px);",
        "  box-shadow: 0 6px 18px rgba(0,0,0,0.20);",
        "}",

        "button[data-baseweb='tab'][aria-selected='true'] {",
        f"  border-bottom: 2px solid {accent};",
        "}",

        "/* ---- Metrics (st.metric) ---- */",
        "[data-testid='stMetric'] {",
        "  padding: 10px 12px;",
        "  border-radius: 12px;",
        "  background: rgba(245,245,245,0.9);",
        "  border: 1px solid rgba(0,0,0,0.06);",
        "  box-shadow: 0 2px 10px rgba(0,0,0,0.06);",
        "  animation: ff-metric-in 0.25s ease-out;",
        "  transform-origin: center;",
        "  transition: transform 0.12s ease-out, box-shadow 0.12s ease-out;",
        "}",
        "[data-testid='stMetric']:hover {",
        "  transform: translateY(-1px) scale(1.01);",
        "  box-shadow: 0 4px 16px rgba(0,0,0,0.10);",
        "}",

        "/* ---- Marquee alertes ---- */",
        ".ff-marquee {",
        "  width: 100%;",
        "  overflow: hidden;",
        "  white-space: nowrap;",
        "  border-radius: 999px;",
        "  border: 1px solid rgba(0,0,0,0.08);",
        "  background: rgba(255, 250, 230, 0.95);",
        "  padding: 4px 10px;",
        "  margin-bottom: 4px;",
        "}",
        ".ff-marquee-inner {",
        "  display: inline-block;",
        "  padding-left: 100%;",
        "  animation: ff-marquee-move 35s linear infinite;",
        "}",

        "/* ---- 52w range ---- */",
        ".ff-52w {",
        "  margin-top: 8px;",
        "}",
        ".ff-52w-labels {",
        "  display: flex;",
        "  justify-content: space-between;",
        "  font-size: 0.8rem;",
        "  margin-bottom: 4px;",
        "}",
        ".ff-52w-bar {",
        "  position: relative;",
        "  height: 10px;",
        "}",
        ".ff-52w-track {",
        "  position: absolute;",
        "  top: 4px;",
        "  left: 0;",
        "  right: 0;",
        "  height: 2px;",
        "  background: rgba(0,0,0,0.15);",
        "  border-radius: 999px;",
        "}",
        ".ff-52w-marker {",
        "  position: absolute;",
        "  top: 0px;",
        "  width: 10px;",
        "  height: 10px;",
        f"  background: {accent};",
        "  border-radius: 50%;",
        "  transform: translateX(-50%);",
        "  box-shadow: 0 0 4px rgba(0,0,0,0.4);",
        "}",
                "/* ---- Cadran analystes : échelle horizontale ---- */",
        ".ff-analyst-card {",
        "  max-width: 430px;",
        "  background: #ffffff;",
        "  border-radius: 16px;",
        "  border: 1px solid rgba(15,23,42,0.06);",
        "  box-shadow: 0 8px 24px rgba(15,23,42,0.06);",
        "  padding: 12px 16px 10px;",
        "  margin-top: 6px;",
        "}",
        ".ff-analyst-header {",
        "  display: flex;",
        "  align-items: center;",
        "  justify-content: flex-start;",
        "  margin-bottom: 6px;",
        "}",
        ".ff-analyst-main-label {",
        "  font-weight: 700;",
        "  font-size: 0.95rem;",
        "}",
        ".ff-analyst-scale {",
        "  display: flex;",
        "  gap: 4px;",
        "  margin-bottom: 4px;",
        "}",
        ".ff-analyst-step {",
        "  flex: 1;",
        "  text-align: center;",
        "  font-size: 0.75rem;",
        "  padding: 4px 2px;",
        "  border-radius: 999px;",
        "  background: #f3f4f6;",
        "  color: #6b7280;",
        "  border: 1px solid transparent;",
        "}",
        ".ff-analyst-step-active {",
        "  color: #ffffff;",
        "  font-weight: 600;",
        "  border-color: rgba(15,23,42,0.25);",
        "}",
        ".ff-analyst-step-0.ff-analyst-step-active {",
        "  background: #b91c1c;",  # Fort vente → rouge
        "}",
        ".ff-analyst-step-1.ff-analyst-step-active {",
        "  background: #f97316;",  # Vente → orange
        "}",
        ".ff-analyst-step-2.ff-analyst-step-active {",
        "  background: #6b7280;",  # Neutre → gris
        "}",
        ".ff-analyst-step-3.ff-analyst-step-active {",
        "  background: #22c55e;",  # Achat → vert
        "}",
        ".ff-analyst-step-4.ff-analyst-step-active {",
        "  background: #16a34a;",  # Fort achat → vert foncé
        "}",
        ".ff-analyst-caption {",
        "  margin-top: 4px;",
        "  font-size: 0.8rem;",
        "  color: #4b5563;",
        "}",



        "/* ---- Animations keyframes ---- */",
        "@keyframes ff-marquee-move {",
        "  0% { transform: translateX(0%); }",
        "  100% { transform: translateX(-100%); }",
        "}",
        "@keyframes ff-metric-in {",
        "  0% {",
        "    opacity: 0;",
        "    transform: translateY(6px) scale(0.99);",
        "  }",
        "  100% {",
        "    opacity: 1;",
        "    transform: translateY(0) scale(1.0);",
        "  }",
        "}",

        "/* ---- Responsive ---- */",
        "@media (max-width: 768px) {",
        "  [data-testid='stMetric'] {",
        "      padding: 6px 8px;",
        "  }",
        "  h1, h2, h3 {",
        "      font-size: 0.95em;",
        "  }",
        "}",
        "</style>",
    ]
    st.markdown("\n".join(lines), unsafe_allow_html=True)





apply_fantazia_theme()


# =========================================================
# WATERMARK LOGO
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


def rerun_app():
    try:
        st.experimental_rerun()
    except Exception:
        try:
            st.rerun()
        except Exception:
            pass


# =========================================================
# FILES
# =========================================================
USERS_FILE = "users.json"
WATCHLIST_FILE = "watchlists.json"
NEWS_SUB_FILE = "news_subscriptions.json"
CONFIG_FILE = "config.json"
ALERTS_FILE = "alerts.json"
NOTES_FILE = "notes.json"

def seed_file_from_b64(path: str, b64_value: str, default_json_obj):
    # Si le fichier existe déjà, on ne touche à rien
    if os.path.exists(path):
        return

    # Si secret présent -> on restaure depuis base64
    if isinstance(b64_value, str) and b64_value.strip():
        try:
            raw = base64.b64decode(b64_value.encode("utf-8"))
            with open(path, "wb") as f:
                f.write(raw)
            return
        except Exception:
            pass

    # Sinon -> on crée un JSON par défaut (vide)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_json_obj, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# Seed des fichiers JSON (option 1)
seed_file_from_b64(USERS_FILE, USERS_JSON_B64, {})
seed_file_from_b64(WATCHLIST_FILE, WATCHLISTS_JSON_B64, {})
seed_file_from_b64(ALERTS_FILE, ALERTS_JSON_B64, {})
seed_file_from_b64(NOTES_FILE, NOTES_JSON_B64, {})
seed_file_from_b64(NEWS_SUB_FILE, NEWS_SUBSCRIPTIONS_JSON_B64, {})

# =========================================================
# USERS
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
    if "user" in st.session_state and st.session_state["user"]:
        return st.session_state["user"]

    st.title(tr("login_title"))
    st.write(tr("login_subtitle"))

    mode = st.radio(
        "",
        [tr("login_mode_login"), tr("login_mode_signup")],
        horizontal=True,
    )

    username_input = st.text_input(tr("login_username"))
    password_input = st.text_input(tr("login_password"), type="password")
    msg = st.empty()
    users = load_users()

    if mode == tr("login_mode_signup"):
        password_confirm = st.text_input(tr("login_password_confirm"), type="password")

        if st.button(tr("login_btn_signup")):
            username = username_input.strip().lower()
            pwd = password_input
            pwd2 = password_confirm

            if not username or len(username) < 3:
                msg.error(tr("login_err_short_user"))
            elif username in users:
                msg.error(tr("login_err_exists"))
            elif not pwd or len(pwd) < 6:
                msg.error(tr("login_err_short_pwd"))
            elif pwd != pwd2:
                msg.error(tr("login_err_pwd_mismatch"))
            else:
                salt = secrets.token_hex(16)
                pwd_hash = hash_password(pwd, salt)

                # Save in JSON
                users[username] = {"password_hash": pwd_hash, "salt": salt}
                save_users(users)

                # Sync user in DB (so DB storage works)
                if engine is not None:
                    db_create_user(username, pwd_hash, salt)

                st.session_state["user"] = username
                msg.success(tr("login_ok_signup"))
                rerun_app()

    else:
        if st.button(tr("login_btn_login")):
            username = username_input.strip().lower()
            pwd = password_input

            if not username or not pwd:
                msg.error(tr("login_err_missing"))
            elif username not in users:
                msg.error(tr("login_err_not_found"))
            else:
                user_rec = users[username]
                salt = user_rec.get("salt", "")
                expected = user_rec.get("password_hash", "")

                if not salt or not expected:
                    msg.error(tr("login_err_corrupt"))
                else:
                    if hash_password(pwd, salt) == expected:
                        # Ensure user exists in DB (so DB storage works)
                        if engine is not None:
                            db_create_user(username, expected, salt)

                        st.session_state["user"] = username
                        msg.success(tr("login_ok_login"))
                        rerun_app()
                    else:
                        msg.error(tr("login_err_wrong_pwd"))

    st.stop()



CURRENT_USER = ensure_authenticated()

# DEBUG: afficher l'id DB de l'utilisateur




# =========================================================
# SECTORS (avec nouveaux presets 3.9)
# =========================================================
SECTORS = {
    "Mega Tech US": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"],
    "Semi-conducteurs": ["NVDA", "AMD", "INTC", "TSM", "ASML"],
    "Banques US": ["JPM", "BAC", "WFC", "C", "GS", "MS"],
    "Pétrole & Énergie": ["XOM", "CVX", "SHEL", "TTE", "BP"],
    "Luxe (Europe)": ["MC.PA", "RMS.PA", "KER.PA", "PRU.L", "BRBY.L"],

    # Nouveaux presets 3.9 (validés)
    "Automobile mondial": ["TSLA", "F", "GM", "STLA", "RNO.PA", "BMW.DE", "MBG.DE"],
    "Divertissement / Streaming": ["NFLX", "DIS", "WBD", "RBLX", "SONY"],
    "Pharma / Santé": ["JNJ", "PFE", "MRK", "LLY", "SAN.PA"],
    "Consommation de base": ["PG", "KO", "PEP", "ULVR.L", "WMT"],
    "Télécoms": ["VZ", "T", "ORAN.PA", "VOD.L"],
    "Défense / Aérospatial": ["LMT", "NOC", "RTX", "BA", "AIR.PA"],
}


# =========================================================
# CONFIG (fallback local uniquement, ne doit PAS écraser les secrets)
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



# =========================================================
# WATCHLISTS
# =========================================================
def json_load_watchlists(user: str) -> Dict[str, List[str]]:
    # ✅ DB si dispo
    if engine is not None:
        try:
            return db_load_watchlists(user)
        except Exception:
            pass

    # 🔁 Fallback JSON
    if not os.path.exists(WATCHLIST_FILE):
        return {}
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    if isinstance(data, dict) and user in data and isinstance(data[user], dict):
        base = data[user]
    else:
        base = {}

    clean = {}
    for name, vals in base.items():
        if isinstance(vals, list):
            clean[name] = [str(x).upper().strip() for x in vals if str(x).strip()]
    return clean


def json_save_watchlists(user: str, wl: Dict[str, List[str]]) -> None:
    # ✅ DB si dispo
    if engine is not None:
        try:
            db_save_watchlists(user, wl)
            return
        except Exception:
            pass

    # 🔁 Fallback JSON
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
# NEWS SUBSCRIPTIONS
# =========================================================
def json_load_news_subscriptions(user: str) -> List[str]:
    if not os.path.exists(NEWS_SUB_FILE):
        return []
    try:
        with open(NEWS_SUB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    subs = data.get(user, [])
    if not isinstance(subs, list):
        return []
    return sorted(list({str(t).upper().strip() for t in subs if str(t).strip()}))


def json_save_news_subscriptions(user: str, subs: List[str]) -> None:
    clean = sorted(list({str(t).upper().strip() for t in subs if str(t).strip()}))
    data = {}
    if os.path.exists(NEWS_SUB_FILE):
        try:
            with open(NEWS_SUB_FILE, "r", encoding="utf-8") as f:
                tmp = json.load(f)
            if isinstance(tmp, dict):
                data = tmp
        except Exception:
            data = {}
    data[user] = clean
    with open(NEWS_SUB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================================================
# ALERTS
# =========================================================
def json_load_alerts(user: str) -> List[Dict]:
    if not os.path.exists(ALERTS_FILE):
        return []
    try:
        with open(ALERTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    alerts = data.get(user, [])
    if not isinstance(alerts, list):
        return []
    clean_alerts = []
    for a in alerts:
        if isinstance(a, dict) and "ticker" in a and "kind" in a and "cmp" in a and "threshold" in a:
            clean_alerts.append(a)
    return clean_alerts


def json_save_alerts(user: str, alerts: List[Dict]) -> None:
    data = {}
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, "r", encoding="utf-8") as f:
                tmp = json.load(f)
            if isinstance(tmp, dict):
                data = tmp
        except Exception:
            data = {}
    data[user] = alerts
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================================================
# NOTES PERSO
# =========================================================
def json_load_notes(user: str) -> Dict[str, str]:
    if not os.path.exists(NOTES_FILE):
        return {}
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    user_notes = data.get(user, {})
    if not isinstance(user_notes, dict):
        return {}
    return {str(k).upper(): str(v) for k, v in user_notes.items()}


def json_save_notes(user: str, notes: Dict[str, str]) -> None:
    data = {}
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                tmp = json.load(f)
            if isinstance(tmp, dict):
                data = tmp
        except Exception:
            data = {}
    clean = {str(k).upper(): str(v) for k, v in notes.items() if str(k).strip()}
    data[user] = clean
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------
# Prix + devise (pour affichage)
# ---------------------------------------------------------
def format_price_with_currency(ticker: str, price: float) -> str:
    """
    Retourne un prix formaté avec la devise si dispo dans le DataFrame 'fund'.
    Exemple : 178.34 $ ou 52.10 €.
    Si la devise est inconnue -> juste le prix avec 2 décimales.
    """
    try:
        cur = None
        # On essaye de lire la devise dans le DF 'fund' (global)
        if "fund" in globals():
            global fund
            if isinstance(fund, pd.DataFrame) and ticker in fund.index:
                cur = fund.loc[ticker].get("Devise", None)
    except Exception:
        cur = None

    # Mapping simple pour les symboles les plus courants
    symbol_map = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "CHF": "CHF",
        "JPY": "¥",
    }

    if cur:
        symbol = symbol_map.get(str(cur).upper(), str(cur))
        return f"{price:.2f} {symbol}"
    else:
        return f"{price:.2f}"

# =========================================================
# DISPLAY HELPERS
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


def perf_color(val):
    try:
        v = float(val)
    except Exception:
        return ""
    if np.isnan(v):
        return ""
    if v > 0:
        return "background-color: rgba(0,200,100,0.15);"
    if v < 0:
        return "background-color: rgba(230,80,80,0.15);"
    return ""


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
# PRICE PROVIDERS
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
# NEWS FINNHUB
# =========================================================
@st.cache_data(ttl=900)
def load_news_finnhub(ticker: str, days: int = 7, max_items: int = 10) -> pd.DataFrame:
    if not FINNHUB_API_KEY:
        return pd.DataFrame()
    try:
        end = pd.Timestamp.utcnow().normalize()
        start = end - pd.Timedelta(days=days)
        url = "https://finnhub.io/api/v1/company-news"
        params = {
            "symbol": ticker.upper(),
            "from": start.date().isoformat(),
            "to": end.date().isoformat(),
            "token": FINNHUB_API_KEY,
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 429:
            return pd.DataFrame()
        data = r.json() if r.content else []
        if not isinstance(data, list) or not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"], unit="s", utc=True).dt.tz_convert(None)
        df = df.sort_values("datetime", ascending=False)
        if max_items:
            df = df.head(max_items)
        cols = []
        for c in ["datetime", "source", "headline", "summary", "url"]:
            if c in df.columns:
                cols.append(c)
        return df[cols]
    except Exception:
        return pd.DataFrame()


# =========================================================
# FALLBACK PER TICKER
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
    if source_mode.startswith("Yahoo"):
        return [("yfinance", provider_yahoo)]
    if source_mode.startswith("Twelve"):
        return [("twelve data", provider_twelve)]
    if source_mode.startswith("Finnhub"):
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
# BENCHMARK (Indice)
# =========================================================
@st.cache_data
def fetch_benchmark_series(ticker: str, period: str, auto_adjust: bool) -> pd.Series:
    if not ticker:
        return pd.Series(dtype=float)
    return fetch_yfinance_single(ticker, period, auto_adjust)


# =========================================================
# FUNDAMENTALS
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
            # === NOUVEAU : données analystes Yahoo ===
            "Reco (brut)": info.get("recommendationKey"),
            "Reco moyenne": info.get("recommendationMean"),
            "Nb analystes": info.get("numberOfAnalystOpinions"),
        })
    return pd.DataFrame(rows).set_index("Ticker")



# =========================================================
# SIDEBAR LANGUAGE SWITCH (AVANT TITRE)
# =========================================================
st.sidebar.markdown("**Language / Langue**")
lang_choice = st.sidebar.radio(
    "",
    ["FR", "EN"],
    horizontal=True,
    index=0 if st.session_state.get("lang", "fr") == "fr" else 1,
)
st.session_state["lang"] = "fr" if lang_choice == "FR" else "en"


# =========================================================
# TITLE
# =========================================================
st.title(tr("app_title"))
st.caption(tr("app_caption").format(user=CURRENT_USER))


# =========================================================
# SIDEBAR
# =========================================================
try:
    st.sidebar.image("Fantazia finance logo chatgpt.png", width=140)
except Exception:
    pass

st.sidebar.markdown(f"### {tr('sidebar_title')}")
st.sidebar.markdown(tr("sidebar_logged_in").format(user=CURRENT_USER))

if st.sidebar.button(tr("sidebar_logout")):
    st.session_state.clear()
    rerun_app()

st.sidebar.markdown("---")
st.sidebar.header(tr("sidebar_mode_title"))

watchlists_sidebar = load_watchlists(CURRENT_USER)

mode = st.sidebar.radio(
    "",
    [tr("sidebar_sector"), tr("sidebar_custom"), tr("sidebar_watchlist")],
    index=0
)

tickers: List[str] = []
sector_label = ""

if mode == tr("sidebar_sector"):
    sector_label = st.sidebar.selectbox(tr("sidebar_select_sector"), list(SECTORS.keys()))
    tickers = SECTORS[sector_label]
elif mode == tr("sidebar_custom"):
    sector_label = "Liste perso"
    txt = st.sidebar.text_area(tr("sidebar_custom_tickers"), value="AAPL, MSFT, NVDA", height=80)
    tickers = parse_tickers(txt)
else:
    sector_label = "Watchlist"
    if watchlists_sidebar:
        wl_name = st.sidebar.selectbox(tr("sidebar_watchlist_select"), list(watchlists_sidebar.keys()))
        tickers = watchlists_sidebar.get(wl_name, [])
    else:
        st.sidebar.info(tr("watchlists_none"))
        tickers = []

st.sidebar.divider()

history_period = st.sidebar.selectbox(
    tr("sidebar_history"),
    ["1d", "5d", "1mo", "3mo", "1y", "3y", "5y"],
    index=4
)
use_auto_adjust = st.sidebar.checkbox(tr("sidebar_auto_adjust"), value=True)

price_source_mode = st.sidebar.selectbox(
    tr("sidebar_source"),
    [
        "Auto (Yahoo → Twelve → Finnhub)",
        "Yahoo Finance (yfinance)",
        "Twelve Data",
        "Finnhub"
    ],
    index=0
)

use_realtime = st.sidebar.checkbox(
    tr("sidebar_rt"),
    value=False
)

refresh_seconds = st.sidebar.selectbox(
    tr("sidebar_refresh"),
    [0, 10, 20, 30, 60],
    index=0,
    help="Requires streamlit-autorefresh."
)

benchmark_options = {
    "Aucun": "",
    "^GSPC (S&P 500)": "^GSPC",
    "^NDX (Nasdaq 100)": "^NDX",
    "^FCHI (CAC 40)": "^FCHI",
    "^STOXX50E (Euro Stoxx 50)": "^STOXX50E",
}
bm_label = st.sidebar.selectbox(tr("sidebar_benchmark"), list(benchmark_options.keys()), index=0)
benchmark_ticker = benchmark_options[bm_label]

st.sidebar.divider()

api_status = []
if TWELVE_API_KEY:
    api_status.append("Twelve Data")
if FINNHUB_API_KEY:
    api_status.append("Finnhub")
if POLYGON_API_KEY:
    api_status.append("Polygon")

if api_status:
    st.sidebar.caption(tr("sidebar_api_detected") + ", ".join(api_status))
else:
    st.sidebar.caption(tr("sidebar_api_none"))

if not tickers:
    st.warning(tr("sidebar_no_tickers"))
    st.stop()

tickers = [t.upper() for t in tickers]

if refresh_seconds and HAS_AUTOREFRESH:
    st_autorefresh(interval=refresh_seconds * 1000, key="auto_refresh_key")

if st.sidebar.checkbox("DEBUG KEYS", value=False):
    st.sidebar.write({
        "TWELVE": bool(TWELVE_API_KEY),
        "FINNHUB": bool(FINNHUB_API_KEY),
        "ALPHAVANTAGE": bool(ALPHAVANTAGE_API_KEY),
        "POLYGON": bool(POLYGON_API_KEY),
    })

# =========================================================
# LOAD DATA
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

# Benchmark
benchmark_series = pd.Series(dtype=float)
if benchmark_ticker:
    benchmark_series = fetch_benchmark_series(benchmark_ticker, history_period, use_auto_adjust)
    benchmark_series = benchmark_series.dropna()
    benchmark_series = filter_period_series(benchmark_series, history_period)

# Precompute metrics
perf_1m = rolling_return(prices, 21)
perf_3m = rolling_return(prices, 63)
perf_6m = rolling_return(prices, 126)
perf_1y = calendar_return_years(prices, years=1)
vol = annualized_vol(prices)
mdd = max_drawdown(prices)

table_base = fund.copy()
table_base["Perf 1M"] = perf_1m
table_base["Perf 3M"] = perf_3m
table_base["Perf 6M"] = perf_6m
table_base["Perf 1Y"] = perf_1y
table_base["Vol annualisée"] = vol
table_base["Max Drawdown"] = mdd

pe = safe_numeric(table_base, "P/E (trailing)")
pb = safe_numeric(table_base, "P/B")
roe = safe_numeric(table_base, "ROE")
margin = safe_numeric(table_base, "Marge nette")
de = safe_numeric(table_base, "Dette/Capitaux")
mom6 = safe_numeric(table_base, "Perf 6M")
mom1y = safe_numeric(table_base, "Perf 1Y")
v = safe_numeric(table_base, "Vol annualisée")
dd = safe_numeric(table_base, "Max Drawdown")

value_score = (-zscore(pe).fillna(0) + -zscore(pb).fillna(0)) / 2
quality_score = (zscore(roe).fillna(0) + zscore(margin).fillna(0) + -zscore(de).fillna(0)) / 3
momentum_score = (zscore(mom6).fillna(0) + zscore(mom1y).fillna(0)) / 2
risk_score = (-zscore(v).fillna(0) + zscore(dd).fillna(0)) / 2

table_base["Score Value"] = value_score
table_base["Score Quality"] = quality_score
table_base["Score Momentum"] = momentum_score
table_base["Score Risk"] = risk_score

table_base["Score Global"] = (
    0.28 * table_base["Score Value"] +
    0.30 * table_base["Score Quality"] +
    0.27 * table_base["Score Momentum"] +
    0.15 * table_base["Score Risk"]
)

ranked_all = table_base.copy()
score_min = ranked_all["Score Global"].min()
score_max = ranked_all["Score Global"].max()

if pd.isna(score_min) or pd.isna(score_max) or score_min == score_max:
    ranked_all["Fantazia Score (%)"] = 50.0
else:
    ranked_all["Fantazia Score (%)"] = (
        (ranked_all["Score Global"] - score_min) / (score_max - score_min) * 100.0
    )

# Surperformance vs benchmark (1Y) si disponible
if benchmark_series is not None and not benchmark_series.empty:
    bm_df = pd.DataFrame({"BM": benchmark_series})
    bm_1y = calendar_return_years(bm_df, years=1)
    bm_1y_val = bm_1y.get("BM", np.nan)
    if not pd.isna(bm_1y_val):
        ranked_all["Surperf 1Y vs BM (pts)"] = (ranked_all["Perf 1Y"] - bm_1y_val) * 100.0
    else:
        ranked_all["Surperf 1Y vs BM (pts)"] = np.nan
else:
    ranked_all["Surperf 1Y vs BM (pts)"] = np.nan


# =========================================================
# FAQ ASSISTANT
# =========================================================
def faq_answer(question: str) -> str:
    q = question.lower()
    lang = st.session_state.get("lang", "fr")

    def fr():
        if "fantazia" in q and "score" in q:
            return (
                "Le **Fantazia Score (%)** est une note de **0 à 100%** pour chaque action *dans le tableau affiché*.\n\n"
                "- **100%** = action la plus intéressante du panier actuel.\n"
                "- **0%** = action la moins intéressante.\n\n"
                "On combine 4 sous-scores :\n"
                "- **Value** : chère ou pas vs les autres (P/E, P/B).\n"
                "- **Quality** : qualité de la boîte (ROE, marge nette, dette).\n"
                "- **Momentum** : dynamique récente (Perf 6M + Perf 1Y).\n"
                "- **Risk** : propreté du parcours (volatilité, drawdown).\n\n"
                "Tu peux aussi activer le **Fantazia Score personnalisé** dans le Dashboard :\n"
                "tu choisis les poids Value / Quality / Momentum / Risk, et le classement s'adapte à tes préférences."
            )
        if "perso" in q and "score" in q or "personnalis" in q:
            return (
                "Le **Fantazia Score personnalisé** te permet de choisir toi-même les poids :\n"
                "- Value\n"
                "- Quality\n"
                "- Momentum\n"
                "- Risk\n\n"
                "Dans le Dashboard, ouvre **\"⚙️ Fantazia Score personnalisé\"** :\n"
                "- Active l'option,\n"
                "- Régle les 4 sliders,\n"
                "- Le tableau et le Top du classement s'adaptent à ce score perso.\n\n"
                "Le score officiel reste affiché pour comparaison."
            )
        if "alerte" in q or "alertes du jour" in q or "ruban" in q:
            return (
                "Les **alertes** te permettent de surveiller :\n\n"
                "- une **variation journalière en %** (par ex. ≤ -3%, ≥ +5%),\n"
                "- ou un **seuil de prix** (par ex. ≤ 200€, ≥ 300€).\n\n"
                "Configuration :\n"
                "- Dans le Dashboard, bloc **\"Configurer mes alertes\"**.\n"
                "- Alertes stockées par compte dans `alerts.json`.\n\n"
                "Affichage :\n"
                "- Le **ruban en haut** liste les alertes **déjà déclenchées**.\n"
                "- Le bloc **\"Alertes du jour\"** en-dessous les récapitule.\n"
                "- S'il n'y a rien, aucune condition n'a été atteinte."
            )
        if "simulateur" in q or "portefeuille" in q:
            return (
                "Le **simulateur** te permet de tester un portefeuille virtuel.\n\n"
                "- On prend le **prix au début de la période** comme prix d'entrée.\n"
                "- Tu définis un **capital initial** et des **poids par action** (égaux ou custom).\n"
                "- On calcule combien d'actions tu aurais acheté, puis la **valeur actuelle** avec le dernier prix.\n\n"
                "Résultat :\n"
                "- Valeur actuelle du portefeuille,\n"
                "- Gain/perte totale en € et en %, \n"
                "- Détail par ligne.\n\n"
                "C'est une **simulation** (ça ne lit pas ton vrai compte broker)."
            )
        if "heatmap" in q or "carte" in q:
            return (
                "La **heatmap des performances** montre l'évolution en % par horizon : 1M, 3M, 6M, 1Y.\n\n"
                "- Chaque **ligne** = une action.\n"
                "- Chaque **colonne** = un horizon.\n"
                "- Couleur **verte** = performance positive,\n"
                "- Couleur **rouge** = performance négative.\n\n"
                "Plus la couleur est intense, plus le mouvement est fort."
            )
        if "corrélat" in q or "correlation" in q:
            return (
                "Le bloc **Corrélation des rendements** calcule la **corrélation** entre les actions du panier\n"
                "à partir des rendements journaliers.\n\n"
                "- **1** = bougent quasiment toujours ensemble,\n"
                "- **0** = pas de lien clair,\n"
                "- **-1** = bougent plutôt en sens opposé.\n\n"
                "La heatmap de corrélation te montre quelles actions sont des \"clones\" entre elles, "
                "et lesquelles diversifient davantage ton panier."
            )
        if "benchmark" in q or "indice" in q:
            return (
                "Le **benchmark** te permet de comparer ton panier à un indice (S&P500, Nasdaq, CAC40, etc.).\n\n"
                "- Dans la barre de gauche, choisis un indice dans **\"Benchmark (indice de référence)\"**.\n"
                "- Les graphiques base 100 peuvent inclure l'indice.\n"
                "- Le tableau calcule aussi la **surperformance 1Y vs benchmark** (en points de pourcentage), "
                "si l'historique est suffisant."
            )
        if "note perso" in q or "note personnelle" in q or "personal note" in q:
            return (
                "Dans **📄 Fiche action**, tu peux saisir une **note personnelle** pour chaque ticker.\n"
                "- Les notes sont stockées par compte dans `notes.json`.\n"
                "- Elles ne sont visibles que par toi.\n"
                "- Tu peux t'en servir pour noter tes idées, zones d'entrée, remarques, etc."
            )
        if "52" in q and "semaine" in q:
            return (
                "La **barre 52 semaines** montre où se situe le prix actuel entre le plus bas et le plus haut 52 semaines.\n\n"
                "- À gauche : plus bas 52w,\n"
                "- À droite : plus haut 52w,\n"
                "- Le curseur indique le **prix actuel**.\n\n"
                "Si le curseur est tout à droite → proche de son plus haut 52 semaines.\n"
                "S'il est à gauche → encore loin de son plus haut."
            )
        if "dashboard" in q or "tableau de bord" in q:
            return (
                "Le **Dashboard** est la vue principale :\n\n"
                "- Ruban + **Alertes du jour**,\n"
                "- Tableau des **sources historiques**, prix actuels,\n"
                "- Graphiques (base 100, prix réel, spread, benchmark),\n"
                "- **Top du classement** (Fantazia Score),\n"
                "- Tableau détaillé (scores, perfs, risques),\n"
                "- Heatmap performances,\n"
                "- News suivies.\n"
            )
        if "news" in q or "abonn" in q:
            return (
                "Tu peux t'abonner aux news d'une action dans **📄 Fiche action** :\n"
                "- coche *\"Suivre les news de TICKER\"*.\n"
                "- Tes abonnements sont liés à ton compte.\n"
                "- Dans le Dashboard, bloc **\"Mes news suivies\"** affiche les dernières news (fenêtre de quelques jours)."
            )
        if "watchlist" in q or "liste" in q:
            return (
                "Les **watchlists** sont des listes d'actions personnalisées.\n\n"
                "- Onglet **⭐ Watchlists** → créer, enregistrer, supprimer,\n"
                "- Stockées par **compte utilisateur** dans `watchlists.json`.\n"
                "- Chaque compte a ses propres listes."
            )
        if "langue" in q or "anglais" in q or "english" in q:
            return (
                "Tu peux changer la **langue de l'interface** en haut de la barre de gauche :\n\n"
                "- `Language / Langue` → FR ou EN.\n"
                "- Les labels, titres, textes principaux s'adaptent.\n"
                "- Les données (prix, ratios) restent identiques."
            )
        return (
            "Je suis l'assistant intégré de **Fantazia Finance**.\n\n"
            "Je peux t'expliquer :\n"
            "- le **Fantazia Score (%)** (officiel + personnalisé),\n"
            "- le Dashboard (graphiques, heatmap, corrélation, benchmark),\n"
            "- les **alertes** (ruban + Alertes du jour),\n"
            "- le **simulateur de portefeuille**, \n"
            "- les **watchlists**, les **notes perso** et les **news suivies**, \n"
            "- la 52w range, les sources de données (Yahoo, Twelve, Finnhub, Polygon).\n\n"
            "Pose ta question le plus clairement possible, par exemple :\n"
            "- \"Explique-moi le Fantazia Score personnalisé\"\n"
            "- \"Comment lire la corrélation ?\"\n"
            "- \"A quoi sert le benchmark ?\""
        )

    def en():
        if "fantazia" in q and "score" in q:
            return (
                "The **Fantazia Score (%)** is a **0–100%** score for each stock *within the displayed basket*.\n\n"
                "- **100%** = most interesting stock in the basket.\n"
                "- **0%** = least interesting.\n\n"
                "It combines 4 sub-scores:\n"
                "- **Value**: cheap or expensive vs others (P/E, P/B).\n"
                "- **Quality**: company quality (ROE, net margin, debt).\n"
                "- **Momentum**: recent trend (6M + 1Y performance).\n"
                "- **Risk**: smoothness of the path (volatility, drawdown).\n\n"
                "You can also enable the **Custom Fantazia Score** in the Dashboard:\n"
                "you choose the weights for Value / Quality / Momentum / Risk, and the ranking adapts."
            )
        if "custom" in q and "score" in q:
            return (
                "The **Custom Fantazia Score** lets you choose your own weights:\n"
                "- Value\n"
                "- Quality\n"
                "- Momentum\n"
                "- Risk\n\n"
                "In the Dashboard, open **\"⚙️ Custom Fantazia Score\"**:\n"
                "- Enable it,\n"
                "- Tune the 4 sliders,\n"
                "- The table and the ranking top will use your custom score.\n\n"
                "The official score remains visible for comparison."
            )
        if "alert" in q or "alerts of the day" in q or "ribbon" in q:
            return (
                "**Alerts** let you monitor:\n\n"
                "- a **daily % move** (e.g. ≤ -3%, ≥ +5%),\n"
                "- or a **price threshold** (e.g. ≤ 200, ≥ 300).\n\n"
                "Configured in the Dashboard, under **\"Configure my alerts\"**.\n"
                "- Alerts are stored per account in `alerts.json`.\n\n"
                "Display:\n"
                "- The **top ribbon** lists **triggered alerts**.\n"
                "- The **\"Alerts of the day\"** block shows the same list.\n"
                "- If it's empty, no condition has been hit."
            )
        if "simulator" in q or "portfolio" in q:
            return (
                "The **simulator** lets you test a virtual portfolio.\n\n"
                "- Uses the **first price in the loaded period** as entry.\n"
                "- You set an **initial capital** and weights (equal or custom).\n"
                "- It computes how many shares you would buy and the **current value** using last prices.\n\n"
                "You get:\n"
                "- current portfolio value,\n"
                "- total P&L in € and %, \n"
                "- per-line details.\n\n"
                "It's a **simulation**, it does not read your real broker account."
            )
        if "heatmap" in q or "map" in q:
            return (
                "The **performance heatmap** shows % moves per horizon: 1M, 3M, 6M, 1Y.\n\n"
                "- Each **row** = a stock,\n"
                "- Each **column** = a timeframe,\n"
                "- **Green** = positive performance,\n"
                "- **Red** = negative performance,\n"
                "- Stronger color = stronger move."
            )
        if "correlation" in q or "corr" in q:
            return (
                "The **Correlation of returns** block computes **correlation** between the basket's stocks\n"
                "using daily returns.\n\n"
                "- **1** = they almost always move together,\n"
                "- **0** = no clear link,\n"
                "- **-1** = mostly opposite moves.\n\n"
                "The correlation heatmap helps you see \"clones\" vs diversification within your basket."
            )
        if "benchmark" in q or "index" in q:
            return (
                "The **benchmark** lets you compare your basket to an index (S&P500, Nasdaq, CAC40, etc.).\n\n"
                "- In the left sidebar, pick an index in **\"Benchmark (reference index)\"**.\n"
                "- Base 100 charts can include the index.\n"
                "- The table also computes **1Y outperformance vs benchmark** (in percentage points), "
                "if there is enough data."
            )
        if "note" in q:
            return (
                "In **📄 Stock sheet**, you can write a **personal note** for each ticker.\n"
                "- Notes are stored per account in `notes.json`.\n"
                "- They are visible only to you.\n"
                "- Useful to track ideas, zones of interest, comments, etc."
            )
        if "52" in q and "week" in q:
            return (
                "The **52-week range bar** shows where the current price stands between the 52-week low and high.\n\n"
                "- Left: 52w low,\n"
                "- Right: 52w high,\n"
                "- The marker indicates the **current price**.\n\n"
                "If the marker is on the right → close to 52w high.\n"
                "If it's on the left → still far from the high."
            )
        if "dashboard" in q:
            return (
                "The **Dashboard** is the main view:\n\n"
                "- Top ribbon + **Alerts of the day**, \n"
                "- **Sources** table, current prices,\n"
                "- Charts (base 100, real price, spread, benchmark),\n"
                "- **Ranking top** (Fantazia Score),\n"
                "- Full table (scores, perfs, risk),\n"
                "- Performance heatmap,\n"
                "- Followed news.\n"
            )
        if "news" in q or "subscribe" in q:
            return (
                "You can subscribe to stock news in **📄 Stock sheet**:\n"
                "- check *\"Follow news of TICKER\"*.\n"
                "- Subscriptions are linked to your account.\n"
                "- The Dashboard **\"My followed news\"** block shows recent news over the last days."
            )
        if "watchlist" in q:
            return (
                "**Watchlists** are your custom stock lists.\n\n"
                "- In **⭐ Watchlists**, you can create, save, delete them,\n"
                "- Stored per **user account** in `watchlists.json`.\n"
                "- Each account has its own lists."
            )
        if "language" in q or "english" in q or "french" in q:
            return (
                "You can change the **interface language** at the top of the left sidebar:\n\n"
                "- `Language / Langue` → FR or EN.\n"
                "- Labels, headings and main messages switch.\n"
                "- Data (prices, ratios) remains unchanged."
            )
        return (
            "I am the built-in assistant of **Fantazia Finance**.\n\n"
            "I can explain:\n"
            "- the **Fantazia Score (%)** (official + custom),\n"
            "- the Dashboard (charts, heatmap, correlation, benchmark),\n"
            "- **alerts** (ribbon + Alerts of the day),\n"
            "- the **portfolio simulator**, \n"
            "- **watchlists**, **personal notes** and **followed news**, \n"
            "- the 52w range, data sources (Yahoo, Twelve, Finnhub, Polygon).\n\n"
            "Ask clearly, e.g.:\n"
            "- \"Explain the custom Fantazia Score\",\n"
            "- \"How to read correlation?\",\n"
            "- \"What is the benchmark used for?\""
        )

    return fr() if lang == "fr" else en()


# =========================================================
# TABS
# =========================================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    tr("tab_dashboard"),
    tr("tab_watchlists"),
    tr("tab_simulator"),
    tr("tab_stock"),
    tr("tab_help"),
    tr("tab_assistant"),
])


# =========================================================
# TAB 1 — DASHBOARD
# =========================================================
with tab1:
    # Realtime best-effort
    rt_data: Dict[str, Tuple[float, pd.Timestamp]] = {}
    if use_realtime and POLYGON_API_KEY:
        rt_data = fetch_realtime_polygon_batch(list(prices.columns))

    if st.button("🔄 Refresh prix (Polygon/Yahoo)"):
        if use_realtime and POLYGON_API_KEY:
            rt_data = fetch_realtime_polygon_batch(list(prices.columns))

    # Prix utilisés pour tout le reste
    prices_display = prices.copy()
    if rt_data:
        for t, (p, _) in rt_data.items():
            if t in prices_display.columns and not prices_display[t].dropna().empty:
                prices_display.loc[prices_display.index[-1], t] = p

    # Derniers prix & variations journalières
    latest_prices: Dict[str, float] = {}
    daily_changes: Dict[str, float] = {}
    for t in prices_display.columns:
        s = prices_display[t].dropna()
        if s.empty:
            continue
        latest_prices[t] = float(s.iloc[-1])
        if len(s) >= 2:
            daily_changes[t] = float((s.iloc[-1] / s.iloc[-2] - 1.0) * 100.0)
        else:
            daily_changes[t] = np.nan

    # Alertes
    user_alerts = load_alerts(CURRENT_USER)
    triggered_alerts = []

    for a in user_alerts:
        ticker = a.get("ticker", "").upper()
        kind = a.get("kind")
        cmp_op = a.get("cmp")
        thr = a.get("threshold", None)
        if not ticker or thr is None:
            continue
        if ticker not in latest_prices:
            continue

        desc = None
        if kind == "pct":
            change = daily_changes.get(ticker, np.nan)
            if pd.isna(change):
                continue
            if cmp_op == "le" and change <= thr:
                desc = f"variation {change:+.2f}% ≤ {thr:.2f}%"
            elif cmp_op == "ge" and change >= thr:
                desc = f"variation {change:+.2f}% ≥ {thr:.2f}%"
        elif kind == "price":
            cur_price = latest_prices.get(ticker, np.nan)
            if pd.isna(cur_price):
                continue
            if cmp_op == "le" and cur_price <= thr:
                desc = f"prix {cur_price:.2f} ≤ {thr:.2f}"
            elif cmp_op == "ge" and cur_price >= thr:
                desc = f"prix {cur_price:.2f} ≥ {thr:.2f}"

        if desc:
            triggered_alerts.append({"ticker": ticker, "desc": desc})

    # Ruban haut
    if triggered_alerts:
        messages = [
            f"[{a['ticker']}] {a['desc']}"
            for a in triggered_alerts
        ]
        text = "  •  ".join(html.escape(m) for m in messages)
        st.markdown(
            f"""
            <div class="ff-marquee">
              <div class="ff-marquee-inner">
                🔔 {text}
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.caption(tr("alerts_ribbon_info"))
    else:
        st.caption(tr("alerts_ribbon_info"))

    # Bloc Alertes du jour
    st.subheader(tr("alerts_of_day"))
    if triggered_alerts:
        for a in triggered_alerts:
            st.markdown(f"- **[{a['ticker']}]** {a['desc']}")
    else:
        st.write(tr("alerts_none"))

    # Configuration alertes
    with st.expander(tr("alerts_config_title")):
        st.caption(tr("alerts_config_caption"))
        if user_alerts:
            rows = []
            for idx, a in enumerate(user_alerts):
                ticker = a.get("ticker", "")
                kind = a.get("kind")
                cmp_op = a.get("cmp")
                thr = a.get("threshold", 0.0)
                if kind == "pct":
                    type_txt = tr("alerts_type_pct")
                    cond_txt = "≤" if cmp_op == "le" else "≥"
                    details = f"Var {cond_txt} {thr:.2f}%"
                else:
                    type_txt = tr("alerts_type_price")
                    cond_txt = "≤" if cmp_op == "le" else "≥"
                    details = f"Prix {cond_txt} {thr:.2f}"
                rows.append({
                    "ID": idx,
                    "Ticker": ticker,
                    "Type": type_txt,
                    "Condition": details,
                })
            st.markdown(tr("alerts_existing"))
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info(tr("alerts_none_for_user"))

        st.markdown(tr("alerts_new"))
        alert_ticker = st.selectbox(
            tr("alerts_ticker"),
            list(prices_display.columns),
            key="alert_ticker_select"
        )
        alert_mode = st.radio(
            tr("alerts_type"),
            [tr("alerts_type_pct"), tr("alerts_type_price")],
            horizontal=True,
            key="alert_mode_radio"
        )
        if alert_mode == tr("alerts_type_pct"):
            alert_cond = st.selectbox(
                tr("alerts_cond"),
                [tr("alerts_cond_drop"), tr("alerts_cond_rise")],
                key="alert_cond_pct"
            )
            kind = "pct"
        else:
            alert_cond = st.selectbox(
                tr("alerts_cond"),
                [tr("alerts_cond_price_le"), tr("alerts_cond_price_ge")],
                key="alert_cond_price"
            )
            kind = "price"
        cmp_op = "le" if ("≤" in alert_cond or "Drop" in alert_cond or "Price ≤" in alert_cond) else "ge"
        alert_thr = st.number_input(
            tr("alerts_threshold"),
            value=0.0,
            step=0.5,
            key="alert_thr_input"
        )
        if st.button(tr("alerts_save")):
            alerts = load_alerts(CURRENT_USER)
            new_alert = {
                "ticker": alert_ticker.upper(),
                "kind": kind,
                "cmp": cmp_op,
                "threshold": float(alert_thr),
            }
            alerts = [
                a for a in alerts
                if not (
                    a.get("ticker", "").upper() == new_alert["ticker"]
                    and a.get("kind") == new_alert["kind"]
                    and a.get("cmp") == new_alert["cmp"]
                )
            ]
            alerts.append(new_alert)
            save_alerts(CURRENT_USER, alerts)
            st.success(tr("alerts_saved"))
            rerun_app()

        if user_alerts:
            st.markdown(tr("alerts_delete_title"))
            del_idx = st.selectbox(
                tr("alerts_delete_select"),
                [a_idx for a_idx in range(len(user_alerts))],
                key="alert_delete_select"
            )
            if st.button(tr("alerts_delete_btn")):
                alerts = load_alerts(CURRENT_USER)
                if 0 <= del_idx < len(alerts):
                    alerts.pop(del_idx)
                    save_alerts(CURRENT_USER, alerts)
                    st.success(tr("alerts_deleted"))
                    rerun_app()

    st.markdown("---")

    # Sources historiques
    st.subheader(tr("sources_title"))
    src_df = pd.DataFrame(
        [{"Ticker": t, "Source historique": pretty_source_name(source_map.get(t, "none"))} for t in prices.columns]
    )
    try:
        styled_src = src_df.style.applymap(source_badge_style, subset=["Source historique"])
        st.dataframe(styled_src, use_container_width=True)
    except Exception:
        st.dataframe(src_df, use_container_width=True)

    # Prix actuels (avec devise)
    st.subheader(tr("prices_title"))
    cols_price = st.columns(min(4, len(prices_display.columns)))
    first_cols = list(prices_display.columns)[:len(cols_price)]
    for i, t in enumerate(first_cols):
        s = prices_display[t].dropna()
        if s.empty:
            continue
        last_close_series = prices[t].dropna()
        last_close = last_close_series.iloc[-1] if not last_close_series.empty else np.nan
        last_disp = s.iloc[-1]
        label = f"{t}"
        if t in rt_data:
            rt_price, _ = rt_data[t]
            delta_pct = (rt_price / last_close - 1.0) * 100 if last_close not in (0, np.nan) else None
            label = f"{t} (Polygon best effort)"
            cols_price[i].metric(
                label=label,
                value=format_price_with_currency(t, rt_price),
                delta=f"{delta_pct:.2f}% vs close" if delta_pct is not None else None
            )
        else:
            cols_price[i].metric(
                label=f"{t} (Yahoo)",
                value=format_price_with_currency(t, last_disp)
            )

    if len(prices_display.columns) > len(cols_price):
        with st.expander("Voir tous les prix actuels"):
            grid_cols = st.columns(4)
            for j, t in enumerate(list(prices_display.columns)):
                c = grid_cols[j % 4]
                s = prices_display[t].dropna()
                if s.empty:
                    continue
                last_close_series = prices[t].dropna()
                last_close = last_close_series.iloc[-1] if not last_close_series.empty else np.nan
                last_disp = s.iloc[-1]
                if t in rt_data:
                    rt_price, _ = rt_data[t]
                    delta_pct = (rt_price / last_close - 1.0) * 100 if last_close not in (0, np.nan) else None
                    c.metric(
                        label=f"{t} (Polygon)",
                        value=format_price_with_currency(t, rt_price),
                        delta=f"{delta_pct:.2f}% vs close" if delta_pct is not None else None
                    )
                else:
                    c.metric(
                        label=f"{t} (Yahoo)",
                        value=format_price_with_currency(t, last_disp)
                    )

        # Graphiques
    st.subheader(tr("graph_title"))

    # Boutons rapides d'horizon d'affichage (sur l'historique déjà chargé)
    view_range = st.radio(
        "Horizon d'affichage (sur la période chargée)",
        ["1M", "3M", "1Y"],
        horizontal=True,
        index=0
    )

    def filter_for_view(df: pd.DataFrame, view: str) -> pd.DataFrame:
        mapping = {
            "1M": "1mo",
            "3M": "3mo",
            "1Y": "1y",
        }
        per = mapping.get(view, None)
        if per is None:
            return df
        return filter_period_df(df, per)

    prices_for_graphs = filter_for_view(prices_display, view_range)

    graph_mode = st.radio(
        "",
        [tr("graph_mode_base100"), tr("graph_mode_price"), tr("graph_mode_spread")],
        horizontal=True
    )

    if prices_for_graphs.empty:
        st.warning("Pas assez de données pour afficher les graphiques sur cet horizon.")
    else:
        if graph_mode == tr("graph_mode_base100"):
            # Base 100 par ticker : on prend le premier prix non-NaN de chaque série
            def _base100(s: pd.Series) -> pd.Series:
                s_clean = s.dropna()
                if s_clean.empty:
                    return s
                return s / s_clean.iloc[0] * 100.0

            norm = prices_for_graphs.apply(_base100)

            # On ajoute le benchmark éventuel, en base 100 aussi
            if benchmark_series is not None and not benchmark_series.empty:
                bm_filtered = filter_for_view(benchmark_series.to_frame("BM"), view_range)["BM"]
                bm_filtered = bm_filtered.dropna()
                if not bm_filtered.empty:
                    bm_norm = bm_filtered / bm_filtered.iloc[0] * 100.0
                    norm = norm.join(bm_norm.rename("BENCHMARK"), how="outer")

            fig = px.line(norm, title=f"Performance normalisée (base 100) — {sector_label}")
            st.plotly_chart(fig, use_container_width=True)

        elif graph_mode == tr("graph_mode_price"):
            selected = st.selectbox(
                tr("graph_choose_stock"),
                list(prices_for_graphs.columns),
                key="price_graph_select"
            )
            price_one = prices_for_graphs[[selected]].dropna()
            log_scale = st.checkbox(tr("graph_log_scale"), value=False)
            fig = px.line(price_one, title=f"{selected} — Prix sur la période")
            fig.update_yaxes(title="Prix", type="log" if log_scale else "linear")
            fig.update_xaxes(title="Date")
            st.plotly_chart(fig, use_container_width=True)

        else:
            col_sp1, col_sp2 = st.columns(2)
            with col_sp1:
                t1 = st.selectbox("Action A (numérateur)", list(prices_for_graphs.columns), index=0)
            with col_sp2:
                t2 = st.selectbox(
                    "Action B (dénominateur)",
                    list(prices_for_graphs.columns),
                    index=min(1, len(prices_for_graphs.columns) - 1)
                )
            if t1 == t2:
                st.info(tr("graph_spread_info"))
            else:
                sub = prices_for_graphs[[t1, t2]].dropna(how="any")
                if sub.empty:
                    st.warning("Pas assez de données pour ce spread.")
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
                    with st.expander("ℹ️ Spread"):
                        st.markdown(tr("graph_spread_how").format(a=t1, b=t2))


    # Top classement
    st.subheader(tr("scores_top_title"))
    df_scores = ranked_all.copy()

    # Score personnalisé
    with st.expander(tr("custom_score_title")):
        st.caption(tr("custom_score_info"))
        custom_enabled = st.checkbox(
            tr("custom_score_enable"),
            value=st.session_state.get("fantazia_custom_enabled", False)
        )
        st.session_state["fantazia_custom_enabled"] = custom_enabled
        if custom_enabled:
            colw1, colw2, colw3, colw4 = st.columns(4)
            with colw1:
                wv = st.slider("Poids Value", 0, 100, st.session_state.get("w_val", 28))
            with colw2:
                wq = st.slider("Poids Quality", 0, 100, st.session_state.get("w_qual", 30))
            with colw3:
                wm = st.slider("Poids Momentum", 0, 100, st.session_state.get("w_mom", 27))
            with colw4:
                wr = st.slider("Poids Risk", 0, 100, st.session_state.get("w_risk", 15))
            st.session_state["w_val"] = wv
            st.session_state["w_qual"] = wq
            st.session_state["w_mom"] = wm
            st.session_state["w_risk"] = wr
            total_w = wv + wq + wm + wr
            if total_w <= 0:
                wv_norm, wq_norm, wm_norm, wr_norm = 0.28, 0.30, 0.27, 0.15
            else:
                wv_norm = wv / total_w
                wq_norm = wq / total_w
                wm_norm = wm / total_w
                wr_norm = wr / total_w
            alt_global = (
                wv_norm * df_scores["Score Value"] +
                wq_norm * df_scores["Score Quality"] +
                wm_norm * df_scores["Score Momentum"] +
                wr_norm * df_scores["Score Risk"]
            )
            alt_min = alt_global.min()
            alt_max = alt_global.max()
            if pd.isna(alt_min) or pd.isna(alt_max) or alt_min == alt_max:
                alt_pct = pd.Series(50.0, index=alt_global.index)
            else:
                alt_pct = (alt_global - alt_min) / (alt_max - alt_min) * 100.0
            df_scores["Score Global Perso"] = alt_global
            df_scores["Fantazia Perso (%)"] = alt_pct
        else:
            wv_norm = wq_norm = wm_norm = wr_norm = None

    score_col_official = "Fantazia Score (%)"
    score_col_custom = "Fantazia Perso (%)"
    if st.session_state.get("fantazia_custom_enabled", False) and score_col_custom in df_scores.columns:
        score_col_current = score_col_custom
    else:
        score_col_current = score_col_official

    ranked_view = df_scores.sort_values(score_col_current, ascending=False)

    cols_top = st.columns(3)
    for i in range(min(3, len(ranked_view))):
        t = ranked_view.index[i]
        name = ranked_view.loc[t, "Nom"] if "Nom" in ranked_view.columns else ""
        fscore = ranked_view.loc[t, score_col_current]
        p1y_val = ranked_view.loc[t, "Perf 1Y"]
        if fscore >= 80:
            label_txt = "⭐ Très intéressante" if st.session_state["lang"] == "fr" else "⭐ Very interesting"
        elif fscore >= 60:
            label_txt = "🟢 Intéressante" if st.session_state["lang"] == "fr" else "🟢 Interesting"
        elif fscore >= 40:
            label_txt = "🟡 Neutre" if st.session_state["lang"] == "fr" else "🟡 Neutral"
        else:
            label_txt = "🔴 Faible intérêt" if st.session_state["lang"] == "fr" else "🔴 Low interest"
        if pd.notna(p1y_val):
            delta_txt = f"{label_txt} · {p1y_val*100:.1f}% 1Y"
        else:
            delta_txt = label_txt
        with cols_top[i]:
            st.metric(
                label=f"{t} {('- ' + name) if name else ''}",
                value=f"{fscore:.1f} %",
                delta=delta_txt
            )
    # Top défensif / Top risqué
    lang_ui = st.session_state.get("lang", "fr")

    if lang_ui == "fr":
        st.markdown("### 🛡️ Actions défensives / ⚡ Actions risquées")
    else:
        st.markdown("### 🛡️ Defensive stocks / ⚡ Risky stocks")

    col_vol = "Vol annualisée" if "Vol annualisée" in df_scores.columns else None
    col_dd = "Max Drawdown" if "Max Drawdown" in df_scores.columns else None

    def format_line(ticker, row):
        name = row.get("Nom", "")
        vol = row.get("Vol annualisée", np.nan)
        dd = row.get("Max Drawdown", np.nan)
        p1y = row.get("Perf 1Y", np.nan)

        parts = [f"**{ticker}**"]
        if name:
            parts.append(f"— {name}")
        if not pd.isna(vol):
            parts.append(f"· Vol : {vol*100:.1f} %")
        if not pd.isna(dd):
            parts.append(f"· DD : {dd*100:.1f} %")
        if not pd.isna(p1y):
            parts.append(f"· 1Y : {p1y*100:+.1f} %")
        return " ".join(parts)

    if col_vol or col_dd:
        # Défensives : faible volatilité (et drawdown moins violent si possible)
        df_def = df_scores.copy()
        if col_vol:
            df_def = df_def.dropna(subset=[col_vol]).sort_values(col_vol, ascending=True)
        elif col_dd:
            df_def = df_def.dropna(subset=[col_dd]).sort_values(col_dd, ascending=False)
        top_def = df_def.head(3)

        # Risquées : forte volatilité (ou drawdown très négatif)
        df_risk = df_scores.copy()
        if col_vol:
            df_risk = df_risk.dropna(subset=[col_vol]).sort_values(col_vol, ascending=False)
        elif col_dd:
            df_risk = df_risk.dropna(subset=[col_dd]).sort_values(col_dd, ascending=True)
        top_risk = df_risk.head(3)

        c_def, c_risk = st.columns(2)

        with c_def:
            if lang_ui == "fr":
                st.markdown("**🛡️ Plus défensives**")
                if top_def.empty:
                    st.write("Aucune donnée suffisante pour identifier les actions défensives.")
                else:
                    for t, row in top_def.iterrows():
                        st.markdown("- " + format_line(t, row))
                    st.caption(
                        "Profil plus calme : volatilité plus faible et drawdown historiquement moins violent."
                    )
            else:
                st.markdown("**🛡️ Most defensive**")
                if top_def.empty:
                    st.write("Not enough data to identify defensive stocks.")
                else:
                    for t, row in top_def.iterrows():
                        st.markdown("- " + format_line(t, row))
                    st.caption(
                        "Calmer profile: lower volatility and historically softer drawdowns."
                    )

        with c_risk:
            if lang_ui == "fr":
                st.markdown("**⚡ Plus risquées**")
                if top_risk.empty:
                    st.write("Aucune donnée suffisante pour identifier les actions risquées.")
                else:
                    for t, row in top_risk.iterrows():
                        st.markdown("- " + format_line(t, row))
                    st.caption(
                        "Profil plus spéculatif : volatilité plus élevée et drawdown plus profond."
                    )
            else:
                st.markdown("**⚡ Riskiest**")
                if top_risk.empty:
                    st.write("Not enough data to identify risky stocks.")
                else:
                    for t, row in top_risk.iterrows():
                        st.markdown("- " + format_line(t, row))
                    st.caption(
                        "More speculative profile: higher volatility and deeper drawdowns."
                    )
    else:
        # Si jamais les colonnes de risque n'existent pas, on ne casse rien
        if lang_ui == "fr":
            st.caption("Pas assez de données de risque (volatilité / drawdown) pour classer les actions.")
        else:
            st.caption("Not enough risk data (volatility / drawdown) to rank the stocks.")

    # Gagnant / perdant du jour dans le panier
    lang_ui = st.session_state.get("lang", "fr")

    if lang_ui == "fr":
        st.markdown("### 🔍 Gagnant / perdant du jour")
    else:
        st.markdown("### 🔍 Biggest winner / loser today")

    # daily_changes a été calculé plus haut dans le Dashboard
    ch_series = pd.Series(daily_changes).dropna()

    # On garde uniquement les tickers présents dans df_scores (sécurité)
    if not df_scores.empty:
        common_idx = df_scores.index.intersection(ch_series.index)
        ch_series = ch_series.loc[common_idx]

    if ch_series.empty:
        if lang_ui == "fr":
            st.caption("Pas assez de données intraday pour afficher le gagnant et le perdant du jour.")
        else:
            st.caption("Not enough intraday data to show today's winner and loser.")
    else:
        # Cas où il n'y a qu'une seule action avec variation du jour
        if len(ch_series) == 1:
            only_ticker = ch_series.index[0]
            only_val = ch_series.iloc[0]
            row = df_scores.loc[only_ticker] if only_ticker in df_scores.index else {}
            name = row.get("Nom", "")
            p1y = row.get("Perf 1Y", np.nan)

            label = "🚀 Gagnant du jour" if lang_ui == "fr" else "🚀 Today's move"
            if only_val < 0:
                label = "🩸 Perdant du jour" if lang_ui == "fr" else "🩸 Today's move"

            st.metric(
                label=label,
                value=only_ticker,
                delta=f"{only_val:+.2f} %"
            )

            # Petit récap en dessous
            parts = []
            if name:
                parts.append(name)
            if not pd.isna(p1y):
                if lang_ui == "fr":
                    parts.append(f"Perf 1 an : {p1y*100:+.1f} %")
                else:
                    parts.append(f"1Y perf: {p1y*100:+.1f} %")
            if parts:
                st.caption(" · ".join(parts))
        else:
            # Plus gros gagnant / plus gros perdant
            top_up_ticker = ch_series.idxmax()
            top_up_val = ch_series.loc[top_up_ticker]

            top_down_ticker = ch_series.idxmin()
            top_down_val = ch_series.loc[top_down_ticker]

            row_up = df_scores.loc[top_up_ticker] if top_up_ticker in df_scores.index else {}
            row_down = df_scores.loc[top_down_ticker] if top_down_ticker in df_scores.index else {}

            name_up = row_up.get("Nom", "")
            p1y_up = row_up.get("Perf 1Y", np.nan)

            name_down = row_down.get("Nom", "")
            p1y_down = row_down.get("Perf 1Y", np.nan)

            col_up, col_down = st.columns(2)

            with col_up:
                label_up = "🚀 Plus grosse hausse du jour" if lang_ui == "fr" else "🚀 Biggest gainer today"
                st.metric(
                    label=label_up,
                    value=top_up_ticker,
                    delta=f"{top_up_val:+.2f} %"
                )
                parts_up = []
                if name_up:
                    parts_up.append(name_up)
                if not pd.isna(p1y_up):
                    if lang_ui == "fr":
                        parts_up.append(f"Perf 1 an : {p1y_up*100:+.1f} %")
                    else:
                        parts_up.append(f"1Y perf: {p1y_up*100:+.1f} %")
                if parts_up:
                    st.caption(" · ".join(parts_up))

            with col_down:
                label_down = "🩸 Plus grosse baisse du jour" if lang_ui == "fr" else "🩸 Biggest loser today"
                st.metric(
                    label=label_down,
                    value=top_down_ticker,
                    delta=f"{top_down_val:+.2f} %"
                )
                parts_down = []
                if name_down:
                    parts_down.append(name_down)
                if not pd.isna(p1y_down):
                    if lang_ui == "fr":
                        parts_down.append(f"Perf 1 an : {p1y_down*100:+.1f} %")
                    else:
                        parts_down.append(f"1Y perf: {p1y_down*100:+.1f} %")
                if parts_down:
                    st.caption(" · ".join(parts_down))

            # Comparaison complète
    st.subheader(tr("table_title"))

    with st.expander(tr("table_filters")):
        min_fscore = st.slider(
            tr("table_min_score"),
            min_value=0,
            max_value=100,
            value=0,
            step=5
        )
        hide_neg_1y = st.checkbox(tr("table_hide_neg1y"), value=False)
        sort_options = [
            "Fantazia Score (%)",
            "Fantazia Perso (%)",
            "Score Global interne",
            "Score Global perso",
            "Perf 1Y",
            "Perf 6M",
            "Perf 3M",
            "Perf 1M",
            "P/E (trailing)",
            "P/B",
            "Surperf 1Y vs BM (pts)",
        ]
        sort_choice = st.selectbox(tr("table_sort_by"), sort_options, index=0)
        sort_order = st.radio(
            "",
            [tr("table_sort_desc"), tr("table_sort_asc")],
            horizontal=True
        )

    table_mode = st.radio(
        tr("table_mode"),
        [tr("table_mode_simple"), tr("table_mode_advanced")],
        horizontal=True
    )

    df_base = df_scores.copy()

    # Filtres
    filter_col = score_col_current
    if filter_col in df_base.columns and min_fscore > 0:
        df_base = df_base[df_base[filter_col] >= min_fscore]
    if hide_neg_1y and "Perf 1Y" in df_base.columns:
        df_base = df_base[df_base["Perf 1Y"] >= 0]

    sort_col_map = {
        "Fantazia Score (%)": "Fantazia Score (%)",
        "Fantazia Perso (%)": "Fantazia Perso (%)",
        "Score Global interne": "Score Global",
        "Score Global perso": "Score Global Perso",
        "Perf 1Y": "Perf 1Y",
        "Perf 6M": "Perf 6M",
        "Perf 3M": "Perf 3M",
        "Perf 1M": "Perf 1M",
        "P/E (trailing)": "P/E (trailing)",
        "P/B": "P/B",
        "Surperf 1Y vs BM (pts)": "Surperf 1Y vs BM (pts)",
    }
    sort_col = sort_col_map.get(sort_choice, filter_col)
    ascending = (sort_order == tr("table_sort_asc"))
    if sort_col in df_base.columns:
        df_base = df_base.sort_values(sort_col, ascending=ascending)

    base_cols = [
        "Nom", "Secteur (API)", "Industrie (API)", "Pays", "Devise",
        "Market Cap (Mds)",
        "P/E (trailing)", "P/B",
        "ROE", "Marge nette", "Dette/Capitaux", "Div. Yield",
        "Perf 1M", "Perf 3M", "Perf 6M", "Perf 1Y",
        "Vol annualisée", "Max Drawdown",
        "Score Value", "Score Quality", "Score Momentum", "Score Risk",
        "Score Global", "Score Global Perso",
        "Fantazia Score (%)", "Fantazia Perso (%)",
        "Surperf 1Y vs BM (pts)",
    ]

    simple_cols = [
        "Nom", "Pays", "Devise", "Market Cap (Mds)",
        "Perf 1M", "Perf 3M", "Perf 1Y",
        "P/E (trailing)", "Div. Yield",
        "Fantazia Score (%)", "Fantazia Perso (%)",
        "Surperf 1Y vs BM (pts)",
    ]

    if table_mode == tr("table_mode_simple"):
        cols_to_use = [c for c in simple_cols if c in df_base.columns]
    else:
        cols_to_use = [c for c in base_cols if c in df_base.columns]

    display_df = df_base.reindex(columns=cols_to_use)
    display_df.insert(
        0,
        "Source historique",
        [pretty_source_name(source_map.get(t, "none")) for t in display_df.index]
    )

    # Colonnes numériques pour formatage
    num_cols = display_df.select_dtypes(include=[np.number, "float64", "int64"]).columns

    perf_cols_subset = [c for c in ["Perf 1M", "Perf 3M", "Perf 6M", "Perf 1Y"] if c in display_df.columns]

    try:
        # 2 décimales pour toutes les colonnes numériques
        styled = display_df.style.format("{:.2f}", subset=num_cols)
        # Badge de la source
        styled = styled.applymap(source_badge_style, subset=["Source historique"])
        # Couleurs perf
        if perf_cols_subset:
            styled = styled.applymap(perf_color, subset=perf_cols_subset)
        # Couleurs scores
        if "Fantazia Score (%)" in display_df.columns:
            styled = styled.applymap(perf_color, subset=["Fantazia Score (%)"])
        if "Fantazia Perso (%)" in display_df.columns:
            styled = styled.applymap(perf_color, subset=["Fantazia Perso (%)"])
        st.dataframe(styled, use_container_width=True)
    except Exception:
        st.dataframe(display_df, use_container_width=True)

    st.caption(
        "ℹ️ Fantazia Score (%) : 0–100% dans ce panier (100 = meilleure action). "
        "Si le score perso est activé, les filtres utilisent la colonne personnalisée."
    )



    # Heatmap
    st.subheader(tr("heatmap_title"))
    heat = df_base[["Perf 1M", "Perf 3M", "Perf 6M", "Perf 1Y"]].copy()
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
    st.caption(tr("heatmap_legend"))

    # Corrélation
    st.subheader(tr("corr_title"))
    returns = prices_display.pct_change().dropna()
    if returns.shape[0] < 2:
        st.info("Pas assez de données pour calculer la corrélation.")
    else:
        corr = returns.corr()
        figc = px.imshow(
            corr,
            x=corr.columns,
            y=corr.index,
            color_continuous_scale="RdYlGn",
            zmin=-1,
            zmax=1,
            title="Corrélation des rendements journaliers"
        )
        figc.update_coloraxes(colorbar_title="Corr")
        st.plotly_chart(figc, use_container_width=True)
        st.caption(tr("corr_caption"))
        
    # Résumé "coach" du panier
    lang_ui = st.session_state.get("lang", "fr")

    if not df_scores.empty:
        n_stocks = len(df_scores)

        # Score moyen
        if score_col_current in df_scores.columns:
            score_mean = df_scores[score_col_current].mean()
        else:
            score_mean = np.nan

        # Perf 1Y moyenne
        if "Perf 1Y" in df_scores.columns:
            perf1y_mean = df_scores["Perf 1Y"].mean()
            nb_neg1y = int((df_scores["Perf 1Y"] < 0).sum())
        else:
            perf1y_mean = np.nan
            nb_neg1y = 0

        # Volatilité & drawdown moyens
        if "Vol annualisée" in df_scores.columns:
            vol_mean = df_scores["Vol annualisée"].mean()
        else:
            vol_mean = np.nan

        if "Max Drawdown" in df_scores.columns:
            dd_mean = df_scores["Max Drawdown"].mean()
        else:
            dd_mean = np.nan

        # Nombre d'actions avec bon score
        if score_col_current in df_scores.columns:
            nb_high = int((df_scores[score_col_current] >= 80).sum())
        else:
            nb_high = 0

        # Surperf moyenne vs benchmark (si dispo)
        if "Surperf 1Y vs BM (pts)" in df_scores.columns:
            surperf_mean = df_scores["Surperf 1Y vs BM (pts)"].mean()
        else:
            surperf_mean = np.nan

        # On formate les nombres proprement
        def fmt_pct(x):
            return f"{x*100:.1f} %" if not pd.isna(x) else "n/d"

        def fmt_pts(x):
            sign = "+" if x >= 0 else ""
            return f"{sign}{x:.1f} pts" if not pd.isna(x) else "n/d"

        if lang_ui == "fr":
            st.markdown("### 🧩 Résumé du panier")

            lignes = [
                f"- **Nombre d'actions dans le panier** : {n_stocks}",
            ]
            if not pd.isna(score_mean):
                lignes.append(f"- **Fantazia Score moyen** : {score_mean:.1f} %")
            if not pd.isna(perf1y_mean):
                lignes.append(f"- **Performance moyenne 1 an** : {perf1y_mean*100:+.1f} %")
            if not pd.isna(vol_mean):
                lignes.append(f"- **Volatilité annualisée moyenne** : {vol_mean*100:.1f} %")
            if not pd.isna(dd_mean):
                lignes.append(f"- **Max drawdown moyen** : {dd_mean*100:.1f} %")
            lignes.append(f"- **Actions avec Fantazia ≥ 80 %** : {nb_high}")
            if "Perf 1Y" in df_scores.columns:
                lignes.append(f"- **Actions avec performance 1 an négative** : {nb_neg1y}")
            if not pd.isna(surperf_mean):
                lignes.append(f"- **Surperformance 1 an moyenne vs benchmark** : {fmt_pts(surperf_mean)}")

            st.markdown("\n".join(lignes))
        else:
            st.markdown("### 🧩 Basket summary")

            lines_en = [
                f"- **Number of stocks in basket**: {n_stocks}",
            ]
            if not pd.isna(score_mean):
                lines_en.append(f"- **Average Fantazia Score**: {score_mean:.1f} %")
            if not pd.isna(perf1y_mean):
                lines_en.append(f"- **Average 1Y performance**: {perf1y_mean*100:+.1f} %")
            if not pd.isna(vol_mean):
                lines_en.append(f"- **Average annualized volatility**: {vol_mean*100:.1f} %")
            if not pd.isna(dd_mean):
                lines_en.append(f"- **Average max drawdown**: {dd_mean*100:.1f} %")
            lines_en.append(f"- **Stocks with Fantazia ≥ 80%**: {nb_high}")
            if "Perf 1Y" in df_scores.columns:
                lines_en.append(f"- **Stocks with negative 1Y performance**: {nb_neg1y}")
            if not pd.isna(surperf_mean):
                lines_en.append(f"- **Average 1Y outperformance vs benchmark**: {fmt_pts(surperf_mean)}")

            st.markdown("\n".join(lines_en))


    # Export CSV (table arrondie)
    csv = display_df.to_csv().encode("utf-8")
    st.download_button(
        tr("export_csv"),
        data=csv,
        file_name=f"comparateur_{sector_label.lower().replace(' ', '_')}.csv",
        mime="text/csv"
    )

    # Détails score
    with st.expander(tr("score_details_title")):
        st.markdown(
            "### Comment lire le Fantazia Score (%)\n\n"
            "- Le **Fantazia Score (%)** va de **0 à 100** pour chaque action.\n"
            "- **100%** = action la plus intéressante du panier actuel.\n"
            "- **0%** = action la moins intéressante.\n\n"
            "On calcule 4 sous-scores (en relatif au panier) :\n\n"
            "- **Score Value** : chère ou pas (P/E, P/B).\n"
            "- **Score Quality** : qualité (ROE, marge, dette/équité).\n"
            "- **Score Momentum** : dynamique (Perf 6M + 1Y).\n"
            "- **Score Risk** : parcours plus ou moins propre (volatilité, drawdown).\n\n"
            "Ensuite, on combine en un **Score Global interne**, puis on le transforme en **Fantazia Score (%)**.\n\n"
            "**Fantazia Score personnalisé** : en changeant les poids Value/Quality/Momentum/Risk, "
            "tu modifies la manière dont ces 4 blocs contribuent au score final."
        )

    # Notes techniques
    with st.expander(tr("tech_notes_title")):
        lines = [
            f"- Source historique choisie : **{price_source_mode}**",
            "- Fallback par action actif.",
            f"- Realtime Polygon (best effort) : **{'activé' if use_realtime else 'désactivé'}**",
            "- Perf 1M/3M/6M : approximation en séances.",
            "- Perf 1Y : calculée en calendrier (1 an réel).",
            f"- Période d'historique actuelle : **{history_period}**.",
        ]
        if benchmark_ticker:
            lines.append(f"- Benchmark sélectionné : **{benchmark_ticker}**")
        st.markdown("\n".join(lines))

    # News suivies
    st.markdown("---")
    st.subheader(tr("mynews_title"))
    if not FINNHUB_API_KEY:
        st.info(tr("mynews_no_key"))
    else:
        subs = load_news_subscriptions(CURRENT_USER)
        if not subs:
            st.info(tr("mynews_no_subs"))
        else:
            all_rows = []
            for t in subs:
                df_n = load_news_finnhub(t, days=5, max_items=5)
                if not df_n.empty:
                    df_n = df_n.copy()
                    df_n["Ticker"] = t
                    all_rows.append(df_n)
            if not all_rows:
                st.info(tr("mynews_none_recent"))
            else:
                news_all = pd.concat(all_rows, ignore_index=True)
                if "datetime" in news_all.columns:
                    news_all = news_all.sort_values("datetime", ascending=False)
                max_show = 15
                count = 0
                for _, row in news_all.iterrows():
                    if count >= max_show:
                        break
                    tck = row.get("Ticker", "")
                    dt = row.get("datetime", None)
                    src = row.get("source", "")
                    title = row.get("headline", "")
                    summary = row.get("summary", "")
                    url = row.get("url", "")
                    date_str = dt.strftime("%d/%m/%Y %H:%M") if isinstance(dt, pd.Timestamp) else ""
                    st.markdown(f"**[{tck}] {title}**")
                    meta_parts = []
                    if date_str:
                        meta_parts.append(date_str)
                    if src:
                        meta_parts.append(src)
                    if meta_parts:
                        st.caption(" · ".join(meta_parts))
                    if summary:
                        st.write(summary)
                    if url:
                        st.markdown(f"[Lire l'article]({url})")
                    st.markdown("---")
                    count += 1


# =========================================================
# TAB 2 — WATCHLISTS
# =========================================================
with tab2:
    st.subheader(tr("watchlists_title"))
    st.caption(tr("watchlists_caption").format(file=WATCHLIST_FILE, user=CURRENT_USER))

    watchlists = load_watchlists(CURRENT_USER)
    colA, colB = st.columns([1, 2])
    with colA:
        st.markdown(tr("watchlists_create"))
        new_name = st.text_input(tr("watchlists_name"), value="")
        new_tickers_txt = st.text_area(tr("watchlists_tickers"), value="", height=80)
        if st.button(tr("watchlists_save")):
            name = new_name.strip()
            if name:
                tick_list = parse_tickers(new_tickers_txt)
                watchlists[name] = tick_list
                save_watchlists(CURRENT_USER, watchlists)
                st.success(
                    tr("watchlists_saved").format(name=name, n=len(tick_list), user=CURRENT_USER)
                )
            else:
                st.warning("Donne un nom à la watchlist.")
    with colB:
        st.markdown(tr("watchlists_existing"))
        if not watchlists:
            st.info(tr("watchlists_none"))
        else:
            rows = [{"Watchlist": n, "Tickers": ", ".join(v)} for n, v in watchlists.items()]
            df_wl = pd.DataFrame(rows)
            st.dataframe(df_wl, use_container_width=True)
            st.markdown(tr("watchlists_delete_title"))
            del_name = st.selectbox(tr("watchlists_delete_select"), list(watchlists.keys()))
            if st.button(tr("watchlists_delete_btn")):
                watchlists.pop(del_name, None)
                save_watchlists(CURRENT_USER, watchlists)
                st.success(tr("watchlists_deleted").format(name=del_name, user=CURRENT_USER))

    st.divider()
    if watchlists:
        export_json = json.dumps(watchlists, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            tr("watchlists_export"),
            data=export_json,
            file_name=f"watchlists_{CURRENT_USER}.json",
            mime="application/json"
        )
    # ------------------------------------------------------
    # Centrale des notes / Notes hub
    # ------------------------------------------------------
    st.markdown("---")
    lang_ui = st.session_state.get("lang", "fr")
    title_notes = "📝 Centrale des notes" if lang_ui == "fr" else "📝 Notes hub"
    st.subheader(title_notes)

    notes_user = load_notes(CURRENT_USER)
    watchlists_all = load_watchlists(CURRENT_USER)

    if not notes_user:
        msg = (
            "Tu n'as encore écrit aucune note personnelle sur tes actions."
            if lang_ui == "fr"
            else "You haven't written any personal notes on your stocks yet."
        )
        st.info(msg)
    else:
        # Construire un tableau : Ticker / Watchlists / Note
        rows = []
        for t, note in notes_user.items():
            wl_for_t = []
            for wl_name, wl_tickers in watchlists_all.items():
                if t in wl_tickers:
                    wl_for_t.append(wl_name)
            rows.append({
                "Ticker": t,
                "Watchlists": ", ".join(wl_for_t) if wl_for_t else ("(aucune)" if lang_ui == "fr" else "(none)"),
                "Note": note,
            })

        df_notes = pd.DataFrame(rows)
        if not df_notes.empty:
            df_notes = df_notes.sort_values("Ticker")

        st.dataframe(df_notes, use_container_width=True)

        # Édition centralisée d'une note
        if lang_ui == "fr":
            st.markdown("### Modifier une note depuis la centrale")
            label_select = "Choisis un ticker"
            label_area = "Note pour {ticker}"
            label_button = "💾 Enregistrer la note"
            msg_saved = "Note mise à jour pour {ticker}."
        else:
            st.markdown("### Edit a note from the hub")
            label_select = "Choose a ticker"
            label_area = "Note for {ticker}"
            label_button = "💾 Save note"
            msg_saved = "Note updated for {ticker}."

        tickers_with_notes = sorted(notes_user.keys())
        selected_t = st.selectbox(
            label_select,
            tickers_with_notes,
            key="notes_central_ticker_select"
        )

        current_note = notes_user.get(selected_t, "")
        new_note_text = st.text_area(
            label_area.format(ticker=selected_t),
            value=current_note,
            height=150,
            key="notes_central_textarea"
        )

        if st.button(label_button, key="notes_central_save_button"):
            notes_user[selected_t] = new_note_text
            save_notes(CURRENT_USER, notes_user)
            st.success(msg_saved.format(ticker=selected_t))


# =========================================================
# TAB 3 — SIMULATEUR
# =========================================================
with tab3:
    st.subheader(tr("sim_title"))
    st.caption(tr("sim_caption"))
    if prices.shape[0] < 2:
        st.warning(tr("sim_not_enough"))
    else:
        start_date = prices.index[0]
        end_date = prices.index[-1]
        st.markdown(f"- Début historique : **{start_date.date()}**")
        st.markdown(f"- Fin historique : **{end_date.date()}**")
        capital = st.number_input(tr("sim_capital"), min_value=100.0, value=10000.0, step=500.0)
        mode_alloc = st.radio(
            tr("sim_alloc_mode"),
            [tr("sim_alloc_equal"), tr("sim_alloc_custom")],
            horizontal=True
        )
        tick_list = list(prices.columns)
        weights = {}
        if mode_alloc == tr("sim_alloc_equal"):
            n = len(tick_list)
            for t in tick_list:
                weights[t] = 1.0 / n
        else:
            st.markdown("Indique un poids pour chaque action (en %, on normalisera).")
            total_input = 0.0
            raw_vals = {}
            for t in tick_list:
                val = st.number_input(
                    tr("sim_weight_for").format(ticker=t),
                    min_value=0.0,
                    value=100.0 / len(tick_list),
                    step=5.0
                )
                raw_vals[t] = val
                total_input += val
            if total_input <= 0:
                st.warning(tr("sim_warn_weights"))
                n = len(tick_list)
                for t in tick_list:
                    weights[t] = 1.0 / n
            else:
                for t in tick_list:
                    weights[t] = raw_vals[t] / total_input

        start_prices = prices.iloc[0]
        last_prices_sim = prices_display.iloc[-1]
        sim_rows = []
        total_value = 0.0
        for t in tick_list:
            p0 = start_prices.get(t, np.nan)
            p1 = last_prices_sim.get(t, np.nan)
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
            st.metric(tr("sim_capital_init"), f"{capital:,.2f} €")
        with col_s2:
            st.metric(tr("sim_current_value"), f"{total_value:,.2f} €", delta=f"{pl_abs:,.2f} €")
        with col_s3:
            st.metric(tr("sim_global_perf"), f"{pl_pct:+.2f} %")
        st.markdown("### " + tr("sim_detail"))
        st.dataframe(sim_df.round(2), use_container_width=True)


# =========================================================
# TAB 4 — FICHE ACTION
# =========================================================
with tab4:
    st.subheader(tr("stock_title"))

    t_selected = st.selectbox(
        tr("graph_choose_stock"),
        list(prices.columns),
        key="detail_select"
    )

    info_row = fund.loc[t_selected] if t_selected in fund.index else None
    s_disp = prices_display[t_selected].dropna()
    if s_disp.empty:
        last_price = np.nan
        start_price = np.nan
        perf_total = np.nan
    else:
        last_price = s_disp.iloc[-1]
        start_price = s_disp.iloc[0]
        perf_total = (last_price / start_price - 1.0) * 100.0 if start_price > 0 else np.nan

    # Abonnement news
    current_subs = load_news_subscriptions(CURRENT_USER)
    already_subscribed = t_selected in current_subs
    sub_checkbox = st.checkbox(
        tr("stock_follow_news").format(ticker=t_selected),
        value=already_subscribed
    )
    if sub_checkbox and not already_subscribed:
        current_subs.append(t_selected)
        save_news_subscriptions(CURRENT_USER, current_subs)
        st.success(tr("stock_follow_added").format(ticker=t_selected))
    elif not sub_checkbox and already_subscribed:
        current_subs = [x for x in current_subs if x != t_selected]
        save_news_subscriptions(CURRENT_USER, current_subs)
        st.info(tr("stock_follow_removed").format(ticker=t_selected))
    

    # Header fiche action
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
            st.metric("Prix actuel", format_price_with_currency(t_selected, last_price))
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

        # 52w range
    if info_row is not None:
        low52 = info_row.get("52w Low", None)
        high52 = info_row.get("52w High", None)
        try:
            low52_val = float(low52)
            high52_val = float(high52)
        except Exception:
            low52_val = high52_val = None
        if low52_val is not None and high52_val is not None and high52_val > low52_val and not pd.isna(last_price):
            ratio = (last_price - low52_val) / (high52_val - low52_val)
            ratio = max(0.0, min(1.0, ratio))
            st.markdown(
                f"""
                <div class="ff-52w">
                  <div class="ff-52w-labels">
                    <span>52w Low : {low52_val:.2f}</span>
                    <span>52w High : {high52_val:.2f}</span>
                  </div>
                  <div class="ff-52w-bar">
                    <div class="ff-52w-track"></div>
                    <div class="ff-52w-marker" style="left: {ratio*100:.1f}%"></div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    # Dossier personnel Fantazia pour ce ticker
    lang_ui = st.session_state.get("lang", "fr")
    if lang_ui == "fr":
        st.markdown("### 📁 Dossier Fantazia pour cette action")
    else:
        st.markdown("### 📁 Fantazia file for this stock")

    # Données perso : watchlists, notes, news, alertes
    wl_user = load_watchlists(CURRENT_USER)
    notes_user = load_notes(CURRENT_USER)
    alerts_user = load_alerts(CURRENT_USER)
    subs_user = load_news_subscriptions(CURRENT_USER)

    t_upper = t_selected.upper()

    # Watchlists contenant ce ticker
    wl_for_t = []
    for wl_name, wl_tickers in wl_user.items():
        if t_upper in [str(x).upper() for x in wl_tickers]:
            wl_for_t.append(wl_name)

    has_note = bool(notes_user.get(t_upper, "").strip())
    is_subscribed = t_upper in [str(x).upper() for x in subs_user]
    n_alerts_t = sum(
        1
        for a in alerts_user
        if str(a.get("ticker", "")).upper() == t_upper
    )

    col_d1, col_d2, col_d3 = st.columns(3)

    # Colonne 1 : Watchlists
    with col_d1:
        if lang_ui == "fr":
            st.markdown("**⭐ Watchlists**")
            if wl_for_t:
                st.write("Présente dans :")
                for name in wl_for_t:
                    st.markdown(f"- `{name}`")
            else:
                st.write("Cette action n'est dans **aucune** de tes watchlists.")
        else:
            st.markdown("**⭐ Watchlists**")
            if wl_for_t:
                st.write("Included in:")
                for name in wl_for_t:
                    st.markdown(f"- `{name}`")
            else:
                st.write("This stock is in **none** of your watchlists.")

    # Colonne 2 : Note perso + suivi news
    with col_d2:
        if lang_ui == "fr":
            st.markdown("**📝 Note personnelle**")
            if has_note:
                st.write("✅ Une note existe pour cette action.")
            else:
                st.write("❌ Aucune note enregistrée pour l'instant.")
            st.markdown("**📰 News suivies**")
            if is_subscribed:
                st.write("✅ Tu suis les news de ce ticker.")
            else:
                st.write("❌ Tu ne suis pas encore les news de ce ticker.")
        else:
            st.markdown("**📝 Personal note**")
            if has_note:
                st.write("✅ A note exists for this stock.")
            else:
                st.write("❌ No note saved yet.")
            st.markdown("**📰 Followed news**")
            if is_subscribed:
                st.write("✅ You follow this ticker's news.")
            else:
                st.write("❌ You don't follow this ticker's news yet.")

    # Colonne 3 : Alertes
    with col_d3:
        if lang_ui == "fr":
            st.markdown("**🔔 Alertes actives**")
            if n_alerts_t > 0:
                st.write(f"✅ {n_alerts_t} alerte(s) configurée(s) sur cette action.")
                st.caption(
                    "Tu peux les gérer dans le Dashboard, section **Alertes**."
                )
            else:
                st.write("❌ Aucune alerte configurée sur cette action.")
        else:
            st.markdown("**🔔 Active alerts**")
            if n_alerts_t > 0:
                st.write(f"✅ {n_alerts_t} alert(s) configured on this stock.")
                st.caption(
                    "You can manage them in the Dashboard, **Alerts** section."
                )
            else:
                st.write("❌ No alert configured on this stock.")

    st.markdown("---")

    # Graphiques fiche
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown(tr("stock_price_history"))
        s_price = prices_display[t_selected].dropna()
        if s_price.empty:
            st.info("Pas assez de données pour afficher le prix historique.")
        else:
            figp = px.line(s_price, title=f"{t_selected} — Prix sur la période ({history_period})")
            figp.update_yaxes(title="Prix")
            figp.update_xaxes(title="Date")
            st.plotly_chart(figp, use_container_width=True)

    with col_g2:
        st.markdown(tr("stock_pe_history"))
        eps = info_row.get("EPS (trailing)") if info_row is not None else None
        if eps is None or pd.isna(eps) or eps == 0:
            st.info(tr("stock_pe_unavailable"))
        else:
            s_price2 = prices_display[t_selected].dropna()
            if s_price2.empty:
                st.info(tr("stock_pe_unavailable"))
            else:
                pe_series = s_price2 / eps
                pe_series.name = "P/E approx"
                figpe = px.line(pe_series, title=f"{t_selected} — P/E recalculé avec EPS actuel (approximation)")
                figpe.update_yaxes(title="P/E approx")
                figpe.update_xaxes(title="Date")
                st.plotly_chart(figpe, use_container_width=True)
                st.caption(tr("stock_pe_caption"))

    # ⚠️ Décomposition Fantazia SUPPRIMÉE (comme demandé) ⚠️

    # Notes perso
    st.markdown("---")
    notes_user = load_notes(CURRENT_USER)
    current_note = notes_user.get(t_selected.upper(), "")
    new_note = st.text_area(
        tr("stock_note_label").format(ticker=t_selected),
        value=current_note,
        height=120
    )
    if st.button("💾 Enregistrer la note"):
        notes_user[t_selected.upper()] = new_note
        save_notes(CURRENT_USER, notes_user)
        st.success(tr("stock_note_saved").format(ticker=t_selected))

        st.markdown("---")

       # Sentiment des analystes / Analyst sentiment
    lang_ui = st.session_state.get("lang", "fr")
    title_sent = "Sentiment des analystes" if lang_ui == "fr" else "Analyst sentiment"
    st.markdown("### " + title_sent)

    # On récupère tout d'un coup via yfinance
    reco_key = None
    reco_mean = None
    reco_n = None
    target_mean = None
    target_high = None
    target_low = None

    try:
        info_full = yf.Ticker(t_selected).info
        # Recos
        reco_key = info_full.get("recommendationKey")
        reco_mean = info_full.get("recommendationMean")
        reco_n = info_full.get("numberOfAnalystOpinions")
        # Objectifs de cours
        target_mean = info_full.get("targetMeanPrice")
        target_high = info_full.get("targetHighPrice")
        target_low = info_full.get("targetLowPrice")
    except Exception:
        pass

    col_sent, col_target = st.columns([2, 1])


    # --------- Colonne gauche : cadran sentiment ---------
    with col_sent:
        if reco_key in [None, "", "none", "na"] or pd.isna(reco_key):
            txt_no = (
                "Pas de données d'analystes disponibles pour ce titre."
                if lang_ui == "fr"
                else "No analyst data available for this stock."
            )
            st.info(txt_no)
        else:
            key = str(reco_key).lower()
            mapping = {
                "strong_buy": ("Fort achat", "Strong Buy", 1.0),
                "buy": ("Achat", "Buy", 0.5),
                "hold": ("Neutre", "Hold", 0.0),
                "sell": ("Vente", "Sell", -0.5),
                "strong_sell": ("Fort vente", "Strong Sell", -1.0),
            }
            label_fr, label_en, score = mapping.get(key, ("Neutre", "Hold", 0.0))
            label = label_fr if lang_ui == "fr" else label_en

            # Angle de l'aiguille entre -80° (forte vente) et +80° (fort achat)
            angle = float(score) * 80.0
            # Score 0–100 pour affichage textuel
            score_pct = (score + 1.0) / 2.0 * 100.0

            extra = []
            if isinstance(reco_mean, (int, float, np.number)) and not pd.isna(reco_mean):
                if lang_ui == "fr":
                    extra.append(
                        f"Note moyenne Yahoo Finance : {reco_mean:.2f} (1 = Fort achat, 5 = Fort vente)."
                    )
                else:
                    extra.append(
                        f"Yahoo Finance average rating: {reco_mean:.2f} (1 = Strong buy, 5 = Strong sell)."
                    )
            if isinstance(reco_n, (int, float, np.number)) and not pd.isna(reco_n) and reco_n > 0:
                if lang_ui == "fr":
                    extra.append(f"Basé sur {int(reco_n)} analystes.")
                else:
                    extra.append(f"Based on {int(reco_n)} analysts.")

                        # On transforme la reco en un cran sur l'échelle 5 niveaux
            order_keys = ["strong_sell", "sell", "hold", "buy", "strong_buy"]
            labels_fr_full = ["Fort vente", "Vente", "Neutre", "Achat", "Fort achat"]
            labels_en_full = ["Strong sell", "Sell", "Hold", "Buy", "Strong buy"]
            labels_full = labels_fr_full if lang_ui == "fr" else labels_en_full

            try:
                active_idx = order_keys.index(key)
            except ValueError:
                active_idx = 2  # par défaut : Neutre

            steps_html = ""
            for i, txt in enumerate(labels_full):
                base_classes = f"ff-analyst-step ff-analyst-step-{i}"
                if i == active_idx:
                    base_classes += " ff-analyst-step-active"
                steps_html += f'<div class="{base_classes}">{html.escape(txt)}</div>'

            html_block = f"""
            <div class="ff-analyst-card">
              <div class="ff-analyst-header">
                <div class="ff-analyst-main-label">{html.escape(label)}</div>
              </div>
              <div class="ff-analyst-scale">
                {steps_html}
              </div>
              <div class="ff-analyst-caption">
                {'<br>'.join(html.escape(x) for x in extra) if extra else ''}
              </div>
            </div>
            """
            st.markdown(html_block, unsafe_allow_html=True)


            # Explications sous le cadran
            if lang_ui == "fr":
                explain = """
**Comment lire ce cadran ?**

- Zone rouge : plutôt *Vente* / *Fort vente*.
- Zone orange : plutôt *Neutre* / conserver.
- Zone verte : plutôt *Achat* / *Fort achat*.

Échelle Yahoo Finance (moyenne des analystes) :
- 1,0 = Fort achat
- 2,0 = Achat
- 3,0 = Neutre
- 4,0 = Vente
- 5,0 = Fort vente
"""
            else:
                explain = """
**How to read this gauge?**

- Red area: *Sell* / *Strong sell* bias.
- Orange area: more *Neutral* / hold.
- Green area: *Buy* / *Strong buy* bias.

Yahoo Finance rating scale (average of analysts):
- 1.0 = Strong buy
- 2.0 = Buy
- 3.0 = Hold
- 4.0 = Sell
- 5.0 = Strong sell
"""
            st.markdown(explain)

            # Phrase résumé type investing.com
            if isinstance(reco_mean, (int, float, np.number)) and not pd.isna(reco_mean):
                if lang_ui == "fr":
                    sentence = (
                        f"Les analystes Yahoo classent actuellement **{t_selected}** en **{label.lower()}** "
                        f"(score moyen {reco_mean:.2f} / 5"
                    )
                    if isinstance(reco_n, (int, float, np.number)) and not pd.isna(reco_n) and reco_n > 0:
                        sentence += f", basé sur {int(reco_n)} analystes"
                    sentence += ")."
                else:
                    sentence = (
                        f"Yahoo analysts currently rate **{t_selected}** as **{label.lower()}** "
                        f"(average score {reco_mean:.2f} / 5"
                    )
                    if isinstance(reco_n, (int, float, np.number)) and not pd.isna(reco_n) and reco_n > 0:
                        sentence += f", based on {int(reco_n)} analysts"
                    sentence += ")."
                st.markdown(sentence)

    # --------- Colonne droite : objectifs de cours ---------
    with col_target:
        if lang_ui == "fr":
            st.markdown("#### Objectif de cours moyen")
        else:
            st.markdown("#### Average price target")

        if target_mean is None or pd.isna(target_mean):
            txt_no_pt = (
                "Pas d'objectif de cours disponible."
                if lang_ui == "fr"
                else "No price target available."
            )
            st.info(txt_no_pt)
        else:
            try:
                tgt = float(target_mean)
                cur = float(last_price) if not pd.isna(last_price) else None
            except Exception:
                tgt = None
                cur = None

            if tgt is None or cur is None or cur <= 0:
                val_label = format_price_with_currency(t_selected, tgt) if tgt is not None else "n/a"
                st.metric(
                    "Objectif moyen 12M" if lang_ui == "fr" else "12M average target",
                    val_label
                )
            else:
                upside_pct = (tgt / cur - 1.0) * 100.0
                val_label = format_price_with_currency(t_selected, tgt)
                delta_label = f"{upside_pct:+.1f} %"
                if lang_ui == "fr":
                    st.metric("Objectif moyen 12M", val_label, delta=f"Potentiel {delta_label}")
                else:
                    st.metric("12M average target", val_label, delta=f"Upside {delta_label}")

            # Détails haut / bas si dispo
            details_lines = []
            if target_low is not None and not pd.isna(target_low):
                if lang_ui == "fr":
                    details_lines.append(f"Objectif bas : {format_price_with_currency(t_selected, target_low)}")
                else:
                    details_lines.append(f"Low target: {format_price_with_currency(t_selected, target_low)}")
            if target_high is not None and not pd.isna(target_high):
                if lang_ui == "fr":
                    details_lines.append(f"Objectif haut : {format_price_with_currency(t_selected, target_high)}")
                else:
                    details_lines.append(f"High target: {format_price_with_currency(t_selected, target_high)}")

            if details_lines:
                st.write("\n".join(details_lines))

    st.markdown("---")
    st.markdown(tr("stock_news_title"))
    if not FINNHUB_API_KEY:
        st.info(tr("mynews_no_key"))
    else:
        news_df = load_news_finnhub(t_selected, days=7, max_items=10)
        if news_df.empty:
            st.info(tr("stock_news_none"))
        else:
            for _, row in news_df.iterrows():
                dt = row.get("datetime", None)
                src = row.get("source", "")
                title = row.get("headline", "")
                summary = row.get("summary", "")
                url = row.get("url", "")
                date_str = dt.strftime("%d/%m/%Y %H:%M") if isinstance(dt, pd.Timestamp) else ""
                st.markdown(f"**{title}**")
                meta_parts = []
                if date_str:
                    meta_parts.append(date_str)
                if src:
                    meta_parts.append(src)
                if meta_parts:
                    st.caption(" · ".join(meta_parts))
                if summary:
                    st.write(summary)
                if url:
                    st.markdown(f"[Lire l'article]({url})")
                st.markdown("---")




    # Export fiche PDF
    st.markdown("---")
    if st.button(tr("stock_pdf_btn")):
        if not HAVE_REPORTLAB:
            st.warning(tr("stock_pdf_no_lib"))
        else:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            story.append(Paragraph(f"Fiche Fantazia Finance — {t_selected}", styles["Title"]))
            story.append(Spacer(1, 12))
            if info_row is not None:
                story.append(Paragraph(f"Nom : {info_row.get('Nom', '')}", styles["Normal"]))

                story.append(Paragraph(
                    f"Secteur : {info_row.get('Secteur (API)', '')}", styles["Normal"]
                ))
                story.append(Paragraph(
                    f"Industrie : {info_row.get('Industrie (API)', '')}", styles["Normal"]
                ))
                story.append(Paragraph(
                    f"Pays / Devise : {info_row.get('Pays', '')} / {info_row.get('Devise', '')}", styles["Normal"]
                ))
            story.append(Spacer(1, 12))
            story.append(Paragraph(f"Prix actuel : {format_price_with_currency(t_selected, last_price)}", styles["Normal"]))
            if not pd.isna(perf_total):
                story.append(Paragraph(f"Perf sur la période : {perf_total:+.2f} %", styles["Normal"]))
            story.append(Spacer(1, 12))
            story.append(Paragraph("Principaux ratios :", styles["Heading3"]))
            if info_row is not None:
                ratio_data = [
                    ["P/E (trailing)", str(info_row.get("P/E (trailing)", ""))],
                    ["P/B", str(info_row.get("P/B", ""))],
                    ["ROE", str(info_row.get("ROE", ""))],
                    ["Marge nette", str(info_row.get("Marge nette", ""))],
                    ["Dette/Capitaux", str(info_row.get("Dette/Capitaux", ""))],
                    ["Div. Yield", str(info_row.get("Div. Yield", ""))],
                ]
                story.append(Table(ratio_data, hAlign="LEFT"))
            story.append(Spacer(1, 12))
            story.append(Paragraph("Note personnelle :", styles["Heading3"]))

            story.append(Paragraph(new_note.replace("\n", "<br/>"), styles["Normal"]))
            doc.build(story)
            buffer.seek(0)
            st.download_button(
                label=tr("stock_pdf_btn"),
                data=buffer,
                file_name=f"fiche_{t_selected}.pdf",
                mime="application/pdf"
            )


# =========================================================
# TAB 5 — AIDE
# =========================================================
with tab5:
    st.subheader(tr("help_title"))
    st.markdown(
        "- Comptes utilisateurs, watchlists, notes et alertes sont stockés localement (JSON).\n"
        "- Fantazia Score = classement relatif des actions dans ton panier.\n"
        "- Fantazia Score personnalisé = même logique mais avec tes poids.\n"
        "- Alertes = variation journalière ou seuil de prix, affichées en ruban et dans 'Alertes du jour'.\n"
        "- Simulateur = portefeuille virtuel basé sur les prix historiques chargés.\n"
        "- Benchmark = comparaison vs indice (surperf 1Y vs benchmark).\n"
        "- Corrélation = qui bouge avec qui (et dans quelle intensité).\n"
        "- News = via Finnhub (si FINNHUB_API_KEY présente).\n"
        "- Historique = Yahoo / Twelve / Finnhub avec fallback par action."
    )
    st.divider()
    st.markdown(tr("help_api_status"))
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write("Twelve Data :", "✅" if TWELVE_API_KEY else "⚠️")
    with c2:
        st.write("Finnhub :", "✅" if FINNHUB_API_KEY else "⚠️")
    with c3:
        st.write("Polygon :", "✅" if POLYGON_API_KEY else "⚠️")
    st.divider()
    st.markdown("### " + tr("help_glossary"))
    lang = st.session_state.get("lang", "fr")
    if lang == "fr":
        st.markdown(
            "- **P/E** : Prix / Bénéfice. Plus c'est élevé, plus le marché paie cher 1€ de bénéfice.\n"
            "- **P/B** : Prix / Valeur comptable. Haut = valorisation élevée vs capitaux propres.\n"
            "- **ROE** : Return on Equity. Rentabilité des fonds propres.\n"
            "- **Marge nette** : Bénéfice net / Chiffre d'affaires.\n"
            "- **Volatilité annualisée** : Amplitude moyenne des variations, annualisée.\n"
            "- **Max Drawdown** : Plus forte baisse depuis un plus haut historique.\n"
            "- **Beta** : Sensibilité au marché (1 = comme le marché, >1 = plus volatile).\n"
        )
    else:
        st.markdown(
            "- **P/E**: Price / Earnings. Higher = market pays more for 1€ of earnings.\n"
            "- **P/B**: Price / Book value. High = rich valuation vs equity.\n"
            "- **ROE**: Return on Equity. Profitability of equity.\n"
            "- **Net margin**: Net income / Revenue.\n"
            "- **Annualized volatility**: Average amplitude of moves, annualized.\n"
            "- **Max Drawdown**: Largest drop from a historical high.\n"
            "- **Beta**: Sensitivity to the market (1 = like index, >1 = more volatile).\n"
        )
    st.divider()
    st.write("Auto-refresh lib :", "✅" if HAS_AUTOREFRESH else "⚠️ non installée")


# =========================================================
# TAB 6 — ASSISTANT
# =========================================================
with tab6:
    st.subheader(tr("assistant_title"))
    st.caption(tr("assistant_caption"))

    if "faq_history" not in st.session_state:
        st.session_state["faq_history"] = []

    lang_ui = st.session_state.get("lang", "fr")

    # Actions rapides (boutons pré-remplis)
    if lang_ui == "fr":
        st.markdown("#### Actions rapides")
    else:
        st.markdown("#### Quick actions")

    preset_msg = None
    col_q1, col_q2, col_q3 = st.columns(3)

    with col_q1:
        if lang_ui == "fr":
            if st.button("❓ Fantazia Score", key="qa_score"):
                preset_msg = "Explique-moi le Fantazia Score."
        else:
            if st.button("❓ Fantazia Score", key="qa_score"):
                preset_msg = "Explain the Fantazia Score."

    with col_q2:
        if lang_ui == "fr":
            if st.button("⚙️ Score personnalisé", key="qa_custom"):
                preset_msg = "Explique-moi le Fantazia Score personnalisé."
        else:
            if st.button("⚙️ Custom score", key="qa_custom"):
                preset_msg = "Explain the custom Fantazia Score."
    
    with col_q3:
        if lang_ui == "fr":
            if st.button("📊 Dashboard & graphiques", key="qa_dashboard"):
                preset_msg = "Explique-moi le Dashboard et les graphiques (base 100, spread, benchmark...)."
        else:
            if st.button("📊 Dashboard & charts", key="qa_dashboard"):
                preset_msg = "Explain the Dashboard and charts (base 100, spread, benchmark...)."

    # Affichage de l'historique du chat
    for role, msg in st.session_state["faq_history"]:
        with st.chat_message(role):
            st.markdown(msg)

    # Entrée utilisateur classique
    user_msg = st.chat_input(tr("assistant_input"))

    # Soit message tapé, soit message pré-rempli par un bouton
    final_msg = user_msg or preset_msg

    if final_msg:
        # On enregistre la question
        st.session_state["faq_history"].append(("user", final_msg))
        # On génère la réponse via la FAQ existante
        answer = faq_answer(final_msg)
        st.session_state["faq_history"].append(("assistant", answer))

        # On affiche uniquement la nouvelle interaction (en plus de l'historique déjà rendu)
        with st.chat_message("user"):
            st.markdown(final_msg)
        with st.chat_message("assistant"):
            st.markdown(answer)
