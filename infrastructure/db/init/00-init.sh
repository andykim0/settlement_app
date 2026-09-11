#!/bin/bash
# /docker-entrypoint-initdb.d/00-init.sh
#
# Postgres first-boot initializer.
# Creates the delivery_rider database (delivery_shared is already created
# by POSTGRES_DB env), then loads schema into both DBs.
#
# This runs ONLY on first container start (or after `docker compose down -v`).
# To replay schema changes during dev: docker compose down -v && docker compose up -d

set -euo pipefail

echo "[init] creating delivery_rider database..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE delivery_rider ENCODING 'UTF8';
EOSQL

echo "[init] loading shared schema into delivery_shared..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" \
    -d delivery_shared -f /sql/shared-schema.sql

echo "[init] loading rider schema into delivery_rider..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" \
    -d delivery_rider -f /sql/rider-schema.sql

echo "[init] done. databases ready: delivery_shared, delivery_rider"
