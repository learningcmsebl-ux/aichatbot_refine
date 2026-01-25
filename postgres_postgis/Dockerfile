FROM postgis/postgis:15-3.4

# Workaround:
# Some images place PostGIS extension files under /usr/share/postgresql/15/extension,
# while the server's share dir expects /usr/local/share/postgresql/extension.
# Copy the PostGIS extension files into the server's expected share directory.
RUN set -eux; \
  mkdir -p /usr/local/share/postgresql/extension; \
  if [ -d /usr/share/postgresql/15/extension ]; then \
    cp -a /usr/share/postgresql/15/extension/postgis* /usr/local/share/postgresql/extension/ || true; \
    cp -a /usr/share/postgresql/15/extension/address_standardizer* /usr/local/share/postgresql/extension/ || true; \
    cp -a /usr/share/postgresql/15/extension/postgis_tiger_geocoder* /usr/local/share/postgresql/extension/ || true; \
    cp -a /usr/share/postgresql/15/extension/fuzzystrmatch* /usr/local/share/postgresql/extension/ || true; \
  fi

