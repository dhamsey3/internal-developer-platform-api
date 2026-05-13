#!/bin/bash
set -e

# Example migration script using Alembic (if used)

if [ ! -f alembic.ini ]; then
  echo "[!] alembic.ini not found. Please set up Alembic."
  exit 1
fi

alembic upgrade head
