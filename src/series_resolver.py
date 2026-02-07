# src/series_resolver.py
CANONICAL = {
  "algorithmicallocation.ai": "algorithmic_governance",
  "algorithmicallocation.systems": "algorithmic_governance",
  "algorithmiclegitimacy.ai": "algorithmic_governance",
  "syntheticsolvency.ai": "monetary_infrastructure",
}

def resolve(domain, series_raw):
    if series_raw != "unmapped":
        return series_raw
    return CANONICAL.get(domain, "unmapped")
