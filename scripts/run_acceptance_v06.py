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
OUT_ROOT = REPO_ROOT / "output" / "acceptance_v06"
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


def check_chain_columns_contract(cur: sqlite3.Cursor) -> None:
    table = "v03_series_chain_latest"
    if not table_has_columns(cur, table, CHAIN_REQUIRED_COLUMNS):
        raise AssertionError(
            f"[FAIL] {table} missing required columns: {CHAIN_REQUIRED_COLUMNS}"
        )


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
    payload = json.loads(ssot.read_text(encoding="utf-8"))
    profiles = payload.get("profiles") if isinstance(payload, dict) else None
    if not isinstance(profiles, dict):
        raise AssertionError("[FAIL] invalid SSOT: profiles must be an object")
    profile = profiles.get("global_baseline")
    if not isinstance(profile, dict):
        raise AssertionError("[FAIL] missing profile: global_baseline")

    required = {
        "enabled": True,
        "kind": "baseline",
        "min_total": 200,
        "min_countries": 6,
        "cap_share": 0.18,
        "alpha": 0.25,
    }
    for k, v in required.items():
        got = profile.get(k)
        if got != v:
            raise AssertionError(
                f"[FAIL] global_baseline.{k} mismatch: expected={v!r}, got={got!r}"
            )


def check_expected_series(rows: list[dict], label: str) -> None:
    got = {r["series"] for r in rows}
    if not EXPECTED_SERIES.issubset(got):
        raise AssertionError(
            f"[FAIL] {label} missing expected series: {sorted(EXPECTED_SERIES - got)}; got={sorted(got)}"
        )


def check_profile_label(rows: list[dict], expected_profile: str, label: str) -> None:
    for row in rows:
        got = row["geo_profile"]
        if got != expected_profile:
            raise AssertionError(
                f"[FAIL] {label}:{row['series']} geo_profile mismatch: expected={expected_profile}, got={got}"
            )


def check_baseline_explain_schema(rows: list[dict], label: str) -> None:
    required = {
        "version",
        "profile",
        "kind",
        "total",
        "min_total",
        "min_countries",
        "cap_share",
        "alpha",
        "raw",
        "geo_factor",
        "gate",
        "baseline_vector",
        "notes",
    }
    for row in rows:
        geo = parse_json_safe(row["geo_factor_explain_json"], f"{label}:{row['series']}:geo")
        missing = [k for k in required if k not in geo]
        if missing:
            raise AssertionError(
                f"[FAIL] {label}:{row['series']} baseline explain missing keys: {missing}"
            )
        if geo.get("kind") != "baseline":
            raise AssertionError(
                f"[FAIL] {label}:{row['series']} expected kind=baseline, got={geo.get('kind')!r}"
            )
        gate = geo.get("gate")
        if not isinstance(gate, dict) or "passed" not in gate or "reason" not in gate:
            raise AssertionError(f"[FAIL] {label}:{row['series']} gate contract missing")

        baseline_vector = geo.get("baseline_vector")
        if not isinstance(baseline_vector, list):
            raise AssertionError(
                f"[FAIL] {label}:{row['series']} baseline_vector must be a list"
            )
        if len(baseline_vector) > 12:
            raise AssertionError(
                f"[FAIL] {label}:{row['series']} baseline_vector must be top-12 max"
            )

        if gate.get("passed") is True:
            if row["geo_factor"] != 1.0:
                raise AssertionError(
                    f"[FAIL] {label}:{row['series']} baseline geo_factor should be 1.0 on pass"
                )
            if not baseline_vector:
                raise AssertionError(
                    f"[FAIL] {label}:{row['series']} baseline_vector must be non-empty when gate passes"
                )
        else:
            if row["geo_factor"] != 0.0:
                raise AssertionError(
                    f"[FAIL] {label}:{row['series']} baseline geo_factor should be 0.0 on gate fail"
                )

        prev_bs = None
        prev_country = None
        for idx, item in enumerate(baseline_vector):
            if not isinstance(item, dict):
                raise AssertionError(
                    f"[FAIL] {label}:{row['series']} baseline_vector[{idx}] must be object"
                )
            for key in ("country", "count", "share", "share_capped", "baseline_share"):
                if key not in item:
                    raise AssertionError(
                        f"[FAIL] {label}:{row['series']} baseline_vector[{idx}] missing key {key}"
                    )
            bs = float(item["baseline_share"] or 0.0)
            country = str(item["country"] or "")
            if prev_bs is not None:
                if bs > prev_bs + 1e-12:
                    raise AssertionError(
                        f"[FAIL] {label}:{row['series']} baseline_vector not sorted desc by baseline_share"
                    )
                if abs(bs - prev_bs) <= 1e-12 and country < str(prev_country):
                    raise AssertionError(
                        f"[FAIL] {label}:{row['series']} baseline_vector tie-break should be country asc"
                    )
            prev_bs = bs
            prev_country = country


