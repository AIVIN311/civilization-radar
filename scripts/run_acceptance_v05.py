from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
INPUT_SAMPLE = REPO_ROOT / "input" / "snapshots.geo.sample.jsonl"
OUT_ROOT = REPO_ROOT / "output" / "acceptance_v05"
EXPECTED_V04_SUMMARY_HASH = "73040be047b87d6638347a2dca4f9ba4a39490fd8c615d679695752b635dd235"
EXPECTED_SERIES = {
    "identity_data",
    "algorithmic_governance",
    "monetary_infrastructure",
}
CHAIN_REQUIRED_COLUMNS = [
    "series",
    "boosted_push",
    "geo_profile",
    "geo_factor",
    "tw_rank_score",
    "geo_factor_explain_json",
    "tw_rank_explain_json",
]


def sh(cmd: list[str]) -> None:
    print(">>", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(REPO_ROOT))


def parse_json_safe(raw: str, label: str) -> dict:
    try:
        payload = json.loads(raw)
    except Exception as e:
        snippet = raw[:500].replace("\n", "\\n")
        raise AssertionError(f"[FAIL] invalid JSON for {label}: {e}; raw={snippet}")
    if not isinstance(payload, dict):
        raise AssertionError(f"[FAIL] {label} must be a JSON object")
    return payload


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception as e:
            raise AssertionError(f"[FAIL] invalid jsonl at {path}:{i}: {e}")
        if not isinstance(obj, dict):
            raise AssertionError(f"[FAIL] jsonl row must be object at {path}:{i}")
        rows.append(obj)
    return rows


def assert_close(a: float, b: float, eps: float, msg: str) -> None:
    if abs(float(a) - float(b)) > eps:
        raise AssertionError(f"[FAIL] {msg}: {a} != {b} (eps={eps})")


def table_has_columns(cur: sqlite3.Cursor, table: str, cols: list[str]) -> bool:
    info = cur.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {r[1] for r in info}
    return all(c in existing for c in cols)


def _on_rm_error(func, path, _exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    func(path)


def safe_rmtree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, onerror=_on_rm_error)


def fetch_chain_rows(db_path: Path) -> list[dict]:
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    check_chain_columns_contract(cur)
    rows = cur.execute(
        """
        SELECT
          series,
          boosted_push,
          geo_profile,
          geo_factor,
          tw_rank_score,
          geo_factor_explain_json,
          tw_rank_explain_json
        FROM v03_series_chain_latest
        ORDER BY W_proj DESC, W_avg DESC
        """
    ).fetchall()
    con.close()
    out = []
    for r in rows:
        out.append(
            {
                "series": str(r[0]),
                "boosted_push": float(r[1] or 0.0),
                "geo_profile": str(r[2] or ""),
                "geo_factor": float(r[3] or 0.0),
                "tw_rank_score": float(r[4] or 0.0),
                "geo_factor_explain_json": str(r[5] or "{}"),
                "tw_rank_explain_json": str(r[6] or "{}"),
            }
        )
    return out


def check_chain_columns_contract(cur: sqlite3.Cursor) -> None:
    table = "v03_series_chain_latest"
    if not table_has_columns(cur, table, CHAIN_REQUIRED_COLUMNS):
        raise AssertionError(
            f"[FAIL] {table} missing required columns: {CHAIN_REQUIRED_COLUMNS}"
        )


def run_pipeline(profile: str, run_tag: str, input_sample: Path, output_root: Path) -> Path:
    out_dir = output_root / run_tag
    safe_rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sh(
        [
            PY,
            "run_pipeline_50.py",
            "--output-dir",
            str(out_dir),
            "--half-life-days",
            "7",
            "--geo-profile",
            profile,
            "--input-snapshots",
            str(input_sample),
        ]
    )
    db_path = out_dir / "latest" / "radar.db"
    if not db_path.exists():
        raise AssertionError(f"[FAIL] missing db: {db_path}")
    return db_path


def check_ssot_exists() -> None:
    ssot = REPO_ROOT / "config" / "geo_profiles_v1.json"
    if not ssot.exists():
        raise AssertionError("[FAIL] missing SSOT file: config/geo_profiles_v1.json")


