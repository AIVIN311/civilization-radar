
import argparse
import csv
import glob
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit


STATUS_ORDER = {"OK": 0, "TREND": 1, "WARN": 2, "ALERT": 3, "FAIL": 4}
STATUS_LEVELS = ("OK", "TREND", "WARN", "ALERT", "FAIL")
COMPARATORS = ("eq", "ne", "lt", "lte", "gt", "gte")
ISSUE_LAYER_ORDER = {"config": 0, "L1": 1, "L2": 2, "L3": 3, "schema": 4}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(dt: datetime | None = None) -> str:
    d = dt or utc_now()
    return d.isoformat().replace("+00:00", "Z")


def utc_stamp(dt: datetime | None = None) -> str:
    d = dt or utc_now()
    return d.strftime("%Y-%m-%dT%H%M%S")


def status_max(current: str, incoming: str) -> str:
    return incoming if STATUS_ORDER.get(incoming, -1) > STATUS_ORDER.get(current, -1) else current


def issue_sort_key(issue: dict[str, Any]) -> tuple[int, str, str]:
    layer = str(issue.get("layer", "schema"))
    return (ISSUE_LAYER_ORDER.get(layer, 999), str(issue.get("code", "")), str(issue.get("message", "")))


def add_issue(
    issues: list[dict[str, Any]],
    layer: str,
    code: str,
    severity: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    item: dict[str, Any] = {"layer": layer, "code": code, "severity": severity, "message": message}
    if payload:
        item["payload"] = payload
    issues.append(item)


def normalize_domain(v: Any) -> str | None:
    if not isinstance(v, str):
        return None
    text = v.strip().rstrip(".").lower()
    return text or None


def parse_iso_ts(v: str) -> datetime | None:
    text = v.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_required_json(path: Path, label: str, issues: list[dict[str, Any]], fail_state: dict[str, bool]) -> Any | None:
    if not path.exists():
        add_issue(
            issues,
            "config",
            f"{label.upper()}_MISSING",
            "FAIL",
            f"Missing required config file: {path}",
            {"path": str(path)},
        )
        fail_state["failed"] = True
        return None
    try:
        return read_json(path)
    except Exception as exc:
        add_issue(
            issues,
            "config",
            f"{label.upper()}_INVALID_JSON",
            "FAIL",
            f"Invalid JSON in required config: {path}",
            {"path": str(path), "error": str(exc)},
        )
        fail_state["failed"] = True
        return None


def to_db_uri(path: Path, immutable: bool) -> str:
    base = path.resolve().as_uri()
    parts = urlsplit(base)
    query = {"mode": "ro"}
    if immutable:
        query["immutable"] = "1"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def resolve_snapshot_bucket(row: dict[str, Any], counters: dict[str, int]) -> str | None:
    ts = row.get("ts")
    if isinstance(ts, str):
        dt = parse_iso_ts(ts)
        if dt is not None:
            if dt.tzinfo is None:
                counters["ts_no_tz_assumed_utc"] += 1
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).date().isoformat()

    d = row.get("date")
    if isinstance(d, str):
        bucket = d.strip()[:10]
        if bucket:
            try:
                datetime.fromisoformat(bucket)
                counters["date_fallback_used"] += 1
                return bucket
            except Exception:
                return None
    return None


def connect_db_readonly(db_path: Path, issues: list[dict[str, Any]]) -> bool:
    if not db_path.exists():
        add_issue(issues, "L1", "RADAR_DB_MISSING", "FAIL", f"Missing radar DB file: {db_path}", {"path": str(db_path)})
        return False
    uri_immutable = to_db_uri(db_path, immutable=True)
    try:
        conn = sqlite3.connect(uri_immutable, uri=True)
        conn.execute("SELECT 1")
        conn.close()
        return True
    except Exception as exc_immutable:
        uri_ro = to_db_uri(db_path, immutable=False)
        try:
            conn = sqlite3.connect(uri_ro, uri=True)
            conn.execute("SELECT 1")
            conn.close()
            add_issue(
                issues,
                "L1",
                "SQLITE_IMMUTABLE_FALLBACK",
                "WARN",
                "SQLite immutable URI failed; fallback to mode=ro.",
                {"error": str(exc_immutable)},
            )
            return True
        except Exception as exc_ro:
            add_issue(
                issues,
                "L1",
                "RADAR_DB_READONLY_CONNECT_FAIL",
                "FAIL",
                "Failed to open radar DB in read-only mode.",
                {"immutable_error": str(exc_immutable), "ro_error": str(exc_ro)},
            )
            return False

