import json, re, hashlib
from typing import Dict, List, Any, Tuple

# ---------- utils ----------
def norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def has_any(text: str, kws: List[str]) -> bool:
    t = norm(text)
    return any(k.lower() in t for k in kws)

def collect_tags(text: str, mapping: Dict[str, List[str]]) -> List[str]:
    t = norm(text)
    out = []
    for tag, kws in mapping.items():
        if any(k.lower() in t for k in kws):
            out.append(tag)
    return out

# ---------- dictionaries (v0.1 starter) ----------
TYPE_PRIORITY = [
    "disaster","health","climate","military","cyber","space",
    "finance","economy","policy","legal","tech","info_ops","social","other"
]

TYPE_KWS = {
  "disaster": ["earthquake","flood","wildfire","explosion","evacuation","地震","洪水","野火","爆炸","撤離","災情"],
  "health": ["outbreak","pandemic","vaccine","who","疫情","疫苗","隔離","公共衛生"],
  "climate": ["climate","emissions","net zero","cop","氣候","排放","淨零","碳"],
  "military": ["missile","blockade","drill","shoot down","軍演","飛彈","封鎖","演習","擊落","軍機","軍艦"],
  "cyber": ["ransomware","breach","leak","ddos","zero-day","駭客","入侵","外洩","勒索","零日","ddos"],
  "space": ["launch","satellite","orbital","lunar","space station","火箭","發射","衛星","軌道","月球","太空站"],
  "finance": ["imf","world bank","rate cut","bond","fx","swift","sanction","金融","降息","升息","債券","匯率","制裁"],
  "economy": ["gdp","inflation","tariff","supply chain","出口","關稅","通膨","供應鏈","失業"],
  "policy": ["bill","executive order","regulation","ban","法案","行政命令","規範","禁令","部會"],
  "legal": ["lawsuit","indictment","ruling","fine","法院","判決","起訴","裁定","罰款"],
  "tech": ["ai","model","chip","compute","datacenter","演算法","模型","晶片","算力","資料中心","ai"],
  "info_ops": ["disinformation","psyops","deepfake","認知作戰","假消息","深偽","輿論操弄"],
  "social": ["protest","riot","strike","election","抗議","暴動","罷工","選舉"]
}

ACTOR_KWS = {
  "org_imf": ["imf"],
  "org_worldbank": ["world bank"],
  "org_un": ["un ", "united nations", "聯合國"],
  "org_who": ["who", "world health organization"],
  "regulator": ["regulator","commission","sec","ftc","監管","金管","央行","委員會"],
  "intelligence": ["cia","nsa","intelligence","情報","情治"],
  "military": ["military","navy","air force","army","軍方","海軍","空軍","陸軍"],
  "state_us": ["u.s.","usa","united states","white house","pentagon","美國","白宮","五角大廈"],
  "state_cn": ["prc","beijing","pla","china","中國","北京","中共","解放軍"],
  "state_tw": ["taiwan","taipei","國防部","行政院","總統府","台灣","台北","國軍"],
  "state_eu": ["eu ","brussels","european commission","歐盟","布魯塞爾"],
  "state_ru": ["russia","kremlin","俄羅斯","克里姆林宮"],
  "company_bigtech": ["google","meta","apple","microsoft","amazon"],
  "company_ai": ["openai","anthropic","deepmind"],
  "company_chip": ["tsmc","nvidia","amd","intel"],
  "company_finance": ["bank","exchange","visa","mastercard","blackrock","銀行","交易所"]
}

GEO_KWS = {
  "geo_tw": ["taiwan","taipei","金門","馬祖","台灣","台北","高雄","澎湖"],
  "geo_indo_pacific": ["indo-pacific","南海","東海","台海","japan","korea","philippines","australia","印太","日本","韓國","菲律賓","澳洲"],
  "geo_europe": ["europe","eu","ukraine","france","germany","歐洲","烏克蘭","法國","德國"],
  "geo_middle_east": ["middle east","israel","iran","gaza","red sea","中東","以色列","伊朗","加薩","紅海"],
  "geo_arctic": ["arctic","北極"],
  "geo_space": ["orbit","orbital","space","lunar","mars","軌道","太空","月球","火星"]
}

def pick_event_type(title: str, text: str) -> str:
    blob = f"{title} {text}"
    for et in TYPE_PRIORITY:
        if et != "other" and has_any(blob, TYPE_KWS.get(et, [])):
            return et
    return "other"

def reliability_from_source(source_type: str) -> float:
    return {"news":0.70, "sensor":0.80, "manual":0.65}.get(source_type, 0.50)

def make_fingerprint(event_type: str, title: str, actor_tags: List[str], geo_tags: List[str]) -> str:
    base = f"{event_type}|{norm(title)[:120]}|{','.join(sorted(actor_tags))}|{','.join(sorted(geo_tags))}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()

def novelty_from_counts(fp: str, fp_counts: Dict[str,int]) -> float:
    n = fp_counts.get(fp, 0) + 1
    fp_counts[fp] = n
    return 1.0 if n == 1 else (0.60 if n == 2 else (0.40 if n == 3 else 0.20))

def extract_event(raw: Dict[str,Any], fp_counts: Dict[str,int]) -> Dict[str,Any]:
    title = raw.get("title","")
    text  = raw.get("text","")
    blob  = f"{title} {text}"

    event_type = pick_event_type(title, text)
    actor_tags = collect_tags(blob, ACTOR_KWS) or ["unknown"]
    geo_tags   = collect_tags(blob, GEO_KWS) or ["geo_global"]

    source_type = (raw.get("source") or {}).get("type","unknown")
    reliability = reliability_from_source(source_type)

    fp = make_fingerprint(event_type, title, actor_tags, geo_tags)
    novelty = novelty_from_counts(fp, fp_counts)

    return {
        "ts": raw.get("ts"),
        "source": raw.get("source", {"type":"unknown"}),
        "title": title,
        "text": text,
        "event_type": event_type,
        "actor_tags": actor_tags,
        "geo_tags": geo_tags,
        "reliability": reliability,
        "novelty": novelty,
        "fingerprint": fp,
        "features": {
            "type_priority": TYPE_PRIORITY,
            "actor_hits": actor_tags,
            "geo_hits": geo_tags
        }
    }
