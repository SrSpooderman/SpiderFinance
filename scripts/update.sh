#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

cd "$(dirname "${BASH_SOURCE[0]}")/.."
mode="${1:-local}"
local_compose=(docker compose -f compose.yaml)
release_compose=(docker compose -f compose.yaml -f compose.release.yaml)

if [[ "$mode" == --help || "$mode" == -h ]]; then
  echo 'Uso: scripts/update.sh [local|source|release]'
  echo 'local: reconstruye el código actual; source: git pull y reconstruye; release: descarga imágenes GHCR.'
  exit 0
fi
if [[ "$mode" != local && "$mode" != source && "$mode" != release ]]; then
  echo "Modo desconocido: $mode" >&2
  exit 2
fi
if [[ ! -f .env ]]; then
  echo 'Falta .env. Cópialo desde .env.example y configura tus secretos.' >&2
  exit 1
fi
if [[ "$mode" == source ]] && ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo 'El modo source requiere un clon Git. Usa local o release.' >&2
  exit 1
fi
if [[ "$mode" == release ]]; then
  "${release_compose[@]}" config --quiet
else
  "${local_compose[@]}" config --quiet
fi

mkdir -p backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
container_backup="/tmp/spiderfinance-${stamp}.dump"
backup="backups/spiderfinance-${stamp}.dump"
cleanup() {
  "${local_compose[@]}" exec -T postgres rm -f "$container_backup" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo 'Creando copia de PostgreSQL...'
"${local_compose[@]}" exec -T postgres sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" -f "$1"' sh "$container_backup"
"${local_compose[@]}" cp "postgres:$container_backup" "$backup"
chmod 600 "$backup"
echo "Copia guardada en $backup"

case "$mode" in
  local)
    "${local_compose[@]}" up -d --build --wait --wait-timeout 180
    ;;
  source)
    git pull --ff-only
    "${local_compose[@]}" up -d --build --wait --wait-timeout 180
    ;;
  release)
    "${release_compose[@]}" pull postgres backend frontend admin
    "${release_compose[@]}" up -d --no-build --wait --wait-timeout 180
    ;;
esac
echo 'Actualización terminada. El volumen de PostgreSQL y .env se han conservado.'