def compute_l1(args: argparse.Namespace, issues: list[dict[str, Any]]) -> dict[str, Any]:
    status = "OK"
    metrics: dict[str, Any] = {
        "snapshots_max_date": None,
        "snapshots_today_count": 0,
        "domain_count_expected": args.domain_count,
        "bad_json_lines": 0,
        "radar_db_exists": False,
        "eval_quality_ok": False,
        "acceptance_files_matched": 0,
        "acceptance_files_parsed": 0,
    }
    counters = {"ts_no_tz_assumed_utc": 0, "date_fallback_used": 0}

    snapshots_path = Path(args.snapshots_jsonl)
    date_to_domains: dict[str, set[str]] = {}
    if not snapshots_path.exists():
        add_issue(issues, "L1", "SNAPSHOTS_MISSING", "FAIL", f"Missing snapshots JSONL: {snapshots_path}", {"path": str(snapshots_path)})
        status = "FAIL"
    else:
        try:
            with snapshots_path.open("r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        metrics["bad_json_lines"] += 1
                        continue
                    if not isinstance(row, dict):
                        continue
                    bucket = resolve_snapshot_bucket(row, counters)
                    if bucket is None:
                        continue
                    d = normalize_domain(row.get("domain"))
                    if d is None:
                        continue
                    date_to_domains.setdefault(bucket, set()).add(d)
        except Exception as exc:
            add_issue(
                issues,
                "L1",
                "SNAPSHOTS_READ_FAILED",
                "FAIL",
                f"Failed to read snapshots JSONL: {snapshots_path}",
                {"path": str(snapshots_path), "error": str(exc)},
            )
            status = "FAIL"

    if date_to_domains:
        max_date = max(date_to_domains.keys())
        metrics["snapshots_max_date"] = max_date
        metrics["snapshots_today_count"] = len(date_to_domains[max_date])
    else:
        add_issue(issues, "L1", "SNAPSHOTS_NO_VALID_DATES", "FAIL", "No valid snapshot date buckets were resolved.")
        status = "FAIL"

    metrics["radar_db_exists"] = connect_db_readonly(Path(args.radar_db), issues)
    if not metrics["radar_db_exists"]:
        status = "FAIL"

    eval_path = Path(args.eval_quality)
    if not eval_path.exists():
        add_issue(issues, "L1", "EVAL_QUALITY_MISSING", "FAIL", f"Missing eval_quality JSON: {eval_path}", {"path": str(eval_path)})
        status = "FAIL"
    else:
        try:
            obj = read_json(eval_path)
            metrics["eval_quality_ok"] = bool(isinstance(obj, dict) and obj.get("ok") is True)
            if not metrics["eval_quality_ok"]:
                add_issue(issues, "L1", "EVAL_QUALITY_NOT_OK", "FAIL", "eval_quality ok flag is not true.")
                status = "FAIL"
        except Exception as exc:
            add_issue(
                issues,
                "L1",
                "EVAL_QUALITY_READ_FAILED",
                "FAIL",
                f"Failed to parse eval_quality JSON: {eval_path}",
                {"path": str(eval_path), "error": str(exc)},
            )
            status = "FAIL"

    files = sorted(glob.glob(args.acceptance_jsons))
    metrics["acceptance_files_matched"] = len(files)
    parsed = 0
    if not files:
        add_issue(issues, "L1", "ACCEPTANCE_MISSING", "FAIL", f"No acceptance files matched: {args.acceptance_jsons}", {"pattern": args.acceptance_jsons})
        status = "FAIL"
    else:
        for p in files:
            path = Path(p)
            try:
                obj = read_json(path)
            except Exception as exc:
                add_issue(issues, "L1", "ACCEPTANCE_PARSE_FAILED", "WARN", f"Failed to parse acceptance JSON: {path}", {"path": str(path), "error": str(exc)})
                continue
            shape_ok = (
                isinstance(obj, dict)
                and isinstance(obj.get("generated_at"), str)
                and isinstance(obj.get("latest"), str)
                and isinstance(obj.get("db"), str)
                and bool(obj.get("generated_at", "").strip())
                and bool(obj.get("latest", "").strip())
                and bool(obj.get("db", "").strip())
            )
            if shape_ok:
                parsed += 1
            else:
                add_issue(issues, "L1", "ACCEPTANCE_BAD_SHAPE", "WARN", f"Acceptance JSON does not match minimal shape: {path}", {"path": str(path)})

    metrics["acceptance_files_parsed"] = parsed
    if parsed == 0:
        add_issue(issues, "L1", "ACCEPTANCE_NONE_PARSED", "FAIL", "No acceptance JSON matched minimal shape.")
        status = "FAIL"
    elif parsed < metrics["acceptance_files_matched"]:
        add_issue(
            issues,
            "L1",
            "ACCEPTANCE_PARTIAL_PARSE",
            "WARN",
            "Some acceptance JSON files did not pass minimal shape checks.",
            {"matched": metrics["acceptance_files_matched"], "parsed": parsed},
        )
        status = status_max(status, "WARN")

    if counters["ts_no_tz_assumed_utc"] > 0:
        add_issue(issues, "L1", "TS_NO_TZ_ASSUMED_UTC", "WARN", "Encountered ts without timezone; assumed UTC.", {"count": counters["ts_no_tz_assumed_utc"]})
        status = status_max(status, "WARN")

    return {
        "status": status,
        "metrics": metrics,
        "audit": {
            "TS_NO_TZ_ASSUMED_UTC": counters["ts_no_tz_assumed_utc"],
            "DATE_FALLBACK_USED": counters["date_fallback_used"],
        },
    }


def parse_threshold_rules_for_layer(thresholds: Any, layer: str, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target: Any = None
    if isinstance(thresholds, dict):
        for key in (layer, layer.lower()):
            if key in thresholds:
                target = thresholds[key]
                break
        if target is None:
            layers = thresholds.get("layers")
            if isinstance(layers, dict):
                target = layers.get(layer) or layers.get(layer.lower())
    if target is None:
        add_issue(issues, "config", f"THRESHOLDS_{layer}_MISSING", "FAIL", f"Missing threshold rules for {layer}.")
        return []

    rules: list[dict[str, Any]] = []
    if isinstance(target, list):
        for item in target:
            if isinstance(item, dict):
                metric = item.get("metric")
                op = str(item.get("op") or item.get("operator") or "").lower()
                status = str(item.get("status") or "").upper()
                if isinstance(metric, str) and op in COMPARATORS and status in STATUS_LEVELS and "value" in item:
                    rules.append({"metric": metric, "op": op, "status": status, "value": item.get("value")})
    elif isinstance(target, dict):
        for metric, cfg in target.items():
            if not isinstance(metric, str) or not isinstance(cfg, dict):
                continue
            for key, value in cfg.items():
                m = re.match(r"^(trend|warn|alert|fail)_(eq|ne|lt|lte|gt|gte)$", str(key).lower())
                if m:
                    rules.append({"metric": metric, "status": m.group(1).upper(), "op": m.group(2), "value": value})
            op = str(cfg.get("op") or cfg.get("operator") or "").lower()
            sev = str(cfg.get("status") or "").upper()
            if op in COMPARATORS and sev in STATUS_LEVELS and "value" in cfg:
                rules.append({"metric": metric, "status": sev, "op": op, "value": cfg.get("value")})

    if not rules:
        add_issue(issues, "config", f"THRESHOLDS_{layer}_UNREADABLE", "FAIL", f"Threshold rules for {layer} were unreadable.")
    return rules


def compare_value(actual: Any, op: str, expected: Any) -> bool:
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    try:
        if op == "lt":
            return actual < expected
        if op == "lte":
            return actual <= expected
        if op == "gt":
            return actual > expected
        if op == "gte":
            return actual >= expected
    except Exception:
        return False
    return False


def apply_thresholds(layer: str, status: str, metrics: dict[str, Any], thresholds: Any, issues: list[dict[str, Any]]) -> str:
    out = status
    rules = parse_threshold_rules_for_layer(thresholds, layer, issues)
    for rule in rules:
        metric = rule["metric"]
        if metric not in metrics:
            continue
        actual = metrics.get(metric)
        if compare_value(actual, rule["op"], rule["value"]):
            out = status_max(out, rule["status"])
            add_issue(
                issues,
                layer,
                "THRESHOLD_TRIGGERED",
                rule["status"],
                f"{layer} threshold triggered: {metric} {rule['op']} {rule['value']}",
                {"metric": metric, "actual": actual, "expected": rule["value"]},
            )
    return out

def parse_requests(raw: Any) -> tuple[int | None, str | None]:
    if isinstance(raw, int):
        return (raw, None) if raw >= 0 else (None, "CSV_BAD_NUMBER_PARSE")
    if raw is None:
        return (None, "CSV_BAD_REQUESTS_FORMAT")
    text = str(raw).strip()
    if not text:
        return (None, "CSV_BAD_REQUESTS_FORMAT")
    if "," in text or "." in text:
        return (None, "CSV_BAD_REQUESTS_FORMAT")
    if not re.fullmatch(r"[0-9]+", text):
        return (None, "CSV_BAD_NUMBER_PARSE")
    try:
        return (int(text), None)
    except Exception:
        return (None, "CSV_BAD_NUMBER_PARSE")


def parse_status_code(raw: Any) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not re.fullmatch(r"[0-9]{3}", text):
        return None
    try:
        return int(text)
    except Exception:
        return None


def compute_l2(csv_pattern: str | None, issues: list[dict[str, Any]]) -> dict[str, Any]:
    status = "OK"
    csv_files: list[str] = []
    bad_files: list[str] = []
    bad_reasons: dict[str, str] = {}

    if not csv_pattern:
        add_issue(issues, "L2", "L2_OPTIONAL_INPUT_MISSING", "WARN", "No Cloudflare CSV pattern provided.")
        return {"status": "WARN", "metrics": {}, "diagnostics": {"cloudflare_csv_files": [], "cloudflare_csv_bad_files": [], "cloudflare_csv_bad_reasons": {}}}

    csv_files = sorted(glob.glob(csv_pattern))
    if not csv_files:
        add_issue(issues, "L2", "L2_OPTIONAL_INPUT_MISSING", "WARN", f"No Cloudflare CSV files matched pattern: {csv_pattern}", {"pattern": csv_pattern})
        return {"status": "WARN", "metrics": {}, "diagnostics": {"cloudflare_csv_files": [], "cloudflare_csv_bad_files": [], "cloudflare_csv_bad_reasons": {}}}

    total_requests = 0
    total_200 = 0
    total_4xx = 0
    total_5xx = 0

    for p in csv_files:
        path = Path(p)
        bad_reason: str | None = None
        file_total = 0
        file_200 = 0
        file_4xx = 0
        file_5xx = 0
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    bad_reason = "CSV_EMPTY"
                else:
                    headers = {h.strip() for h in reader.fieldnames if isinstance(h, str)}
                    if "EdgeResponseStatus" not in headers or "Requests" not in headers:
                        bad_reason = "CSV_BAD_HEADER"
                    else:
                        has_row = False
                        for row in reader:
                            has_row = True
                            req, req_err = parse_requests(row.get("Requests"))
                            if req_err:
                                bad_reason = req_err
                                break
                            code = parse_status_code(row.get("EdgeResponseStatus"))
                            if code is None:
                                bad_reason = "CSV_BAD_NUMBER_PARSE"
                                break
                            req_val = req or 0
                            file_total += req_val
                            if code == 200:
                                file_200 += req_val
                            elif 400 <= code <= 499:
                                file_4xx += req_val
                            elif 500 <= code <= 599:
                                file_5xx += req_val
                        if not has_row and bad_reason is None:
                            bad_reason = "CSV_EMPTY"
        except Exception:
            bad_reason = "CSV_BAD_NUMBER_PARSE"

        if bad_reason:
            bad_files.append(str(path))
            bad_reasons[str(path)] = bad_reason
            add_issue(issues, "L2", bad_reason, "WARN", f"Cloudflare CSV rejected: {path}", {"path": str(path), "reason": bad_reason})
            status = status_max(status, "WARN")
            continue

        total_requests += file_total
        total_200 += file_200
        total_4xx += file_4xx
        total_5xx += file_5xx

    if total_requests <= 0:
        add_issue(issues, "L2", "L2_NO_VALID_REQUESTS", "WARN", "Cloudflare CSV input present but no valid request totals computed.")
        status = status_max(status, "WARN")
        metrics: dict[str, Any] = {}
    else:
        metrics = {
            "total_requests": total_requests,
            "http_200_rate": round(total_200 / total_requests, 8),
            "http_4xx_rate": round(total_4xx / total_requests, 8),
            "http_5xx_rate": round(total_5xx / total_requests, 8),
        }

    return {
        "status": status,
        "metrics": metrics,
        "diagnostics": {
            "cloudflare_csv_files": [str(Path(x)) for x in csv_files],
            "cloudflare_csv_bad_files": bad_files,
            "cloudflare_csv_bad_reasons": bad_reasons,
        },
    }


def extract_l3_entities(obj: Any) -> tuple[list[str], list[str], list[str], bool]:
    if not isinstance(obj, dict):
        return ([], [], [], False)
    nodes: list[str] = []
    groups: list[str] = []
    watchlist: list[str] = []

    raw_nodes = obj.get("nodes")
    if isinstance(raw_nodes, list):
        for item in raw_nodes:
            if isinstance(item, str) and item.strip():
                nodes.append(item.strip())
            elif isinstance(item, dict):
                for k in ("id", "name", "node", "series"):
                    v = item.get(k)
                    if isinstance(v, str) and v.strip():
                        nodes.append(v.strip())
                        break

    raw_groups = obj.get("groups")
    if isinstance(raw_groups, dict):
        for k in raw_groups.keys():
            if isinstance(k, str) and k.strip():
                groups.append(k.strip())
    elif isinstance(raw_groups, list):
        for item in raw_groups:
            if isinstance(item, str) and item.strip():
                groups.append(item.strip())
            elif isinstance(item, dict):
                for k in ("name", "id", "group"):
                    v = item.get(k)
                    if isinstance(v, str) and v.strip():
                        groups.append(v.strip())
                        break

    for wk in ("bridge_watchlist", "watchlist", "watchlist_nodes"):
        raw_watch = obj.get(wk)
        if isinstance(raw_watch, list):
            for item in raw_watch:
                if isinstance(item, str) and item.strip():
                    watchlist.append(item.strip())
                elif isinstance(item, dict):
                    for k in ("id", "name", "node", "series"):
                        v = item.get(k)
                        if isinstance(v, str) and v.strip():
                            watchlist.append(v.strip())
                            break
            break

    nodes = sorted(set(nodes))
    groups = sorted(set(groups))
    watchlist = sorted(set(watchlist))
    return (nodes, groups, watchlist, bool(nodes or groups or watchlist))


def compute_l3(node_group_map: Any, issues: list[dict[str, Any]]) -> dict[str, Any]:
    status = "OK"
    nodes, groups, watchlist, ok = extract_l3_entities(node_group_map)
    if not ok:
        add_issue(issues, "L3", "NODE_GROUP_MAP_UNREADABLE", "FAIL", "node_group_map is unreadable or missing required entities.")
        status = "FAIL"
    return {
        "status": status,
        "metrics": {
            "node_hotspot_scores": {n: 0.0 for n in nodes},
            "group_comove_count": {g: 0 for g in groups},
            "bridge_watchlist_scores": {n: 0.0 for n in watchlist},
        },
    }


def default_from_template(t: Any) -> Any:
    if isinstance(t, dict):
        return {k: default_from_template(v) for k, v in sorted(t.items(), key=lambda kv: str(kv[0]))}
    if isinstance(t, list):
        return []
    return None


def align_to_template(value: Any, template: Any, stats: dict[str, int]) -> Any:
    if isinstance(template, dict):
        src = value if isinstance(value, dict) else {}
        out: dict[str, Any] = {}
        for k in sorted(template.keys()):
            if k in src:
                out[k] = align_to_template(src[k], template[k], stats)
            else:
                out[k] = default_from_template(template[k])
                stats["filled"] += 1
        for k in src.keys():
            if k not in template:
                stats["dropped"] += 1
        return out
    if isinstance(template, list):
        if not template:
            return value if isinstance(value, list) else []
        if not isinstance(value, list):
            stats["filled"] += 1
            return []
        return [align_to_template(v, template[0], stats) for v in value]
    if value is None:
        stats["filled"] += 1
        return None
    return value


def parse_metrics_keys(metrics_keys: Any, issues: list[dict[str, Any]]) -> tuple[Any | None, set[str], list[str] | None]:
    if isinstance(metrics_keys, dict):
        top_level = metrics_keys.get("top_level")
        if isinstance(top_level, list) and all(isinstance(x, str) for x in top_level):
            return (None, set(top_level), list(top_level))
        return (metrics_keys, set(metrics_keys.keys()), None)
    if isinstance(metrics_keys, list) and all(isinstance(x, str) for x in metrics_keys):
        return (None, set(metrics_keys), list(metrics_keys))
    add_issue(issues, "config", "METRICS_KEYS_UNREADABLE", "FAIL", "metrics_keys_v01.json is unreadable for alignment.")
    return (None, set(), None)


def align_with_top_list(report: dict[str, Any], keys: list[str], stats: dict[str, int]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    allowed = set(keys)
    for k in sorted(keys):
        if k in report:
            out[k] = report[k]
        else:
            out[k] = None
            stats["filled"] += 1
    for k in report.keys():
        if k not in allowed:
            stats["dropped"] += 1
    return out


def schema_top_properties(schema: Any) -> set[str]:
    if isinstance(schema, dict) and isinstance(schema.get("properties"), dict):
        return set(str(k) for k in schema["properties"].keys())
    return set()

def type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def validate_schema_shape(value: Any, schema: Any, path: str, errors: list[str]) -> None:
    if not isinstance(schema, dict):
        return
    st = schema.get("type")
    if isinstance(st, str):
        if not type_matches(value, st):
            errors.append(f"{path}: expected type {st}")
            return
    elif isinstance(st, list):
        if not any(type_matches(value, t) for t in st if isinstance(t, str)):
            errors.append(f"{path}: expected one of types {st}")
            return

    enum_vals = schema.get("enum")
    if isinstance(enum_vals, list) and value not in enum_vals:
        errors.append(f"{path}: value not in enum")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum")

    if isinstance(value, list):
        if isinstance(schema.get("minItems"), int) and len(value) < schema["minItems"]:
            errors.append(f"{path}: below minItems")
        if isinstance(schema.get("maxItems"), int) and len(value) > schema["maxItems"]:
            errors.append(f"{path}: above maxItems")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                validate_schema_shape(item, item_schema, f"{path}[{i}]", errors)

    if isinstance(value, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    errors.append(f"{path}.{key}: required property missing")
        props = schema.get("properties")
        if isinstance(props, dict):
            for key, child_schema in props.items():
                if key in value and isinstance(child_schema, dict):
                    validate_schema_shape(value[key], child_schema, f"{path}.{key}", errors)
            if schema.get("additionalProperties") is False:
                allowed = set(props.keys())
                for key in value.keys():
                    if key not in allowed:
                        errors.append(f"{path}.{key}: additional property not allowed")


def build_base_report(run_dt: datetime) -> dict[str, Any]:
    return {
        "observer_version": "v0.1",
        "generated_at": utc_iso(run_dt),
        "run_id": utc_stamp(run_dt),
        "overall_status": "OK",
        "layers": {
            "L1": {"status": "OK", "metrics": {}, "audit": {}},
            "L2": {"status": "OK", "metrics": {}},
            "L3": {"status": "OK", "metrics": {}},
        },
        "issues": [],
    }


def build_summary(report: dict[str, Any]) -> str:
    lines: list[str] = [f"overall_status: {report.get('overall_status')}", "", "[meta]"]
    for k in ("generated_at", "observer_version", "run_id"):
        lines.append(f"{k}: {report.get(k)}")
    lines.append("")

    layers = report.get("layers") if isinstance(report.get("layers"), dict) else {}
    for layer_name in ("L1", "L2", "L3"):
        layer = layers.get(layer_name) if isinstance(layers, dict) else {}
        layer = layer if isinstance(layer, dict) else {}
        lines.append(f"[{layer_name}]")
        lines.append(f"status: {layer.get('status')}")
        metrics = layer.get("metrics") if isinstance(layer.get("metrics"), dict) else {}
        for mk in sorted(metrics.keys()):
            lines.append(f"{mk}: {metrics[mk]}")
        audit = layer.get("audit") if isinstance(layer.get("audit"), dict) else {}
        for ak in sorted(audit.keys()):
            lines.append(f"{ak}: {audit[ak]}")
        lines.append("")

    lines.append("[issues]")
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    for item in issues:
        if not isinstance(item, dict):
            continue
        lines.append(f"{item.get('layer')} | {item.get('severity')} | {item.get('code')} | {item.get('message')}")
        payload = item.get("payload")
        if isinstance(payload, dict):
            for k in sorted(payload.keys()):
                lines.append(f"  {k}: {payload[k]}")
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(report: dict[str, Any], output_dir: Path, run_dt: datetime) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"observer_report_{utc_stamp(run_dt)}.json"
    summary_path = output_dir / f"observer_summary_{run_dt.strftime('%Y-%m-%d')}.txt"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(build_summary(report), encoding="utf-8")
    return (report_path, summary_path)


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    run_dt = utc_now()
    repo = Path(__file__).resolve().parents[2]
    obs_dir = Path(__file__).resolve().parent
    out_dir = repo / "output" / "observer"

    issues: list[dict[str, Any]] = []
    fail_state = {"failed": False}

    schema = load_required_json(obs_dir / "observer_report.schema.json", "observer_schema", issues, fail_state)
    thresholds = load_required_json(obs_dir / "thresholds_v01.json", "thresholds", issues, fail_state)
    node_group_map = load_required_json(obs_dir / "node_group_map.json", "node_group_map", issues, fail_state)
    metrics_keys = load_required_json(obs_dir / "metrics_keys_v01.json", "metrics_keys", issues, fail_state)

    report = build_base_report(run_dt)
    l1 = compute_l1(args, issues)
    l2 = compute_l2(args.cloudflare_csvs, issues)
    l3 = compute_l3(node_group_map, issues) if node_group_map is not None else {"status": "FAIL", "metrics": {}}
    if node_group_map is None:
        add_issue(issues, "L3", "NODE_GROUP_MAP_MISSING", "FAIL", "node_group_map config is missing or invalid.")

    if thresholds is not None:
        l1["status"] = apply_thresholds("L1", l1["status"], l1["metrics"], thresholds, issues)
        l2["status"] = apply_thresholds("L2", l2["status"], l2["metrics"], thresholds, issues)
        l3["status"] = apply_thresholds("L3", l3["status"], l3["metrics"], thresholds, issues)

    report["layers"]["L1"] = l1
    report["layers"]["L2"] = {"status": l2["status"], "metrics": l2["metrics"]}
    report["layers"]["L3"] = {"status": l3["status"], "metrics": l3["metrics"]}

    alignment_stats = {"filled": 0, "dropped": 0}
    metrics_template, metrics_whitelist, metrics_top_list = (None, set(), None)
    if metrics_keys is not None:
        metrics_template, metrics_whitelist, metrics_top_list = parse_metrics_keys(metrics_keys, issues)
        if metrics_template is not None:
            report = align_to_template(report, metrics_template, alignment_stats)
        elif metrics_top_list is not None:
            report = align_with_top_list(report, metrics_top_list, alignment_stats)
    else:
        fail_state["failed"] = True

    schema_props = schema_top_properties(schema)
    diagnostics = {
        "layer_statuses": {
            "L1": report.get("layers", {}).get("L1", {}).get("status") if isinstance(report.get("layers"), dict) else "OK",
            "L2": report.get("layers", {}).get("L2", {}).get("status") if isinstance(report.get("layers"), dict) else "OK",
            "L3": report.get("layers", {}).get("L3", {}).get("status") if isinstance(report.get("layers"), dict) else "OK",
        },
        "metrics_keys_filled": alignment_stats["filled"],
        "metrics_keys_dropped": alignment_stats["dropped"],
        "cloudflare_csv_files": l2.get("diagnostics", {}).get("cloudflare_csv_files", []),
        "cloudflare_csv_bad_files": l2.get("diagnostics", {}).get("cloudflare_csv_bad_files", []),
    }

    extra: dict[str, Any] = {}
    for k, v in diagnostics.items():
        if k in schema_props and k in metrics_whitelist:
            report[k] = v
        else:
            extra[k] = v
    if extra:
        add_issue(issues, "schema", "EXTRA_DIAGNOSTIC", "WARN", "Diagnostics excluded by schema/keys gate.", extra)

    issues_sorted = sorted(issues, key=issue_sort_key)
    report["issues"] = issues_sorted

    overall = "OK"
    for layer_name in ("L1", "L2", "L3"):
        layer = report.get("layers", {}).get(layer_name, {}) if isinstance(report.get("layers"), dict) else {}
        if isinstance(layer, dict):
            overall = status_max(overall, str(layer.get("status", "OK")))
    for item in issues_sorted:
        overall = status_max(overall, str(item.get("severity", "OK")))
    if fail_state["failed"]:
        overall = status_max(overall, "FAIL")
    report["overall_status"] = overall

    if schema is not None:
        schema_errors: list[str] = []
        validate_schema_shape(report, schema, "$", schema_errors)
        if schema_errors:
            add_issue(
                issues_sorted,
                "schema",
                "SCHEMA_VALIDATION_FAILED",
                "FAIL",
                "Observer report failed schema validation.",
                {"errors": schema_errors[:20]},
            )
            report["issues"] = sorted(issues_sorted, key=issue_sort_key)
            report["overall_status"] = status_max(report["overall_status"], "FAIL")
    else:
        add_issue(issues_sorted, "schema", "SCHEMA_MISSING", "FAIL", "Schema validation skipped because schema config is missing or invalid.")
        report["issues"] = sorted(issues_sorted, key=issue_sort_key)
        report["overall_status"] = status_max(report["overall_status"], "FAIL")

    write_outputs(report, out_dir, run_dt)
    return (report, 1 if report.get("overall_status") == "FAIL" else 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Civilization Radar Observer v0.1 (read-only)")
    parser.add_argument("--domain-count", type=int, required=True)
    parser.add_argument("--snapshots-jsonl", default="output/snapshots.jsonl")
    parser.add_argument("--radar-db", default="output/latest/radar.db")
    parser.add_argument("--eval-quality", default="output/latest/reports/eval_quality.json")
    parser.add_argument("--acceptance-jsons", default="output/reports/acceptance_latest_*.json")
    parser.add_argument("--cloudflare-csvs", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dt = utc_now()
    output_dir = Path(__file__).resolve().parents[2] / "output" / "observer"
    try:
        _, code = run(args)
        return code
    except Exception as exc:
        issues: list[dict[str, Any]] = []
        add_issue(issues, "schema", "INTERNAL_ERROR", "FAIL", "Unhandled exception in observer runtime.", {"error": str(exc)})
        report = build_base_report(run_dt)
        report["overall_status"] = "FAIL"
        report["issues"] = sorted(issues, key=issue_sort_key)
        write_outputs(report, output_dir, run_dt)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
