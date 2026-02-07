import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
SAMPLE = ROOT / "input" / "snapshots.sample.jsonl"


def run(cmd, env=None, expect=0):
    print(">>", " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT, env=env)
    if r.returncode != expect:
        raise SystemExit(f"command failed ({r.returncode}): {' '.join(cmd)}")


def mk_env(output_dir: Path):
    env = os.environ.copy()
    env["RADAR_OUTPUT_DIR"] = str(output_dir)
    env["RADAR_EVENT_HALF_LIFE_DAYS"] = "7"
    return env


def pipeline_run(output_dir: Path, input_path: Path):
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    env = mk_env(output_dir)
    run([PY, "scripts/apply_sql_migrations.py", "--output-dir", str(output_dir)], env=env)
    run([PY, "seed_from_snapshots.py", "--input", str(input_path), "--output-dir", str(output_dir)], env=env)
    run([PY, "upgrade_to_v02.py", "--output-dir", str(output_dir)], env=env)
    run(
        [
            PY,
            "scripts/derive_events_from_daily.py",
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
        ],
        env=env,
    )
    run([PY, "scripts/load_events_into_db.py", "--output-dir", str(output_dir)], env=env)
    run([PY, "build_chain_matrix_v10.py", "--half-life-days", "7", "--output-dir", str(output_dir)], env=env)
    run([PY, "upgrade_to_v03_chain.py", "--output-dir", str(output_dir)], env=env)
    run([PY, "render_dashboard_v02.py", "--half-life-days", "7", "--output-dir", str(output_dir)], env=env)
    run([PY, "scripts/eval_quality.py", "--missing-ratio-threshold", "0.0", "--output-dir", str(output_dir)], env=env)
    return output_dir / "radar.db"


def summarize_db(db_path: Path):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    summary = {
        "metrics_rows": cur.execute("SELECT COUNT(*) FROM metrics_v02").fetchone()[0],
        "events_rows": cur.execute("SELECT COUNT(*) FROM events_v01").fetchone()[0],
        "edges_rows": cur.execute("SELECT COUNT(*) FROM v03_chain_edges_latest").fetchone()[0],
        "series_rows": cur.execute("SELECT COUNT(*) FROM v03_series_chain_latest").fetchone()[0],
        "series_values": cur.execute(
            "SELECT GROUP_CONCAT(DISTINCT series) FROM metrics_v02"
        ).fetchone()[0],
        "top_event_strength": cur.execute(
            "SELECT COALESCE(MAX(strength),0.0) FROM events_v01"
        ).fetchone()[0],
        "top_delta_boost": cur.execute(
            "SELECT COALESCE(MAX(delta_boost),0.0) FROM v03_chain_edges_latest"
        ).fetchone()[0],
    }
    payload = json.dumps(summary, sort_keys=True).encode("utf-8")
    summary["hash"] = hashlib.sha256(payload).hexdigest()
    con.close()
    return summary


def assert_schema_fixed():
    out = ROOT / "output" / "accept_schema"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    messy = out / "messy.jsonl"
    rows = [
        {"domain": "m1.example", "series": "identity", "req": 10, "unknown_x": 1},
        {"ts": "2026-01-01T00:00:00+00:00", "series": "identity-data", "dns_total": 20, "domain": "m2.example"},
        {"ts": "2026-01-02T00:00:00+00:00", "domain": "m3.example", "series": "identity_data", "req": 30, "extra": "k"},
    ]
    with messy.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    env = mk_env(out)
    run([PY, "scripts/apply_sql_migrations.py", "--output-dir", str(out)], env=env)
    run([PY, "seed_from_snapshots.py", "--input", str(messy), "--output-dir", str(out)], env=env)
    con = sqlite3.connect(out / "radar.db")
    cur = con.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(snapshots_v01)").fetchall()]
    required = {
        "ts",
        "domain",
        "series",
        "req",
        "cf_served",
        "origin_served",
        "mitigated",
        "missing_fields_json",
        "extra_fields_json",
        "schema_version",
    }
    if not required.issubset(set(cols)):
        raise SystemExit("schema fixed check failed")
    markers = cur.execute(
        "SELECT COUNT(*) FROM snapshots_v01 WHERE missing_fields_json NOT IN ('[]','')"
    ).fetchone()[0]
    con.close()
    if markers <= 0:
        raise SystemExit("missing field marker check failed")


def assert_alias_and_strength(db_path: Path):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    values = {
        r[0]
        for r in cur.execute(
            "SELECT DISTINCT series FROM metrics_v02 WHERE domain LIKE 'identity-%'"
        ).fetchall()
    }
    if values != {"identity_data"}:
        raise SystemExit(f"alias check failed: {values}")
    rows = cur.execute(
        """
        SELECT domain, strength, strength_explain_json
        FROM events_v01
        WHERE domain IN ('identity-a.example','identity-b.example')
        ORDER BY domain
        """
    ).fetchall()
    as_map = {d: float(s or 0.0) for d, s, _ in rows}
    explain = {d: json.loads(j or "{}") for d, _, j in rows}
    if as_map.get("identity-b.example", 0.0) < as_map.get("identity-a.example", 0.0):
        raise SystemExit("cf vs origin strength ordering check failed")
    if explain.get("identity-b.example", {}).get("origin_amp", 0.0) <= explain.get("identity-a.example", {}).get("origin_amp", 0.0):
        raise SystemExit("cf vs origin explain gap check failed")
    con.close()


def assert_chain_explain_and_delta(db_path: Path):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    missing = cur.execute(
        """
        SELECT COUNT(*) FROM v03_chain_edges_latest
        WHERE src_event_decayed_strength IS NULL
           OR boost_multiplier IS NULL
           OR max_event_level IS NULL
        """
    ).fetchone()[0]
    if missing > 0:
        raise SystemExit("top-3 explain columns missing")
    neg = cur.execute("SELECT COUNT(*) FROM v03_chain_edges_latest WHERE delta_boost < 0").fetchone()[0]
    if neg > 0:
        raise SystemExit("delta_boost negative check failed")
    con.close()


def assert_half_life_sensitivity(output_dir: Path):
    con = sqlite3.connect(output_dir / "radar.db")
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO events_v01
        (ts,date,domain,series,event_type,req_key,baseline_avg,current,delta,ratio,strength,series_raw,event_level,matched_signals_json,strength_explain_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "2025-12-01T00:00:00Z",
            "2025-12-01",
            "identity-b.example",
            "identity_data",
            "spike",
            "dns_total",
            100.0,
            500.0,
            400.0,
            4.0,
            500.0,
            "identity_data",
            "L2",
            "[]",
            "{}",
        ),
    )
    con.commit()
    con.close()

    env = mk_env(output_dir)
    run([PY, "build_chain_matrix_v10.py", "--half-life-days", "3", "--output-dir", str(output_dir)], env=env)
    run([PY, "upgrade_to_v03_chain.py", "--output-dir", str(output_dir)], env=env)
    con = sqlite3.connect(output_dir / "radar.db")
    cur = con.cursor()
    short = cur.execute(
        "SELECT src_series, ROUND(SUM(src_event_decayed_strength),6) FROM v03_chain_edges_latest GROUP BY src_series ORDER BY 2 DESC"
    ).fetchall()
    con.close()

    run([PY, "build_chain_matrix_v10.py", "--half-life-days", "14", "--output-dir", str(output_dir)], env=env)
    run([PY, "upgrade_to_v03_chain.py", "--output-dir", str(output_dir)], env=env)
    con = sqlite3.connect(output_dir / "radar.db")
    cur = con.cursor()
    long = cur.execute(
        "SELECT src_series, ROUND(SUM(src_event_decayed_strength),6) FROM v03_chain_edges_latest GROUP BY src_series ORDER BY 2 DESC"
    ).fetchall()
    con.close()

    if short == long:
        raise SystemExit("half-life sensitivity check failed")


