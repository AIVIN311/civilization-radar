from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.persistence_v1 import compute_tag_persistence, load_persistence_config

PY = sys.executable
INPUT_SAMPLE = REPO_ROOT / "input" / "snapshots.geo.sample.jsonl"
OUT_ROOT = REPO_ROOT / "output" / "acceptance_v07"
EXPECTED_V04_SUMMARY_HASH = "73040be047b87d6638347a2dca4f9ba4a39490fd8c615d679695752b635dd235"
FORBIDDEN_CORE_FILES = [
    REPO_ROOT / "build_chain_matrix_v10.py",
    REPO_ROOT / "src" / "event_strength.py",
    REPO_ROOT / "src" / "chain_event_boost.py",
]


def sh(cmd: list[str]) -> None:
    print(">>", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(REPO_ROOT))


def parse_json_safe(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"[FAIL] invalid JSON ({label}): {e}\npath={path}")
    if not isinstance(payload, dict):
        raise AssertionError(f"[FAIL] {label} must be a JSON object: path={path}")
    return payload


def _on_rm_error(func, path, _exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    func(path)


def safe_rmtree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, onerror=_on_rm_error)


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
    latest = out_dir / "latest"
    if not latest.exists():
        raise AssertionError(f"[FAIL] missing latest output dir: {latest}")
    return latest


def load_derived_payloads(latest_dir: Path, profile: str) -> tuple[dict, dict, str, str]:
    token = _safe_profile_token(profile)
    persistence_path = latest_dir / "derived" / f"persistence_v1_{token}.json"
    kernel_path = latest_dir / "derived" / f"event_kernel_v1_{token}.json"
    if not persistence_path.exists():
        raise AssertionError(f"[FAIL] missing persistence derived file: {persistence_path}")
    if not kernel_path.exists():
        raise AssertionError(f"[FAIL] missing event kernel derived file: {kernel_path}")

    persistence_raw = persistence_path.read_text(encoding="utf-8")
    kernel_raw = kernel_path.read_text(encoding="utf-8")
    persistence = parse_json_safe(persistence_path, "persistence")
    kernel = parse_json_safe(kernel_path, "event_kernel")
    return persistence, kernel, persistence_raw, kernel_raw


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def check_schema_acceptance(persistence: dict, kernel: dict, cfg: dict, label: str) -> None:
    if "persistence_v1" not in persistence or not isinstance(persistence["persistence_v1"], dict):
        raise AssertionError(f"[FAIL] {label}: missing persistence_v1 object")
    p = persistence["persistence_v1"]
    if int(p.get("window") or -1) != int(cfg["window"]):
        raise AssertionError(
            f"[FAIL] {label}: persistence window mismatch expected={cfg['window']} got={p.get('window')}"
        )
    tags = p.get("tags")
    if not isinstance(tags, list):
        raise AssertionError(f"[FAIL] {label}: persistence tags must be a list")
    for i, row in enumerate(tags):
        if not isinstance(row, dict):
            raise AssertionError(f"[FAIL] {label}: tags[{i}] must be object")
        for key in ("tag", "delta", "p", "dir", "streak", "ers"):
            if key not in row:
                raise AssertionError(f"[FAIL] {label}: tags[{i}] missing key '{key}'")
        p_val = float(row["p"])
        if not (0.0 <= p_val <= 1.0):
            raise AssertionError(f"[FAIL] {label}: tags[{i}].p out of range [0,1], got {p_val}")
        ers = str(row["ers"])
        if ers not in {"none", "watch", "eligible"}:
            raise AssertionError(f"[FAIL] {label}: invalid ers value '{ers}'")

    if "event_kernel_v1" not in kernel or not isinstance(kernel["event_kernel_v1"], dict):
        raise AssertionError(f"[FAIL] {label}: missing event_kernel_v1 object")
    k = kernel["event_kernel_v1"]
    if int(k.get("window") or -1) != int(cfg["window"]):
        raise AssertionError(
            f"[FAIL] {label}: kernel window mismatch expected={cfg['window']} got={k.get('window')}"
        )
    tags_block = k.get("tags")
    if not isinstance(tags_block, list):
        raise AssertionError(f"[FAIL] {label}: event_kernel_v1.tags must be a list")
    for i, row in enumerate(tags_block):
        if not isinstance(row, dict) or "tag" not in row or "top_domains" not in row:
            raise AssertionError(f"[FAIL] {label}: event_kernel_v1.tags[{i}] invalid")
        top_domains = row["top_domains"]
        if not isinstance(top_domains, list):
            raise AssertionError(f"[FAIL] {label}: top_domains must be list")
        if len(top_domains) > int(cfg["kernel"]["top_k_domains"]):
            raise AssertionError(
                f"[FAIL] {label}: top_domains exceeds top_k={cfg['kernel']['top_k_domains']}"
            )
        for j, d in enumerate(top_domains):
            if not isinstance(d, dict):
                raise AssertionError(f"[FAIL] {label}: top_domains[{j}] must be object")
            for key in ("domain", "kernel", "dir", "streak"):
                if key not in d:
                    raise AssertionError(f"[FAIL] {label}: top_domains[{j}] missing '{key}'")


