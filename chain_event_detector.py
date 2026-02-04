import json

IN_PATH = "signals_chain_v01.json"
OUT_PATH = "chain_events_v01.json"

def bucket(W, th):
    if W >= th["alr"]: return "event"
    if W >= th["sus"]: return "alert"
    if W >= th["bg"]:  return "suspect"
    return "bg"

def main():
    with open(IN_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    th = data["thresholds"]
    ts = data["ts"]

    out = {
        "ts": ts,
        "events": {}
    }

    for series, s in data["series"].items():
        base = float(s["W_base"])
        proj = float(s["W_projected"])
        dW = float(s["dW"])
        chain = bool(s.get("is_chain_driven", False))

        b0 = bucket(base, th)
        b1 = bucket(proj, th)

        # 狀態標記：新爆發 / 持續中 / 消退中（v1.0：用 base→projected 當一跳預測）
        status = "steady"
        if b0 != "event" and b1 == "event":
            status = "new_burst"
        elif b0 in ("event","alert") and b1 in ("event","alert"):
            status = "ongoing"
        elif b0 in ("event","alert") and b1 in ("suspect","bg"):
            status = "cooling"

        # 鏈式事件：需要「狀態變紅」或「仍紅」且明顯由外部推動
        chain_flag = False
        if chain and (status in ("new_burst","ongoing")):
            chain_flag = True

        out["events"][series] = {
            "base_bucket": b0,
            "proj_bucket": b1,
            "status": status,
            "is_chain_event": chain_flag,
            "top_src": s.get("top_src"),
            "top_src_share": s.get("top_src_share"),
            "dW": s.get("dW"),
            "push_in": s.get("push_in"),
            "W_base": s.get("W_base"),
            "W_projected": s.get("W_projected")
        }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_PATH} (chain event labels)")

if __name__ == "__main__":
    main()