def assert_l3_consistency(db_path: Path):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    a = cur.execute("SELECT COUNT(*) FROM v02_domain_latest WHERE level_max='L3'").fetchone()[0]
    b = cur.execute("SELECT COUNT(*) FROM events_v01 WHERE event_level='L3'").fetchone()[0]
    c = cur.execute("SELECT COUNT(*) FROM v03_chain_edges_latest WHERE max_event_level='L3'").fetchone()[0]
    con.close()
    if not (a > 0 and b > 0 and c > 0):
        raise SystemExit("L3 consistency check failed")


def assert_eval_fail_on_bad_input():
    out = ROOT / "output" / "accept_bad"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(x) for x in SAMPLE.read_text(encoding="utf-8").splitlines() if x.strip()]
    # inject ts disorder for one domain
    for i, r in enumerate(rows):
        if r["domain"] == "identity-a.example" and r["date"] == "2026-01-02":
            rows[i]["ts"] = "2026-01-09T00:00:00+00:00"
    bad = out / "bad_ts.jsonl"
    with bad.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    env = mk_env(out)
    run([PY, "scripts/apply_sql_migrations.py", "--output-dir", str(out)], env=env)
    run([PY, "seed_from_snapshots.py", "--input", str(bad), "--output-dir", str(out)], env=env)
    run([PY, "upgrade_to_v02.py", "--output-dir", str(out)], env=env)
    run([PY, "scripts/derive_events_from_daily.py", "--input", str(bad), "--output-dir", str(out)], env=env)
    run([PY, "scripts/load_events_into_db.py", "--output-dir", str(out)], env=env)
    run([PY, "build_chain_matrix_v10.py", "--output-dir", str(out)], env=env)
    run([PY, "upgrade_to_v03_chain.py", "--output-dir", str(out)], env=env)
    r = subprocess.run(
        [PY, "scripts/eval_quality.py", "--missing-ratio-threshold", "0.0", "--output-dir", str(out)],
        cwd=ROOT,
        env=env,
    )
    if r.returncode == 0:
        raise SystemExit("eval gate should fail on bad ts order")


def main():
    assert_schema_fixed()

    run1 = ROOT / "output" / "accept_run1"
    run2 = ROOT / "output" / "accept_run2"
    db1 = pipeline_run(run1, SAMPLE)
    db2 = pipeline_run(run2, SAMPLE)

    s1 = summarize_db(db1)
    s2 = summarize_db(db2)
    if s1["hash"] != s2["hash"]:
        raise SystemExit("deterministic hash mismatch")

    assert_alias_and_strength(db1)
    assert_chain_explain_and_delta(db1)
    assert_l3_consistency(db1)
    assert_half_life_sensitivity(run1)
    assert_eval_fail_on_bad_input()

    print("=== v0.4 acceptance summary ===")
    print(json.dumps({"run1": s1, "run2": s2}, ensure_ascii=False, indent=2))
    print("PASS: v0.4 acceptance checks")


if __name__ == "__main__":
    main()
