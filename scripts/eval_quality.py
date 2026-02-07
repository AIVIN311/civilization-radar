import math
import sqlite3
from datetime import datetime, timedelta
from statistics import mean

DB_PATH = "radar.db"
TOP_K = 10
ALERT_A = 2.0


def parse_ts(ts_text):
    try:
        return datetime.fromisoformat(str(ts_text))
    except Exception:
        return None


def rank_map(values_desc):
    # values_desc: [(item, value), ...] already sorted DESC
    return {item: i + 1 for i, (item, _) in enumerate(values_desc)}


def spearman_from_rank_maps(r1, r2):
    common = sorted(set(r1.keys()) & set(r2.keys()))
    n = len(common)
    if n < 2:
        return None
    d2 = 0.0
    for k in common:
        d = float(r1[k] - r2[k])
        d2 += d * d
    return 1.0 - (6.0 * d2) / (n * (n * n - 1.0))


def load_domain_rows(cur):
    cols = {r[1] for r in cur.execute("PRAGMA table_info(metrics_v02)").fetchall()}
    if "level_max" not in cols and "level" not in cols and "lvl" not in cols:
        return []
    level_col = "level_max" if "level_max" in cols else ("level" if "level" in cols else "lvl")
    rows = cur.execute(
        f"""
        SELECT ts, domain, COALESCE(W,0.0) AS W, COALESCE(A,0.0) AS A, COALESCE({level_col}, '') AS level
        FROM metrics_v02
        """
    ).fetchall()
    return rows


def precision_at_k(cur, top_k=TOP_K):
    rows = load_domain_rows(cur)
    if not rows:
        return None

    by_ts = {}
    for ts, domain, w, a, level in rows:
        by_ts.setdefault(ts, []).append((domain, float(w or 0.0), float(a or 0.0), str(level or "")))

    scores = []
    for ts, items in by_ts.items():
        items = sorted(items, key=lambda x: x[1], reverse=True)[:top_k]
        if not items:
            continue
        hit = 0
        for _, _, a, level in items:
            if a >= ALERT_A or level in ("L2", "L3"):
                hit += 1
        scores.append(hit / float(len(items)))

    if not scores:
        return None
    return {
        "windows": len(scores),
        "top_k": top_k,
        "score": mean(scores),
    }


def event_hit_rate_24h(cur):
    # event -> whether same domain has elevated state within next 24h
    e_rows = cur.execute(
        """
        SELECT domain, date
        FROM events_v01
        WHERE domain IS NOT NULL AND date IS NOT NULL
        """
    ).fetchall()
    if not e_rows:
        return None

    m_rows = load_domain_rows(cur)
    by_domain = {}
    for ts, domain, _, a, level in m_rows:
        t = parse_ts(ts)
        if t is None:
            continue
        by_domain.setdefault(str(domain), []).append((t, float(a or 0.0), str(level or "")))
    for d in by_domain:
        by_domain[d].sort(key=lambda x: x[0])

    total = 0
    hit = 0
    for domain, d in e_rows:
        try:
            start = datetime.fromisoformat(str(d) + "T00:00:00+00:00")
        except Exception:
            continue
        end = start + timedelta(hours=24)
        total += 1
        found = False
        for t, a, level in by_domain.get(str(domain), []):
            if start <= t <= end and (a >= ALERT_A or level in ("L2", "L3")):
                found = True
                break
        if found:
            hit += 1

    if total == 0:
        return None
    return {
        "events": total,
        "hits": hit,
        "score": hit / float(total),
    }


def series_ranking_stability(cur):
    rows = cur.execute(
        """
        SELECT ts, series, AVG(COALESCE(W,0.0)) AS w_avg
        FROM metrics_v02
        GROUP BY ts, series
        """
    ).fetchall()
    if not rows:
        return None

    by_ts = {}
    for ts, s, w in rows:
        by_ts.setdefault(ts, []).append((str(s), float(w or 0.0)))

    ts_sorted = sorted(by_ts.keys(), key=lambda x: parse_ts(x) or datetime.min)
    if len(ts_sorted) < 2:
        return None

    rho_vals = []
    for i in range(1, len(ts_sorted)):
        prev_ts = ts_sorted[i - 1]
        cur_ts = ts_sorted[i]
        prev_rank = rank_map(sorted(by_ts[prev_ts], key=lambda x: x[1], reverse=True))
        now_rank = rank_map(sorted(by_ts[cur_ts], key=lambda x: x[1], reverse=True))
        rho = spearman_from_rank_maps(prev_rank, now_rank)
        if rho is not None:
            rho_vals.append(rho)

    if not rho_vals:
        return None
    return {
        "pairs": len(rho_vals),
        "score": mean(rho_vals),
    }


def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    p_at_k = precision_at_k(cur, top_k=TOP_K)
    hit_24h = event_hit_rate_24h(cur)
    rank_stability = series_ranking_stability(cur)

    con.close()

    print("=== Quality Report ===")
    if p_at_k is None:
        print("precision@K: n/a")
    else:
        print(
            f"precision@{p_at_k['top_k']}: {p_at_k['score']:.3f} "
            f"(windows={p_at_k['windows']})"
        )

    if hit_24h is None:
        print("event_hit_rate_24h: n/a")
    else:
        print(
            f"event_hit_rate_24h: {hit_24h['score']:.3f} "
            f"(hits={hit_24h['hits']}/{hit_24h['events']})"
        )

    if rank_stability is None:
        print("series_ranking_stability: n/a")
    else:
        print(
            f"series_ranking_stability: {rank_stability['score']:.3f} "
            f"(pairs={rank_stability['pairs']})"
        )


if __name__ == "__main__":
    main()