def check_input_sample_contract(input_sample: Path) -> None:
    rows = read_jsonl(input_sample)
    if not rows:
        raise AssertionError(f"[FAIL] input sample is empty: {input_sample}")
    required_series = EXPECTED_SERIES
    required_prefixes = ("tw-", "nearby-", "none-")
    seen_series = {str(r.get("series", "")).strip() for r in rows}
    if not required_series.issubset(seen_series):
        missing = sorted(required_series - seen_series)
        raise AssertionError(f"[FAIL] input sample missing required series: {missing}")
    seen_prefix = {p: False for p in required_prefixes}
    for r in rows:
        domain = str(r.get("domain", "")).strip()
        for p in required_prefixes:
            if domain.startswith(p):
                seen_prefix[p] = True
    missing_prefix = [p for p, ok in seen_prefix.items() if not ok]
    if missing_prefix:
        raise AssertionError(
            f"[FAIL] input sample missing scenario domains with prefixes: {missing_prefix}"
        )


def check_explain_schema(rows: list[dict], label: str) -> None:
    geo_keys = {
        "version",
        "profile",
        "total",
        "min_total",
        "cap_share",
        "alpha",
        "raw",
        "geo_factor",
        "gate",
        "matched",
        "unmatched_top",
    }
    tw_keys = {
        "version",
        "boosted_score",
        "geo_factor",
        "multiplier",
        "tw_rank_score",
        "formula",
        "base_metric",
        "reason",
    }
    for row in rows:
        geo = parse_json_safe(row["geo_factor_explain_json"], f"{label}:{row['series']}:geo")
        tw = parse_json_safe(row["tw_rank_explain_json"], f"{label}:{row['series']}:tw")
        missing_geo = [k for k in geo_keys if k not in geo]
        missing_tw = [k for k in tw_keys if k not in tw]
        if missing_geo:
            raise AssertionError(
                f"[FAIL] {label}:{row['series']} geo explain missing keys: {missing_geo}"
            )
        if missing_tw:
            raise AssertionError(
                f"[FAIL] {label}:{row['series']} tw explain missing keys: {missing_tw}"
            )
        gate_obj = geo.get("gate")
        if not isinstance(gate_obj, dict) or "passed" not in gate_obj:
            raise AssertionError(f"[FAIL] {label}:{row['series']} gate contract missing")


def check_expected_series(rows: list[dict], label: str) -> None:
    got = {r["series"] for r in rows}
    if not EXPECTED_SERIES.issubset(got):
        raise AssertionError(
            f"[FAIL] {label} missing expected series: {sorted(EXPECTED_SERIES - got)}; got={sorted(got)}"
        )


def check_none_zero_impact(rows: list[dict]) -> None:
    for row in rows:
        assert_close(
            row["tw_rank_score"],
            row["boosted_push"],
            eps=1e-9,
            msg=f"profile=none tw_rank_score should equal boosted_push ({row['series']})",
        )


def signature(rows: list[dict]) -> dict[str, tuple[float, float, str]]:
    sig = {}
    for row in rows:
        geo_obj = parse_json_safe(row["geo_factor_explain_json"], f"signature:{row['series']}")
        gate = "unknown"
        gate_obj = geo_obj.get("gate")
        if isinstance(gate_obj, dict):
            if gate_obj.get("passed") is True:
                gate = "true"
            elif gate_obj.get("passed") is False:
                gate = "false"
        sig[row["series"]] = (row["geo_factor"], row["tw_rank_score"], gate)
    return sig


def check_deterministic_tw(sig_a: dict, sig_b: dict) -> None:
    if sig_a.keys() != sig_b.keys():
        raise AssertionError("[FAIL] deterministic tw check: series sets differ")
    for series in sorted(sig_a.keys()):
        a = sig_a[series]
        b = sig_b[series]
        if abs(a[0] - b[0]) > 1e-12 or abs(a[1] - b[1]) > 1e-12 or a[2] != b[2]:
            raise AssertionError(
                f"[FAIL] deterministic tw mismatch for {series}: first={a}, second={b}"
            )


def _has_vector_diff(left: dict, right: dict, eps: float = 1e-12) -> bool:
    common = sorted(set(left.keys()) & set(right.keys()))
    for series in common:
        la = left[series]
        rb = right[series]
        if abs(la[0] - rb[0]) > eps:
            return True
        if abs(la[1] - rb[1]) > eps:
            return True
        if la[2] != rb[2]:
            return True
    return False


def check_scenario_difference_medium(sig_tw: dict, sig_nearby: dict, sig_none: dict) -> None:
    if not _has_vector_diff(sig_tw, sig_none):
        raise AssertionError("[FAIL] scenario diff check: tw and none are identical")
    if not _has_vector_diff(sig_nearby, sig_none):
        raise AssertionError("[FAIL] scenario diff check: nearby and none are identical")
    if not _has_vector_diff(sig_tw, sig_nearby):
        raise AssertionError("[FAIL] scenario diff check: tw and nearby are identical")


