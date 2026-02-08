from __future__ import annotations

import json
from pathlib import Path


DEFAULT_PERSISTENCE_CONFIG_PATH = Path("config") / "persistence_v1.json"
PERSISTENCE_VERSION = "persistence_v1"


def _table_exists(cur, name: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE (type='table' OR type='view') AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return bool(row)


def _as_positive_int(value, default: int) -> int:
    try:
        num = int(value)
    except Exception:
        return int(default)
    return num if num > 0 else int(default)


def _as_positive_float(value, default: float) -> float:
    try:
        num = float(value)
    except Exception:
        return float(default)
    return num if num > 0 else float(default)


def _sign(value: float, eps: float) -> int:
    if value > eps:
        return 1
    if value < -eps:
        return -1
    return 0


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def load_persistence_config(path: str | Path = DEFAULT_PERSISTENCE_CONFIG_PATH) -> dict:
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Missing persistence config: {resolved}")

    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if payload.get("version") != PERSISTENCE_VERSION:
        raise ValueError(
            f"Invalid persistence config version: {payload.get('version')!r}, expected '{PERSISTENCE_VERSION}'"
        )

    window = _as_positive_int(payload.get("window"), 16)
    alpha = _as_positive_float(payload.get("alpha"), 2.0 / (window + 1))
    eps = _as_positive_float(payload.get("eps"), 0.01)

    thresholds = payload.get("ers_thresholds") if isinstance(payload.get("ers_thresholds"), dict) else {}
    watch_p = float(thresholds.get("watch_p", 0.55))
    watch_streak = _as_positive_int(thresholds.get("watch_streak"), 3)
    eligible_p = float(thresholds.get("eligible_p", 0.70))
    eligible_streak = _as_positive_int(thresholds.get("eligible_streak"), 5)

    kernel_cfg = payload.get("kernel") if isinstance(payload.get("kernel"), dict) else {}
    top_k_domains = _as_positive_int(kernel_cfg.get("top_k_domains"), 3)

    if not (0.0 < alpha <= 1.0):
        raise ValueError("Invalid persistence config: alpha must be in (0,1]")
    if not (0.0 <= watch_p <= 1.0 and 0.0 <= eligible_p <= 1.0):
        raise ValueError("Invalid persistence config: p thresholds must be in [0,1]")
    if eligible_p < watch_p:
        raise ValueError("Invalid persistence config: eligible_p must be >= watch_p")
    if eligible_streak < watch_streak:
        raise ValueError("Invalid persistence config: eligible_streak must be >= watch_streak")

    return {
        "version": PERSISTENCE_VERSION,
        "window": int(window),
        "alpha": float(alpha),
        "eps": float(eps),
        "ers_thresholds": {
            "watch_p": float(watch_p),
            "watch_streak": int(watch_streak),
            "eligible_p": float(eligible_p),
            "eligible_streak": int(eligible_streak),
        },
        "kernel": {
            "top_k_domains": int(top_k_domains),
        },
    }


def build_delta_series_from_db(cur, cfg: dict) -> dict[str, list[tuple[str, float]]]:
    if not _table_exists(cur, "series_chain_v10"):
        return {}

    rows = cur.execute(
        """
        SELECT ts, series, COALESCE(tw_rank_score,0.0), COALESCE(boosted_push,0.0)
        FROM series_chain_v10
        ORDER BY ts ASC, series ASC
        """
    ).fetchall()
    if not rows:
        return {}

    by_ts_geo: dict[str, dict[str, float]] = {}
    by_ts_base: dict[str, dict[str, float]] = {}
    all_tags: set[str] = set()
    for ts, series, tw_rank_score, boosted_push in rows:
        ts_key = str(ts)
        tag = str(series)
        all_tags.add(tag)
        by_ts_geo.setdefault(ts_key, {})[tag] = float(tw_rank_score or 0.0)
        by_ts_base.setdefault(ts_key, {})[tag] = float(boosted_push or 0.0)

    delta_by_tag: dict[str, list[tuple[str, float]]] = {tag: [] for tag in sorted(all_tags)}
    ts_list = sorted(by_ts_geo.keys())
    for ts in ts_list:
        vec_geo = by_ts_geo.get(ts, {})
        vec_base = by_ts_base.get(ts, {})
        sum_geo = sum(float(v) for v in vec_geo.values())
        sum_base = sum(float(v) for v in vec_base.values())
        for tag in sorted(all_tags):
            geo_norm = float(vec_geo.get(tag, 0.0)) / sum_geo if sum_geo > 1e-12 else 0.0
            base_norm = float(vec_base.get(tag, 0.0)) / sum_base if sum_base > 1e-12 else 0.0
            delta_by_tag[tag].append((ts, geo_norm - base_norm))
    return delta_by_tag


def classify_ers(p: float, streak: int, cfg: dict) -> str:
    th = cfg["ers_thresholds"]
    if p >= th["eligible_p"] and streak >= th["eligible_streak"]:
        return "eligible"
    if p >= th["watch_p"] and streak >= th["watch_streak"]:
        return "watch"
    return "none"


def compute_tag_persistence(delta_series_by_tag: dict[str, list[tuple[str, float]]], cfg: dict) -> dict:
    window = int(cfg["window"])
    alpha = float(cfg["alpha"])
    eps = float(cfg["eps"])

    latest_ts = ""
    tags_out = []
    for tag in sorted(delta_series_by_tag.keys()):
        series = sorted(delta_series_by_tag.get(tag) or [], key=lambda x: x[0])
        if not series:
            continue
        latest_ts = max(latest_ts, str(series[-1][0]))

        m = 0.0
        m_values: list[float] = []
        for _, d in series:
            m = alpha * float(d) + (1.0 - alpha) * m
            m_values.append(m)

        latest_delta = float(series[-1][1])
        latest_m = float(m_values[-1])
        m_sign = _sign(latest_m, eps)

        window_series = series[-window:]
        same_sign_count = 0
        nonzero_count = 0
        for _, d in window_series:
            s = _sign(float(d), eps)
            if s != 0:
                nonzero_count += 1
            if m_sign != 0 and s == m_sign:
                same_sign_count += 1
        c_ratio = float(same_sign_count) / max(1, nonzero_count)

        p = _clamp01(abs(latest_m) / (abs(latest_m) + eps)) * c_ratio

        streak = 0
        if m_sign != 0:
            for _, d in reversed(series):
                if _sign(float(d), eps) == m_sign:
                    streak += 1
                else:
                    break

        if m_sign > 0:
            direction = "+"
        elif m_sign < 0:
            direction = "-"
        else:
            direction = "0"

        tags_out.append(
            {
                "tag": str(tag),
                "delta": float(latest_delta),
                "p": float(p),
                "dir": direction,
                "streak": int(streak),
                "ers": classify_ers(p, streak, cfg),
            }
        )

    tags_out.sort(key=lambda x: (-float(x["p"]), -abs(float(x["delta"])), str(x["tag"])))
    return {
        "version": PERSISTENCE_VERSION,
        "window": window,
        "latest_ts": latest_ts,
        "tags": tags_out,
    }


def _compute_ewma(values: list[float], alpha: float) -> list[float]:
    m = 0.0
    out = []
    for v in values:
        m = alpha * float(v) + (1.0 - alpha) * m
        out.append(m)
    return out


def compute_event_kernel(cur, latest_ts: str, cfg: dict) -> dict:
    if not _table_exists(cur, "metrics_v02"):
        return {
            "version": "event_kernel_v1",
            "window": int(cfg["window"]),
            "latest_ts": str(latest_ts or ""),
            "tags": [],
            "top_domains": [],
        }

    alpha = float(cfg["alpha"])
    eps = float(cfg["eps"])
    top_k = int(cfg["kernel"]["top_k_domains"])

    rows = cur.execute(
        """
        SELECT ts, domain, series, COALESCE(W,0.0)
        FROM metrics_v02
        ORDER BY ts ASC, series ASC, domain ASC
        """
    ).fetchall()

    by_key: dict[tuple[str, str], list[tuple[str, float]]] = {}
    active_latest: set[tuple[str, str]] = set()
    for ts, domain, series, w in rows:
        ts_key = str(ts)
        key = (str(series), str(domain))
        by_key.setdefault(key, []).append((ts_key, float(w or 0.0)))
        if ts_key == str(latest_ts):
            active_latest.add(key)

    tags_map: dict[str, list[dict]] = {}
    for (tag, domain), series in sorted(by_key.items(), key=lambda x: (x[0][0], x[0][1])):
        if active_latest and (tag, domain) not in active_latest:
            continue
        series_sorted = sorted(series, key=lambda x: x[0])
        values = [float(v) for _, v in series_sorted]
        ewma_values = _compute_ewma(values, alpha)
        kernel_latest = float(ewma_values[-1]) if ewma_values else 0.0

        if len(ewma_values) >= 2:
            deltas = [ewma_values[i] - ewma_values[i - 1] for i in range(1, len(ewma_values))]
            latest_diff = float(deltas[-1])
            diff_sign = _sign(latest_diff, eps)
            streak = 0
            if diff_sign != 0:
                for d in reversed(deltas):
                    if _sign(float(d), eps) == diff_sign:
                        streak += 1
                    else:
                        break
        else:
            diff_sign = 0
            streak = 0

        if diff_sign > 0:
            direction = "+"
        elif diff_sign < 0:
            direction = "-"
        else:
            direction = "0"

        tags_map.setdefault(tag, []).append(
            {
                "domain": str(domain),
                "kernel": kernel_latest,
                "dir": direction,
                "streak": int(streak),
            }
        )

    tags_out = []
    flattened = []
    for tag in sorted(tags_map.keys()):
        ranked = sorted(tags_map[tag], key=lambda x: (-abs(float(x["kernel"])), str(x["domain"])))
        top_domains = ranked[:top_k]
        tags_out.append({"tag": tag, "top_domains": top_domains})
        for item in top_domains:
            flattened.append(
                {
                    "tag": tag,
                    "domain": item["domain"],
                    "kernel": float(item["kernel"]),
                    "dir": item["dir"],
                    "streak": int(item["streak"]),
                }
            )

    return {
        "version": "event_kernel_v1",
        "window": int(cfg["window"]),
        "latest_ts": str(latest_ts or ""),
        "tags": tags_out,
        "top_domains": flattened,
    }
