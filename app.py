import json
import os
import base64
import hashlib
import secrets
import html
from io import BytesIO
from typing import Dict, List, Tuple, Optional, Callable

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import requests

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
    page_title="Fantazia Finance — Comparateur V3.7",
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
        "app_title": "📈 Comparateur d'actions par secteur, Fait par Fantazia Finance ( Alexandre) — V3.7",
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
        "sidebar_rt": "Tenter prix live (Polygon, expérimental)",
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
        "mynews_no_key": "Aucune clé Finnhub configurée → impossible de charger les news. Ajoute `FINNHUB_API_KEY` dans config.json.",
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
        "help_title": "ℹ️ Aide rapide — V3.7 (comptes, Fantazia Score %, alertes, news & assistant)",
        "help_api_status": "### Statut des clés API",
        "help_glossary": "📚 Glossaire rapide (termes financiers)",
        "assistant_title": "🤖 Assistant Fantazia (FAQ)",
        "assistant_caption": "Pose tes questions sur le fonctionnement du site : Fantazia Score, graphiques, watchlists, alertes, simulateur, benchmark, corrélation, news, etc.",
        "assistant_input": "Ta question sur Fantazia Finance...",
    },
    "en": {
        "app_title": "📈 Sector Stock Comparator, made by Fantazia Finance (Alexandre) — V3.7",
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
        "sidebar_rt": "Try live prices (Polygon, experimental)",
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
        "mynews_no_key": "No Finnhub key configured → cannot load news. Add `FINNHUB_API_KEY` in config.json.",
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
        "help_title": "ℹ️ Quick help — V3.7 (accounts, Fantazia Score %, alerts, news & assistant)",
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
        "button[data-baseweb='tab'][aria-selected='true'] {",
        f"border-bottom: 2px solid {accent};",
        "}",
        "[data-testid='stMetric'] {",
        "padding: 10px 12px;",
        "border-radius: 12px;",
        "background: rgba(245,245,245,0.9);",
        "border: 1px solid rgba(0,0,0,0.06);",
        "}",
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
        "@keyframes ff-marquee-move {",
        "  0% { transform: translateX(0%); }",
        "  100% { transform: translateX(-100%); }",
        "}",
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
                users[username] = {"password_hash": pwd_hash, "salt": salt}
                save_users(users)
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
                        st.session_state["user"] = username
                        msg.success(tr("login_ok_login"))
                        rerun_app()
                    else:
                        msg.error(tr("login_err_wrong_pwd"))

    st.stop()


CURRENT_USER = ensure_authenticated()


# =========================================================
# SECTORS
# =========================================================
SECTORS = {
    "Mega Tech US": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"],
    "Semi-conducteurs": ["NVDA", "AMD", "INTC", "TSM", "ASML"],
    "Banques US": ["JPM", "BAC", "WFC", "C", "GS", "MS"],
    "Pétrole & Énergie": ["XOM", "CVX", "SHEL", "TTE", "BP"],
    "Luxe (Europe)": ["MC.PA", "RMS.PA", "KER.PA", "PRU.L", "BRBY.L"],
}


# =========================================================
# CONFIG
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
# WATCHLISTS
# =========================================================
def load_watchlists(user: str) -> Dict[str, List[str]]:
    if not os.path.exists(WATCHLIST_FILE):
        return {}
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if isinstance(data, dict):
        if user in data and isinstance(data[user], dict):
            base = data[user]
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
def load_news_subscriptions(user: str) -> List[str]:
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


def save_news_subscriptions(user: str, subs: List[str]) -> None:
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
def load_alerts(user: str) -> List[Dict]:
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


def save_alerts(user: str, alerts: List[Dict]) -> None:
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
def load_notes(user: str) -> Dict[str, str]:
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


def save_notes(user: str, notes: Dict[str, str]) -> None:
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
    """
    Yahoo Finance :
    - 1d / 5d : interval 5m (intraday)
    - sinon : interval 1d
    """
    try:
        if period in ["1d", "5d"]:
            interval = "5m"
        else:
            interval = "1d"
        data = yf.download(
            [ticker],
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            progress=False
        )
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
# REALTIME POLYGON (EXPERIMENTAL)
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


@st.cache_data(ttl=900)  # <= données rafraîchies au max toutes les 15 min
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
@st.cache_data(ttl=900)
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
            "- la 52w range, les sources de données (Yahoo, Twelve, Finnhub, Polygon expérimental).\n\n"
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
            "- the 52w range, data sources (Yahoo, Twelve, Finnhub, experimental Polygon).\n\n"
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
    rt_data: Dict[str, Tuple[float, pd.Timestamp]] = {}
    if use_realtime and POLYGON_API_KEY:
        rt_data = fetch_realtime_polygon_batch(list(prices.columns))

    if st.button("🔄 Refresh prix temps réel (Polygon expérimental)"):
        if use_realtime and POLYGON_API_KEY:
            rt_data = fetch_realtime_polygon_batch(list(prices.columns))

    prices_display = prices.copy()
    if rt_data:
        for t, (p, _) in rt_data.items():
            if t in prices_display.columns and not prices_display[t].dropna().empty:
                prices_display.loc[prices_display.index[-1], t] = p

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

    st.subheader(tr("alerts_of_day"))
    if triggered_alerts:
        for a in triggered_alerts:
            st.markdown(f"- **[{a['ticker']}]** {a['desc']}")
    else:
        st.write(tr("alerts_none"))

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

    st.subheader(tr("sources_title"))
    src_df = pd.DataFrame(
        [{"Ticker": t, "Source historique": pretty_source_name(source_map.get(t, "none"))} for t in prices.columns]
    )
    try:
        styled_src = src_df.style.applymap(source_badge_style, subset=["Source historique"])
        st.dataframe(styled_src, use_container_width=True)
    except Exception:
        st.dataframe(src_df, use_container_width=True)

    st.subheader(tr("prices_title"))
    cols_price = st.columns(min(4, len(prices_display.columns)))
    first_cols = list(prices_display.columns)[:len(cols_price)]
    for i, t in enumerate(first_cols):
        s = prices_display[t].dropna()
        if s.empty:
            continue
        last_close = prices[t].dropna().iloc[-1]
        last_disp = s.iloc[-1]
        cur = ""
        if t in fund.index:
            cur = str(fund.loc[t, "Devise"] or "")
        unit = f" {cur}" if cur else ""
        if t in rt_data:
            rt_price, _ = rt_data[t]
            delta_pct = (rt_price / last_close - 1.0) * 100 if last_close else None
            suffix = "(Polygon expérimental)" if st.session_state.get("lang", "fr") == "fr" else "(Polygon experimental)"
            cols_price[i].metric(
                label=f"{t} {suffix}",
                value=f"{rt_price:.2f}{unit}",
                delta=f"{delta_pct:.2f}% vs last close" if delta_pct is not None else None
            )
        else:
            cols_price[i].metric(label=f"{t} (Last)", value=f"{last_disp:.2f}{unit}")

    if len(prices_display.columns) > len(cols_price):
        with st.expander("Voir tous les prix actuels"):
            grid_cols = st.columns(4)
            for j, t in enumerate(list(prices_display.columns)):
                c = grid_cols[j % 4]
                s = prices_display[t].dropna()
                if s.empty:
                    continue
                last_close = prices[t].dropna().iloc[-1]
                last_disp = s.iloc[-1]
                cur = ""
                if t in fund.index:
                    cur = str(fund.loc[t, "Devise"] or "")
                unit = f" {cur}" if cur else ""
                if t in rt_data:
                    rt_price, _ = rt_data[t]
                    delta_pct = (rt_price / last_close - 1.0) * 100 if last_close else None
                    suffix = "(Polygon expérimental)" if st.session_state.get("lang", "fr") == "fr" else "(Polygon experimental)"
                    c.metric(
                        label=f"{t} {suffix}",
                        value=f"{rt_price:.2f}{unit}",
                        delta=f"{delta_pct:.2f}% vs close" if delta_pct is not None else None
                    )
                else:
                    c.metric(label=f"{t}", value=f"{last_disp:.2f}{unit}")

    st.subheader(tr("graph_title"))
    graph_mode = st.radio(
        "",
        [tr("graph_mode_base100"), tr("graph_mode_price"), tr("graph_mode_spread")],
        horizontal=True
    )

    if graph_mode == tr("graph_mode_base100"):
        norm = prices_display / prices_display.iloc[0] * 100.0
        if benchmark_series is not None and not benchmark_series.empty:
            bm_norm = benchmark_series / benchmark_series.iloc[0] * 100.0
            norm = norm.join(bm_norm.rename("BENCHMARK"), how="outer")
        fig = px.line(norm, title=f"Performance normalisée (base 100) — {sector_label}")
        st.plotly_chart(fig, use_container_width=True)
    elif graph_mode == tr("graph_mode_price"):
        selected = st.selectbox(
            tr("graph_choose_stock"),
            list(prices_display.columns),
            key="price_graph_select"
        )
        price_one = prices_display[[selected]].dropna()
        log_scale = st.checkbox(tr("graph_log_scale"), value=False)
        fig = px.line(price_one, title=f"{selected} — Prix sur la période ({history_period})")
        fig.update_yaxes(title="Prix", type="log" if log_scale else "linear")
        fig.update_xaxes(title="Date")
        st.plotly_chart(fig, use_container_width=True)
    else:
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
            st.info(tr("graph_spread_info"))
        else:
            sub = prices_display[[t1, t2]].dropna(how="any")
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

    st.subheader(tr("scores_top_title"))

    df_scores = ranked_all.copy()

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
        "Market Cap",
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
        "Nom", "Pays", "Devise", "Market Cap",
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

    # Market Cap en milliards dans le tableau
    if "Market Cap" in display_df.columns:
        mcap = pd.to_numeric(display_df["Market Cap"], errors="coerce")
        display_df["Market Cap (Mds)"] = (mcap / 1e9).round(2)
        display_df.drop(columns=["Market Cap"], inplace=True)

    # Arrondir toutes les colonnes numériques à 2 décimales
    for col_name in display_df.columns:
        if pd.api.types.is_numeric_dtype(display_df[col_name]):
            display_df[col_name] = display_df[col_name].round(2)

    perf_cols_subset = [c for c in ["Perf 1M", "Perf 3M", "Perf 6M", "Perf 1Y"] if c in display_df.columns]

    try:
        styled = display_df.style.applymap(source_badge_style, subset=["Source historique"])
        if perf_cols_subset:
            styled = styled.applymap(perf_color, subset=perf_cols_subset)
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

    csv = display_df.to_csv().encode("utf-8")
    st.download_button(
        tr("export_csv"),
        data=csv,
        file_name=f"comparateur_{sector_label.lower().replace(' ', '_')}.csv",
        mime="text/csv"
    )

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

    with st.expander(tr("tech_notes_title")):
        lines = [
            f"- Source historique choisie : **{price_source_mode}**",
            "- Fallback par action actif.",
            f"- Polygon (expérimental) : **{'activé' if use_realtime else 'désactivé'}**",
            "- Perf 1M/3M/6M : approximation en séances.",
            "- Perf 1Y : calculée en calendrier (1 an réel).",
            f"- Période d'historique actuelle : **{history_period}**.",
            "- Cache des prix : rafraîchi au max toutes les 15 minutes (Yahoo / autres sources).",
        ]
        if benchmark_ticker:
            lines.append(f"- Benchmark sélectionné : **{benchmark_ticker}**")
        st.markdown("\n".join(lines))

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
        last_prices = prices_display.iloc[-1]
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
            st.metric(tr("sim_capital_init"), f"{capital:,.2f} €")
        with col_s2:
            st.metric(tr("sim_current_value"), f"{total_value:,.2f} €", delta=f"{pl_abs:,.2f} €")
        with col_s3:
            st.metric(tr("sim_global_perf"), f"{pl_pct:+.2f} %")
        st.markdown("### " + tr("sim_detail"))
        st.dataframe(sim_df, use_container_width=True)


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
    last_price = prices_display[t_selected].dropna().iloc[-1]
    start_price = prices_display[t_selected].dropna().iloc[0]
    perf_total = (last_price / start_price - 1.0) * 100.0 if start_price > 0 else np.nan

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
            cur = info_row.get("Devise", "")
            unit = f" {cur}" if cur else ""
            st.metric("Prix actuel", f"{last_price:.2f}{unit}")
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
        if low52_val is not None and high52_val is not None and high52_val > low52_val:
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

    st.markdown("---")

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown(tr("stock_price_history"))
        s_price = prices_display[t_selected].dropna()
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
            pe_series = s_price2 / eps
            pe_series.name = "P/E approx"
            figpe = px.line(pe_series, title=f"{t_selected} — P/E recalculé avec EPS actuel (approximation)")
            figpe.update_yaxes(title="P/E approx")
            figpe.update_xaxes(title="Date")
            st.plotly_chart(figpe, use_container_width=True)
            st.caption(tr("stock_pe_caption"))

    # Notes perso
    st.markdown("---")
    notes_user = load_notes(CURRENT_USER)
    current_note = notes_user.get(t_selected.upper(), "")
    new_note = st.text_area(
        tr("stock_note_label").format(ticker=t_selected),
        value=current_note,
        height=120
    )
    if st.button("💾 " + (tr("stock_note_label").split(" ")[0] if st.session_state["lang"] == "fr" else "Save note")):
        notes_user[t_selected.upper()] = new_note
        save_notes(CURRENT_USER, notes_user)
        st.success(tr("stock_note_saved").format(ticker=t_selected))

    st.markdown("---")

    st.markdown(tr("stock_raw_data"))
    if info_row is not None:
        raw = info_row.copy()
        for idx, val in raw.items():
            if isinstance(val, (int, float, np.number)):
                if pd.isna(val):
                    continue
                try:
                    raw[idx] = round(float(val), 2)
                except Exception:
                    pass
        st.dataframe(raw.to_frame(name="Valeur"), use_container_width=True)

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

                story.append(Paragraph(f"Secteur : {info_row.get('Secteur (API)', '')}", styles["Normal"]))
                story.append(Paragraph(f"Industrie : {info_row.get('Industrie (API)', '')}", styles["Normal"]))
                story.append(Paragraph(f"Pays / Devise : {info_row.get('Pays', '')} / {info_row.get('Devise', '')}", styles["Normal"]))
            story.append(Spacer(1, 12))
            story.append(Paragraph(f"Prix actuel : {last_price:.2f}", styles["Normal"]))
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
        "- Historique = Yahoo / Twelve / Finnhub avec fallback par action, cache rafraîchi toutes les 15 minutes.\n"
        "- Polygon = tentative de prix live, mode expérimental (peut échouer ou ne rien ajouter selon la clé)."
    )
    st.divider()
    st.markdown(tr("help_api_status"))
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write("Twelve Data :", "✅" if TWELVE_API_KEY else "⚠️")
    with c2:
        st.write("Finnhub :", "✅" if FINNHUB_API_KEY else "⚠️")
    with c3:
        st.write("Polygon (expérimental) :", "✅" if POLYGON_API_KEY else "⚠️")
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

    for role, msg in st.session_state["faq_history"]:
        with st.chat_message(role):
            st.markdown(msg)

    user_msg = st.chat_input(tr("assistant_input"))
    if user_msg:
        st.session_state["faq_history"].append(("user", user_msg))
        answer = faq_answer(user_msg)
        st.session_state["faq_history"].append(("assistant", answer))
        with st.chat_message("user"):
            st.markdown(user_msg)
        with st.chat_message("assistant"):
            st.markdown(answer)
