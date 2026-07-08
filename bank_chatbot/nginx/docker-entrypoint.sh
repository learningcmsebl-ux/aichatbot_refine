#!/bin/sh
set -e

mkdir -p /etc/nginx/ssl

if [ ! -f /etc/nginx/ssl/server.crt ] || [ ! -f /etc/nginx/ssl/intermediate.crt ] || [ ! -f /etc/nginx/ssl/privkey.pem ]; then
  echo "ERROR: Missing TLS files in /etc/nginx/ssl (server.crt, intermediate.crt, privkey.pem)" >&2
  exit 1
fi

cat /etc/nginx/ssl/server.crt /etc/nginx/ssl/intermediate.crt > /etc/nginx/ssl/fullchain.pem
chmod 600 /etc/nginx/ssl/privkey.pem 2>/dev/null || true

echo "TLS fullchain prepared for dia.ebl-bd.com"
exec /docker-entrypoint.sh "$@"
