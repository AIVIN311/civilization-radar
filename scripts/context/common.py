"""Shared, standard-library-only helpers for non-canonical context artifacts."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, fieldnames, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_number(value):
    if value is None: return None
    text = str(value).strip().replace(",", "")
    if text in {"", "--", "---", "X", "N/A", "null"}: return None
    text = text.replace("−", "-")
    try: return float(text)
    except ValueError: return None


def iso_date(value):
    text = str(value).strip().replace("/", "-")
    parts = text.split("-")
    if len(parts) != 3: raise ValueError(f"invalid date: {value}")
    year = int(parts[0]); year = year + 1911 if year < 1911 else year
    return date(year, int(parts[1]), int(parts[2])).isoformat()


def atomic_replace_dir(staging, target):
    staging, target = Path(staging), Path(target)
    backup = target.with_name(target.name + ".previous")
    if backup.exists():
        import shutil; shutil.rmtree(backup)
    def replace_with_retry(source,destination):
        for attempt in range(5):
            try: os.replace(source,destination); return
            except PermissionError:
                if attempt == 4: raise
                time.sleep(.2 * (attempt + 1))
    if target.exists(): replace_with_retry(target, backup)
    try: replace_with_retry(staging, target)
    except Exception:
        if backup.exists() and not target.exists(): os.replace(backup, target)
        raise
    if backup.exists():
        import shutil; shutil.rmtree(backup)


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i]); out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]: j += 1
        rank = (i + j - 1) / 2 + 1
        for k in range(i, j): out[order[k]] = rank
        i = j
    return out


def pearson(xs, ys):
    if len(xs) < 3: return None
    mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
    dx, dy = [x-mx for x in xs], [y-my for y in ys]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    return None if den == 0 else sum(x*y for x,y in zip(dx,dy))/den


def spearman(xs, ys): return pearson(ranks(xs), ranks(ys))
