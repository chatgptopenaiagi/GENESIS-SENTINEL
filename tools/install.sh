#!/bin/sh
set -eu
prefix="${HOME}/.local/share/genesis-sentinel/venv"
python_path="$(command -v python3 || true)"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix) [ "$#" -ge 2 ] || exit 2; prefix=$2; shift 2 ;;
    --python) [ "$#" -ge 2 ] || exit 2; python_path=$2; shift 2 ;;
    --help) printf '%s\n' 'Usage: ./install.sh [--python /absolute/python3] [--prefix /absolute/new/venv]'; exit 0 ;;
    *) printf '%s\n' "Unknown option: $1" >&2; exit 2 ;;
  esac
done
case "$prefix" in /*) ;; *) printf '%s\n' 'Prefix must be absolute.' >&2; exit 2 ;; esac
case "$python_path" in /*) ;; *) printf '%s\n' 'Select an existing absolute Python with --python.' >&2; exit 2 ;; esac
if [ -e "$prefix" ] || [ -L "$prefix" ]; then printf '%s\n' 'Refusing to overwrite an existing prefix.' >&2; exit 1; fi
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
set -- "$here"/genesis_arch_sentinel-0.1.0-*.whl
[ "$#" -eq 1 ] && [ -f "$1" ] || { printf '%s\n' 'Exactly one bundled wheel is required next to install.sh.' >&2; exit 1; }
wheel=$1
"$python_path" -m venv "$prefix"
"$prefix/bin/python" -m pip install --no-deps --no-index "$wheel"
printf '%s\n' "Installed Python wrappers in $prefix/bin" "Run: $prefix/bin/genesis-sentinel init" "Dashboard: $prefix/bin/genesis-sentinel-dashboard start"