def check_tw_weighted_schema(rows: list[dict], label: str) -> None:
    for row in rows:
        geo = parse_json_safe(row["geo_factor_explain_json"], f"{label}:{row['series']}:geo")
        if geo.get("kind") == "baseline":
            raise AssertionError(
                f"[FAIL] {label}:{row['series']} tw explain should not be baseline kind"
            )
        if "matched" not in geo or "unmatched_top" not in geo:
            raise AssertionError(
                f"[FAIL] {label}:{row['series']} tw explain missing matched/unmatched_top"
            )
        baseline_vector = geo.get("baseline_vector")
        if isinstance(baseline_vector, list) and baseline_vector:
            raise AssertionError(
                f"[FAIL] {label}:{row['series']} tw explain should not contain populated baseline_vector"
            )


def check_none_zero_impact(rows: list[dict], label: str) -> None:
    for row in rows:
        assert_close(
            row["tw_rank_score"],
            row["boosted_push"],
            eps=1e-9,
            msg=f"{label}:{row['series']} tw_rank_score should equal boosted_push",
        )
        assert_close(
            row["geo_factor"],
            0.0,
            eps=1e-12,
            msg=f"{label}:{row['series']} geo_factor should be 0 for none",
        )
        geo = parse_json_safe(row["geo_factor_explain_json"], f"{label}:{row['series']}:geo")
        gate = geo.get("gate")
        if not isinstance(gate, dict) or gate.get("passed") is not False:
            raise AssertionError(
                f"[FAIL] {label}:{row['series']} none profile must have gate passed=false"
            )
        baseline_vector = geo.get("baseline_vector")
        if baseline_vector not in (None, []):
            raise AssertionError(
                f"[FAIL] {label}:{row['series']} none profile baseline_vector must be empty/absent"
            )


def signature(rows: list[dict], label: str) -> dict[str, tuple[float, bool, str, str]]:
    sig = {}
    for row in rows:
        geo = parse_json_safe(row["geo_factor_explain_json"], f"{label}:{row['series']}:geo")
        gate = geo.get("gate") if isinstance(geo.get("gate"), dict) else {}
        gate_passed = bool(gate.get("passed")) if "passed" in gate else False
        gate_reason = str(gate.get("reason") or "unknown")
        baseline_vector = geo.get("baseline_vector")
        if not isinstance(baseline_vector, list):
            baseline_vector = []
        baseline_key = json.dumps(baseline_vector, ensure_ascii=False, sort_keys=True)
        sig[row["series"]] = (
            float(row["geo_factor"]),
            gate_passed,
            gate_reason,
            baseline_key,
        )
    return sig


def check_global_baseline_deterministic(
    sig_a: dict[str, tuple[float, bool, str, str]],
    sig_b: dict[str, tuple[float, bool, str, str]],
) -> None:
    if sig_a.keys() != sig_b.keys():
        raise AssertionError("[FAIL] baseline deterministic check: series sets differ")
    for series in sorted(sig_a.keys()):
        if sig_a[series] != sig_b[series]:
            raise AssertionError(
                f"[FAIL] baseline deterministic mismatch for {series}: {sig_a[series]} != {sig_b[series]}"
            )


def _has_signature_diff(
    left: dict[str, tuple[float, bool, str, str]],
    right: dict[str, tuple[float, bool, str, str]],
) -> bool:
    common = sorted(set(left.keys()) & set(right.keys()))
    for series in common:
        if left[series] != right[series]:
            return True
    return False


def check_scenario_difference(
    sig_baseline: dict[str, tuple[float, bool, str, str]],
    sig_tw: dict[str, tuple[float, bool, str, str]],
    sig_none: dict[str, tuple[float, bool, str, str]],
) -> None:
    has_gate_passed = any(v[1] is True for v in sig_baseline.values())
    has_nonempty_vector = any(v[3] not in ("[]", "") for v in sig_baseline.values())
    if not has_gate_passed or not has_nonempty_vector:
        raise AssertionError(
            "[FAIL] global_baseline scenario must contain gate=true rows with non-empty baseline_vector"
        )
    if not _has_signature_diff(sig_baseline, sig_tw):
        raise AssertionError("[FAIL] scenario difference: global_baseline and tw are identical")
    if not _has_signature_diff(sig_baseline, sig_none):
        raise AssertionError("[FAIL] scenario difference: global_baseline and none are identical")