def check_none_behavior(persistence_none: dict) -> None:
    for row in persistence_none.get("persistence_v1", {}).get("tags", []):
        p_val = float(row.get("p") or 0.0)
        ers = str(row.get("ers") or "none")
        if p_val > 1e-9:
            raise AssertionError(
                f"[FAIL] none profile should produce ~0 persistence, got p={p_val} tag={row.get('tag')}"
            )
        if ers != "none":
            raise AssertionError(
                f"[FAIL] none profile should not produce watch/eligible, got ers={ers} tag={row.get('tag')}"
            )


def check_deterministic_acceptance(
    p_raw_a: str, p_raw_b: str, k_raw_a: str, k_raw_b: str
) -> None:
    if hash_text(p_raw_a) != hash_text(p_raw_b):
        raise AssertionError("[FAIL] persistence derived output hash mismatch across deterministic runs")
    if hash_text(k_raw_a) != hash_text(k_raw_b):
        raise AssertionError("[FAIL] event kernel derived output hash mismatch across deterministic runs")


def check_isolation_acceptance() -> None:
    forbidden_tokens = ("persistence_v1", "event_kernel_v1")
    for path in FORBIDDEN_CORE_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                raise AssertionError(
                    f"[FAIL] isolation check: token '{token}' found in forbidden core file {path}"
                )


def check_behavioral_acceptance(cfg: dict) -> None:
    synthetic = {
        "tag_a": [
            ("t01", 0.00),
            ("t02", 0.06),
            ("t03", 0.06),
            ("t04", 0.06),
            ("t05", 0.06),
            ("t06", 0.06),
        ],
        "tag_b": [
            ("t01", 0.00),
            ("t02", 0.00),
            ("t03", 0.20),
            ("t04", 0.00),
            ("t05", 0.00),
            ("t06", 0.00),
        ],
    }
    state = compute_tag_persistence(synthetic, cfg)
    by_tag = {str(row["tag"]): row for row in state.get("tags", [])}
    tag_a = by_tag.get("tag_a")
    tag_b = by_tag.get("tag_b")
    if not tag_a or not tag_b:
        raise AssertionError("[FAIL] behavioral acceptance failed: synthetic tags missing")
    if str(tag_a.get("ers")) != "eligible":
        raise AssertionError(f"[FAIL] expected tag_a ers=eligible, got {tag_a.get('ers')!r}")
    if str(tag_b.get("ers")) != "none":
        raise AssertionError(f"[FAIL] expected tag_b ers=none, got {tag_b.get('ers')!r}")


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

    if not INPUT_SAMPLE.exists():
        raise SystemExit(f"missing input sample: {INPUT_SAMPLE}")

    cfg = load_persistence_config()

    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = (REPO_ROOT / output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    print("\n[v0.7 Acceptance] start\n")

    latest_tw_a = run_pipeline("tw", "run_tw_a", INPUT_SAMPLE, output_root)
    persistence_tw_a, kernel_tw_a, p_raw_tw_a, k_raw_tw_a = load_derived_payloads(latest_tw_a, "tw")
    check_schema_acceptance(persistence_tw_a, kernel_tw_a, cfg, "tw_a")
    print("[OK] schema acceptance for tw_a")

    latest_tw_b = run_pipeline("tw", "run_tw_b", INPUT_SAMPLE, output_root)
    persistence_tw_b, kernel_tw_b, p_raw_tw_b, k_raw_tw_b = load_derived_payloads(latest_tw_b, "tw")
    check_schema_acceptance(persistence_tw_b, kernel_tw_b, cfg, "tw_b")
    check_deterministic_acceptance(p_raw_tw_a, p_raw_tw_b, k_raw_tw_a, k_raw_tw_b)
    print("[OK] deterministic acceptance for tw")

    latest_none = run_pipeline("none", "run_none", INPUT_SAMPLE, output_root)
    persistence_none, kernel_none, _, _ = load_derived_payloads(latest_none, "none")
    check_schema_acceptance(persistence_none, kernel_none, cfg, "none")
    check_none_behavior(persistence_none)
    print("[OK] none profile behavior acceptance")

    check_isolation_acceptance()
    print("[OK] isolation acceptance")

    check_behavioral_acceptance(cfg)
    print("[OK] behavioral acceptance")

    if not args.skip_v05:
        check_v05_regression()
        print("[OK] v0.5 regression check")
    else:
        print("[SKIP] v0.5 regression check")

    if not args.skip_v04_hash:
        check_v04_non_interference()
        print("[OK] v0.4 non-interference summary hash check")
    else:
        print("[SKIP] v0.4 non-interference summary hash check")

    print("\n[PASS] v0.7 acceptance\n")


if __name__ == "__main__":
    main()
