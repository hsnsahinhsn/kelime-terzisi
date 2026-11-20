#!/usr/bin/env bash
# Kelime Terzisi komutu: bu becerinin bulunduğu eklenti kökünden terzi paketini çalıştırır.
KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHONPATH="$KOK${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m terzi "$@"
