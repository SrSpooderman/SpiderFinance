#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ $# -lt 1 || $# -gt 3 || ${1:-} == --help ]]; then
  echo 'Uso: scripts/import-excel.sh ARCHIVO.xlsx [ID_USUARIO] [--apply]'
  echo 'Sin --apply valida el Excel. Con --apply crea una copia y carga los datos en un usuario vacío.'
  exit 2
fi
file="$(realpath -- "$1")"
if [[ ! -f "$file" || "$file" != *.xlsx ]]; then
  echo 'Indica un archivo XLSX existente.' >&2
  exit 2
fi
user_id="${2:-}"
mode="${3:-}"
if [[ -n "$user_id" && ! "$user_id" =~ ^[0-9]+$ ]]; then
  echo 'El ID de usuario debe ser numérico.' >&2
  exit 2
fi
if [[ -n "$mode" && "$mode" != --apply ]]; then
  echo 'La única opción admitida es --apply.' >&2
  exit 2
fi
if [[ "$mode" == --apply && -z "$user_id" ]]; then
  echo 'La carga necesita un ID de usuario.' >&2
  exit 2
fi
docker compose config --quiet
args=(--file /import/input.xlsx)
if [[ -n "$user_id" ]]; then args+=(--user-id "$user_id"); fi
if [[ "$mode" == --apply ]]; then
  mkdir -p backups
  stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
  container_backup="/tmp/spiderfinance-${stamp}.dump"
  backup="backups/spiderfinance-${stamp}.dump"
  cleanup() {
    docker compose exec -T postgres rm -f "$container_backup" >/dev/null 2>&1 || true
  }
  trap cleanup EXIT
  docker compose exec -T postgres sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" -f "$1"' sh "$container_backup"
  docker compose cp "postgres:$container_backup" "$backup"
  chmod 600 "$backup"
  echo "Copia de PostgreSQL: $backup"
  args+=(--apply)
fi
docker compose run --rm --no-deps -v "$file:/import/input.xlsx:ro" backend \
  python -m app.application.template_import "${args[@]}"
