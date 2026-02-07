# src/series_canonical.py
"""
Canonical resolver for domain -> series

Design goals:
- Minimal
- Deterministic
- Explicit (no magic inference)
- Safe fallback to 'unmapped'
"""

# 1️⃣ 明確宣告 canonical series（你現有的世界觀）
CANONICAL_SERIES = {
    "algorithmic_governance",
    "monetary_infrastructure",
    "synthetic_systems",
    "civilization_resilience",
    "identity_data",
    "human_manifesto",
    "offworld_expansion",
}

# 2️⃣ domain → canonical series 對照表（只放你「確定」的）
DOMAIN_SERIES_MAP = {
    # algorithmic governance
    "algorithmicallocation.ai": "algorithmic_governance",
    "algorithmicallocation.systems": "algorithmic_governance",
    "algorithmiclegitimacy.ai": "algorithmic_governance",

    # monetary
    "syntheticsolvency.ai": "monetary_infrastructure",

    # 你之後只要往這裡加，不會影響其他模組
}


def resolve_series(domain: str, series_raw: str | None) -> str:
    """
    Resolve a canonical series for an event.

    Priority:
    1. If series_raw is already canonical → trust it
    2. If domain has explicit mapping → use it
    3. Else → 'unmapped'
    """

    # 已經是 canonical（例如來自 metrics / domains table）
    if series_raw in CANONICAL_SERIES:
        return series_raw

    # domain 明確指定
    if domain in DOMAIN_SERIES_MAP:
        return DOMAIN_SERIES_MAP[domain]

    # 保守回退
    return "unmapped"