def extract_v04_summary_hash(stdout_text: str) -> str:
    matches = re.findall(r'"hash"\s*:\s*"([0-9a-fA-F]{64})"', stdout_text)
    if len(matches) < 2:
        raise AssertionError(
            "[FAIL] could not extract run1/run2 hash from run_acceptance_v04 output"
        )
    unique = {m.lower() for m in matches}
    if len(unique) != 1:
        raise AssertionError(
            f"[FAIL] run_acceptance_v04 produced inconsistent hashes: {sorted(unique)}"
        )
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


def check_v05_regression() -> None:
    cmd = [PY, "scripts/run_acceptance_v05.py", "--skip-v04-hash"]
    print(">>", " ".join(cmd))
    try:
        subprocess.check_output(cmd, cwd=str(REPO_ROOT), text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        out = e.output or ""
        snippet = out[-2000:] if out else "<no stdout>"
        raise AssertionError(
            f"[FAIL] run_acceptance_v05 regression check failed (exit={e.returncode})\n{snippet}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-v04-hash", action="store_true")
    parser.add_argument("--skip-v05", action="store_true")
    parser.add_argument("--output-root", default=str(OUT_ROOT.relative_to(REPO_ROOT)))
    args = parser.parse_args()

    input_sample = INPUT_SAMPLE
    if not input_sample.exists():
        raise SystemExit(f"missing input sample: {input_sample}")

    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = (REPO_ROOT / output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    print("\n[v0.6 Acceptance] start\n")
    check_ssot_exists()

    db_base_a = run_pipeline("global_baseline", "geo_global_baseline_a", input_sample, output_root)
    rows_base_a = fetch_chain_rows(db_base_a)
    check_expected_series(rows_base_a, "global_baseline_a")
    check_profile_label(rows_base_a, "global_baseline", "global_baseline_a")
    check_baseline_explain_schema(rows_base_a, "global_baseline_a")
    sig_base_a = signature(rows_base_a, "global_baseline_a")
    print(f"[OK] scenario=global_baseline_a rows={len(rows_base_a)}")

    db_base_b = run_pipeline("global_baseline", "geo_global_baseline_b", input_sample, output_root)
    rows_base_b = fetch_chain_rows(db_base_b)
    check_expected_series(rows_base_b, "global_baseline_b")
    check_profile_label(rows_base_b, "global_baseline", "global_baseline_b")
    check_baseline_explain_schema(rows_base_b, "global_baseline_b")
    sig_base_b = signature(rows_base_b, "global_baseline_b")
    check_global_baseline_deterministic(sig_base_a, sig_base_b)
    print(f"[OK] scenario=global_baseline_b rows={len(rows_base_b)} (deterministic)")

    db_tw = run_pipeline("tw", "geo_tw", input_sample, output_root)
    rows_tw = fetch_chain_rows(db_tw)
    check_expected_series(rows_tw, "tw")
    check_profile_label(rows_tw, "tw", "tw")
    check_tw_weighted_schema(rows_tw, "tw")
    sig_tw = signature(rows_tw, "tw")
    print(f"[OK] scenario=tw rows={len(rows_tw)}")

    db_none = run_pipeline("none", "geo_none", input_sample, output_root)
    rows_none = fetch_chain_rows(db_none)
    check_expected_series(rows_none, "none")
    check_profile_label(rows_none, "none", "none")
    check_none_zero_impact(rows_none, "none")
    sig_none = signature(rows_none, "none")
    print(f"[OK] scenario=none rows={len(rows_none)}")

    check_scenario_difference(sig_base_a, sig_tw, sig_none)
    print("[OK] scenario difference check")

    if not args.skip_v05:
        check_v05_regression()
        print("[OK] v0.5 acceptance regression check confirmed")
    else:
        print("[SKIP] v0.5 acceptance regression check")

    if not args.skip_v04_hash:
        check_v04_non_interference()
        print("[OK] v0.4 non-interference summary hash confirmed")
    else:
        print("[SKIP] v0.4 non-interference summary hash check")

    print("\n[PASS] v0.6 acceptance\n")


if __name__ == "__main__":
    main()
