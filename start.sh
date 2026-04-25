#!/bin/bash

# Génère le fichier secrets.toml depuis les variables d'environnement Railway
mkdir -p /app/.streamlit

cat > /app/.streamlit/secrets.toml << EOF
TWELVE_API_KEY = "${TWELVE_API_KEY}"
FINNHUB_API_KEY = "${FINNHUB_API_KEY}"
ALPHAVANTAGE_API_KEY = "${ALPHAVANTAGE_API_KEY}"
POLYGON_API_KEY = "${POLYGON_API_KEY}"
ADMIN_USER = "${ADMIN_USER}"
ADMIN_PASS = "${ADMIN_PASS}"
DB_URL = "${DB_URL}"
smtp_server = "${smtp_server}"
smtp_port = ${smtp_port}
smtp_login = "${smtp_login}"
smtp_password = "${smtp_password}"
EOF

echo "✅ secrets.toml generated at /app/.streamlit/secrets.toml"

# Démarre Streamlit sur le port dynamique assigné par Railway
streamlit run app.py \
  --server.port $PORT \
  --server.address 0.0.0.0 \
  --server.headless true