def extract_v04_summary_hash(stdout_text: str) -> str:
    matches = re.findall(r'"hash"\s*:\s*"([0-9a-fA-F]{64})"', stdout_text)
    if len(matches) < 2:
        raise AssertionError("[FAIL] could not extract run1/run2 hash from run_acceptance_v04 output")
    unique = {m.lower() for m in matches}
    if len(unique) != 1:
        raise AssertionError(f"[FAIL] run_acceptance_v04 produced inconsistent hashes: {sorted(unique)}")
    return next(iter(unique))


def check_v04_non_interference() -> None:
    cmd = [PY, "scripts/run_acceptance_v04.py"]
    print(">>", " ".join(cmd))
    attempts = 4
    out = ""
    for i in range(1, attempts + 1):
        try:
            out = subprocess.check_output(
                cmd, cwd=str(REPO_ROOT), text=True, stderr=subprocess.STDOUT
            )
            break
        except subprocess.CalledProcessError as e:
            out = e.output or ""
            lock_hint = "WinError 32" in out or "PermissionError" in out
            if i < attempts and lock_hint:
                wait_sec = i
                print(
                    f"[WARN] run_acceptance_v04 transient lock detected, retrying "
                    f"({i}/{attempts}) after {wait_sec}s"
                )
                time.sleep(wait_sec)
                continue
            snippet = out[-2000:] if out else "<no stdout>"
            raise AssertionError(
                f"[FAIL] run_acceptance_v04 failed with exit code {e.returncode}\n{snippet}"
            )
    summary_hash = extract_v04_summary_hash(out)
    if summary_hash != EXPECTED_V04_SUMMARY_HASH:
        raise AssertionError(
            "[FAIL] v0.4 acceptance summary hash changed: "
            f"expected={EXPECTED_V04_SUMMARY_HASH}, got={summary_hash}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-v04-hash", action="store_true")
    parser.add_argument("--output-root", default=str(OUT_ROOT.relative_to(REPO_ROOT)))
    args = parser.parse_args()

    input_sample = INPUT_SAMPLE
    if not input_sample.exists():
        raise SystemExit(f"missing input sample: {input_sample}")
    check_input_sample_contract(input_sample)

    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = (REPO_ROOT / output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    print("\n[PR-4 Acceptance v0.5] start\n")
    check_ssot_exists()

    db_tw_a = run_pipeline("tw", "geo_tw_a", input_sample, output_root)
    rows_tw_a = fetch_chain_rows(db_tw_a)
    check_expected_series(rows_tw_a, "tw_a")
    check_explain_schema(rows_tw_a, "tw_a")
    sig_tw_a = signature(rows_tw_a)
    print(f"[OK] scenario=tw_a rows={len(rows_tw_a)}")

    db_tw_b = run_pipeline("tw", "geo_tw_b", input_sample, output_root)
    rows_tw_b = fetch_chain_rows(db_tw_b)
    check_expected_series(rows_tw_b, "tw_b")
    check_explain_schema(rows_tw_b, "tw_b")
    sig_tw_b = signature(rows_tw_b)
    check_deterministic_tw(sig_tw_a, sig_tw_b)
    print(f"[OK] scenario=tw_b rows={len(rows_tw_b)} (deterministic)")

    db_nearby = run_pipeline("nearby", "geo_nearby", input_sample, output_root)
    rows_nearby = fetch_chain_rows(db_nearby)
    check_expected_series(rows_nearby, "nearby")
    check_explain_schema(rows_nearby, "nearby")
    sig_nearby = signature(rows_nearby)
    print(f"[OK] scenario=nearby rows={len(rows_nearby)}")

    db_none = run_pipeline("none", "geo_none", input_sample, output_root)
    rows_none = fetch_chain_rows(db_none)
    check_expected_series(rows_none, "none")
    check_explain_schema(rows_none, "none")
    check_none_zero_impact(rows_none)
    sig_none = signature(rows_none)
    print(f"[OK] scenario=none rows={len(rows_none)} (zero-impact confirmed)")

    check_scenario_difference_medium(sig_tw_a, sig_nearby, sig_none)
    print("[OK] scenario difference check (medium strict)")

    if not args.skip_v04_hash:
        check_v04_non_interference()
        print("[OK] v0.4 non-interference summary hash confirmed")
    else:
        print("[SKIP] v0.4 non-interference summary hash check")

    print("\n[PASS] PR-4 acceptance v0.5\n")


if __name__ == "__main__":
    main()
