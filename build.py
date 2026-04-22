#!/usr/bin/env python3
"""Construye el paquete .ankiaddon a partir de src/jisho_lookup/.

Uso:
    python3 build.py                       # -> dist/jisho_lookup-<version>.ankiaddon
    python3 build.py --out my.ankiaddon    # ruta de salida personalizada
    python3 build.py --plain               # nombre sin número de versión
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile


ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src", "jisho_lookup")
DIST = os.path.join(ROOT, "dist")

IGNORE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache"}
IGNORE_SUFFIXES = (".pyc", ".pyo")


def _read_version() -> str:
    with open(os.path.join(SRC, "manifest.json"), "r", encoding="utf-8") as f:
        return json.load(f)["human_version"]


def build(out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    files_written = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(SRC):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for fn in files:
                if fn.endswith(IGNORE_SUFFIXES):
                    continue
                full = os.path.join(root, fn)
                arc = os.path.relpath(full, SRC)
                # Normalizamos separadores para ZIP multiplataforma
                arc = arc.replace(os.sep, "/")
                z.write(full, arc)
                files_written += 1
    return out_path if files_written else ""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Construir .ankiaddon")
    parser.add_argument(
        "--out",
        help="Ruta de salida (por defecto dist/jisho_lookup-<version>.ankiaddon)",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Usar dist/jisho_lookup.ankiaddon sin número de versión",
    )
    args = parser.parse_args(argv)

    if not os.path.isdir(SRC):
        print(f"ERROR: no existe {SRC}", file=sys.stderr)
        return 1

    if args.out:
        out = args.out
    elif args.plain:
        out = os.path.join(DIST, "jisho_lookup.ankiaddon")
    else:
        version = _read_version()
        out = os.path.join(DIST, f"jisho_lookup-{version}.ankiaddon")

    built = build(out)
    if not built:
        print("ERROR: no se añadió ningún archivo", file=sys.stderr)
        return 2

    size_kb = os.path.getsize(built) / 1024
    print(f"Built {built}  ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
