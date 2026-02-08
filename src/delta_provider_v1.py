from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

from src.persistence_v1 import build_delta_series_from_db


_DEFAULT_ARTIFACT_GLOBS = [
    "derived/deltaT_v1_{token}.json",
    "derived/tag_vector_v1_{token}.json",
    "derived/tag_vector_v1_global.json",
    "derived/semantic_projection_v1_{token}.json",
    "derived/semantic_projection_v1_global.json",
]
_DEFAULT_ALLOWED_VERSIONS = ["deltaT_v1", "tag_vector_v1", "semantic_projection_v1"]
_EPS = 1e-12
_LAST_DELTA_META = {"delta_source_used": "fallback_db", "artifact_path": ""}


def _safe_profile_token(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "unknown"
    out = []
    for ch in raw:
        if ch.isalnum() or ch in ("_", "-"):
            out.append(ch)
        else:
            out.append("_")
    token = "".join(out).strip("_")
    return token or "unknown"


def _as_positive_int(value, default: int) -> int:
    try:
        num = int(value)
    except Exception:
        return int(default)
    return num if num > 0 else int(default)


def _as_string_list(value, default: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(default)
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out or list(default)


def _set_last_meta(source: str, artifact_path: str) -> None:
    global _LAST_DELTA_META
    _LAST_DELTA_META = {
        "delta_source_used": str(source or "fallback_db"),
        "artifact_path": str(artifact_path or ""),
    }


def get_last_delta_meta() -> dict[str, str]:
    return dict(_LAST_DELTA_META)


def _to_rel_path(path: Path, output_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(output_root.resolve())
        return rel.as_posix()
    except Exception:
        return path.name


def _load_json_obj(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _is_finite_number(value) -> bool:
    try:
        num = float(value)
    except Exception:
        return False
    return math.isfinite(num)


def _normalize_value(value) -> float:
    num = float(value)
    if not math.isfinite(num):
        raise ValueError("value must be finite")
    return num


def _is_global_geo(token: str) -> bool:
    return token == "global" or token.startswith("global_")


def _version_allowed(version_value, allowed_versions: set[str]) -> bool:
    version = str(version_value or "").strip()
    if not version:
        return False
    if not allowed_versions:
        return True
    return version in allowed_versions


def _tags_payload(payload: dict):
    for key in ("tags", "vectors", "series"):
        if key in payload:
            return payload.get(key)
    return None


def _parse_point(entry, value_keys: tuple[str, ...]) -> tuple[str, float]:
    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
        ts = str(entry[0] or "").strip()
        if not ts:
            raise ValueError("missing ts")
        return ts, _normalize_value(entry[1])

    if isinstance(entry, dict):
        ts = str(entry.get("ts") or entry.get("t") or "").strip()
        if not ts:
            raise ValueError("missing ts")
        value = None
        for key in value_keys:
            if key in entry:
                value = entry[key]
                break
        if value is None:
            raise ValueError("missing value")
        return ts, _normalize_value(value)

    raise ValueError("invalid point shape")


def _parse_series_entries(entries, value_keys: tuple[str, ...]) -> list[tuple[str, float]]:
    points: list[tuple[str, float]] = []
    if isinstance(entries, dict):
        for ts in sorted(entries.keys()):
            points.append((str(ts), _normalize_value(entries[ts])))
    elif isinstance(entries, list):
        for row in entries:
            points.append(_parse_point(row, value_keys))
    else:
        raise ValueError("series entries must be list or object")

    prev_ts = ""
    for ts, value in points:
        if not ts:
            raise ValueError("missing ts")
        if prev_ts and ts <= prev_ts:
            raise ValueError("ts must be strictly increasing")
        if not _is_finite_number(value):
            raise ValueError("value must be finite")
        prev_ts = ts
    return points


def _canonicalize_tags(tags_obj, value_keys: tuple[str, ...]) -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    if isinstance(tags_obj, dict):
        for tag in sorted(tags_obj.keys(), key=lambda x: str(x)):
            tag_name = str(tag or "").strip()
            if not tag_name:
                raise ValueError("empty tag")
            out[tag_name] = _parse_series_entries(tags_obj[tag], value_keys)
    elif isinstance(tags_obj, list):
        for row in tags_obj:
            if not isinstance(row, dict):
                raise ValueError("list tags entry must be object")
            tag_name = str(row.get("tag") or "").strip()
            if not tag_name:
                raise ValueError("missing tag")
            if tag_name in out:
                raise ValueError("duplicate tag")
            series_raw = None
            for key in ("series", "values", "points", "data"):
                if key in row:
                    series_raw = row.get(key)
                    break
            if series_raw is None and "ts" in row:
                series_raw = [row]
            out[tag_name] = _parse_series_entries(series_raw, value_keys)
    else:
        raise ValueError("tags must be object or list")

    canonical = {}
    for tag in sorted(out.keys()):
        series = out[tag]
        if not series:
            continue
        canonical[tag] = series
    if not canonical:
        raise ValueError("empty tag series")
    return canonical


def _series_ts_count(series_by_tag: dict[str, list[tuple[str, float]]]) -> int:
    ts_set: set[str] = set()
    for series in series_by_tag.values():
        for ts, _ in series:
            ts_set.add(str(ts))
    return len(ts_set)


def _series_by_tag_to_by_ts(series_by_tag: dict[str, list[tuple[str, float]]]) -> dict[str, dict[str, float]]:
    by_ts: dict[str, dict[str, float]] = {}
    for tag in sorted(series_by_tag.keys()):
        for ts, value in series_by_tag[tag]:
            by_ts.setdefault(str(ts), {})[tag] = float(value)
    return by_ts


def _compute_delta_from_vectors(
    geo_vectors: dict[str, list[tuple[str, float]]],
    base_vectors: dict[str, list[tuple[str, float]]],
    window: int,
) -> dict[str, list[tuple[str, float]]]:
    by_ts_geo = _series_by_tag_to_by_ts(geo_vectors)
    by_ts_base = _series_by_tag_to_by_ts(base_vectors)
    common_ts = sorted(set(by_ts_geo.keys()) & set(by_ts_base.keys()))
    if len(common_ts) < int(window):
        return {}

    all_tags = sorted(set(geo_vectors.keys()) | set(base_vectors.keys()))
    delta_by_tag: dict[str, list[tuple[str, float]]] = {tag: [] for tag in all_tags}
    for ts in common_ts:
        vec_geo = by_ts_geo.get(ts, {})
        vec_base = by_ts_base.get(ts, {})
        sum_geo = sum(float(v) for v in vec_geo.values())
        sum_base = sum(float(v) for v in vec_base.values())
        for tag in all_tags:
            geo_norm = float(vec_geo.get(tag, 0.0)) / sum_geo if sum_geo > _EPS else 0.0
            base_norm = float(vec_base.get(tag, 0.0)) / sum_base if sum_base > _EPS else 0.0
            delta_by_tag[tag].append((ts, geo_norm - base_norm))
    return delta_by_tag


def _collect_artifact_paths(output_root: Path, patterns: list[str], token: str) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for pattern in patterns:
        rendered = str(pattern or "").replace("{token}", token).replace("{geo}", token)
        if not rendered:
            continue
        for path in sorted(output_root.glob(rendered)):
            if not path.is_file() or path.suffix.lower() != ".json":
                continue
            try:
                key = str(path.resolve()).lower()
            except Exception:
                key = str(path).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(path)
    return out


def _looks_like_delta_artifact(path: Path) -> bool:
    name = path.name.lower()
    return "deltat" in name or "delta_t" in name


def _looks_like_vector_artifact(path: Path) -> bool:
    name = path.name.lower()
    return "tag_vector" in name or "semantic_projection" in name


def _load_delta_artifact(
    artifact_path: Path,
    geo: str,
    window: int,
    allowed_versions: set[str],
) -> dict[str, list[tuple[str, float]]] | None:
    payload = _load_json_obj(artifact_path)
    if not payload:
        return None
    if not _version_allowed(payload.get("version"), allowed_versions):
        return None
    geo_token = _safe_profile_token(payload.get("geo") or "")
    if geo_token != _safe_profile_token(geo):
        return None
    try:
        canonical = _canonicalize_tags(_tags_payload(payload), ("delta", "value", "v"))
    except Exception:
        return None
    if _series_ts_count(canonical) < int(window):
        return None
    return canonical


def _load_vector_artifact(
    artifact_path: Path,
    geo: str,
    allowed_versions: set[str],
    require_global: bool,
) -> dict[str, list[tuple[str, float]]] | None:
    payload = _load_json_obj(artifact_path)
    if not payload:
        return None
    if not _version_allowed(payload.get("version"), allowed_versions):
        return None

    geo_token = _safe_profile_token(payload.get("geo") or "")
    if require_global:
        if not _is_global_geo(geo_token):
            return None
    elif geo_token != _safe_profile_token(geo):
        return None

    try:
        return _canonicalize_tags(
            _tags_payload(payload),
            ("value", "v", "score", "weight", "delta"),
        )
    except Exception:
        return None


def _fallback_db(output_root: Path, cfg: dict) -> dict[str, list[tuple[str, float]]]:
    db_path = output_root / "radar.db"
    if not db_path.exists():
        return {}
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        return build_delta_series_from_db(cur, cfg)
    except Exception:
        return {}
    finally:
        con.close()


def get_delta_series(geo: str, window: int, output_dir: str, cfg: dict) -> dict[str, list[tuple[str, float]]]:
    """
    Return canonical delta series: {tag: [(ts, delta)]}.

    Artifact-first:
    1) direct delta artifact
    2) geo/global vector artifacts transformed to delta
    3) fallback DB minimal provider
    """
    output_root = Path(output_dir)
    window_int = _as_positive_int(window, 16)

    delta_cfg = cfg.get("delta_source") if isinstance(cfg.get("delta_source"), dict) else {}
    mode = str(delta_cfg.get("mode") or "artifact_first").strip().lower() or "artifact_first"
    artifact_globs = _as_string_list(delta_cfg.get("artifact_globs"), _DEFAULT_ARTIFACT_GLOBS)
    allowed_versions = set(_as_string_list(delta_cfg.get("allowed_versions"), _DEFAULT_ALLOWED_VERSIONS))

    if mode == "artifact_first":
        token = _safe_profile_token(geo)
        candidates = _collect_artifact_paths(output_root, artifact_globs, token)

        delta_candidates = [p for p in candidates if _looks_like_delta_artifact(p)]
        for artifact_path in delta_candidates:
            series = _load_delta_artifact(artifact_path, geo, window_int, allowed_versions)
            if series:
                _set_last_meta("artifact", _to_rel_path(artifact_path, output_root))
                return series

        vector_candidates = [p for p in candidates if _looks_like_vector_artifact(p)]
        geo_vectors = None
        geo_path = None
        for artifact_path in vector_candidates:
            loaded = _load_vector_artifact(artifact_path, geo, allowed_versions, require_global=False)
            if loaded:
                geo_vectors = loaded
                geo_path = artifact_path
                break

        global_vectors = None
        global_path = None
        for artifact_path in vector_candidates:
            if geo_path is not None and artifact_path == geo_path:
                continue
            loaded = _load_vector_artifact(artifact_path, geo, allowed_versions, require_global=True)
            if loaded:
                global_vectors = loaded
                global_path = artifact_path
                break

        if geo_vectors and global_vectors and geo_path and global_path:
            delta_series = _compute_delta_from_vectors(geo_vectors, global_vectors, window_int)
            if delta_series:
                rel_geo = _to_rel_path(geo_path, output_root)
                rel_global = _to_rel_path(global_path, output_root)
                _set_last_meta("artifact_vector", f"{rel_geo}|{rel_global}")
                return delta_series

    fallback_series = _fallback_db(output_root, cfg)
    _set_last_meta("fallback_db", "")
    return fallback_series


def get_tag_vector_series(geo: str, window: int, output_dir: str, cfg: dict) -> dict[str, list[tuple[str, float]]]:
    """
    Optional helper: return canonical tag vectors from geo artifact when present.
    """
    output_root = Path(output_dir)
    window_int = _as_positive_int(window, 16)

    delta_cfg = cfg.get("delta_source") if isinstance(cfg.get("delta_source"), dict) else {}
    artifact_globs = _as_string_list(delta_cfg.get("artifact_globs"), _DEFAULT_ARTIFACT_GLOBS)
    allowed_versions = set(_as_string_list(delta_cfg.get("allowed_versions"), _DEFAULT_ALLOWED_VERSIONS))

    token = _safe_profile_token(geo)
    candidates = _collect_artifact_paths(output_root, artifact_globs, token)
    vector_candidates = [p for p in candidates if _looks_like_vector_artifact(p)]
    for artifact_path in vector_candidates:
        series = _load_vector_artifact(artifact_path, geo, allowed_versions, require_global=False)
        if series and _series_ts_count(series) >= window_int:
            return series
    return {}
