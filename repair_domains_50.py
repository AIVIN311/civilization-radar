import json, os

# 來源：你貼的 50 domain 清單（含 series/profile）
DOMAINS_50 = [
  { "domain": "algorithmicallocation.com", "series": "algorithmic_governance", "profile": "honeypot" },
  { "domain": "algorithmicenforcement.com", "series": "algorithmic_governance", "profile": "honeypot" },
  { "domain": "algorithmiclegitimacy.com", "series": "algorithmic_governance", "profile": "normal" },
  { "domain": "algorithmicmartiallaw.com", "series": "algorithmic_governance", "profile": "hot" },
  { "domain": "algorithmicreserves.com", "series": "monetary_infrastructure", "profile": "honeypot" },
  { "domain": "algorithmicsovereignty.com", "series": "algorithmic_governance", "profile": "honeypot" },
  { "domain": "aurumreserveprotocol.com", "series": "monetary_infrastructure", "profile": "normal" },
  { "domain": "automatedjurisprudence.com", "series": "algorithmic_governance", "profile": "normal" },
  { "domain": "biologicaldatacenter.com", "series": "identity_data", "profile": "hot" },
  { "domain": "biometricliability.com", "series": "identity_data", "profile": "honeypot" },
  { "domain": "biometricsovereignty.com", "series": "identity_data", "profile": "normal" },
  { "domain": "civilizationcaching.com", "series": "civilization_resilience", "profile": "normal" },
  { "domain": "civilizationprotocols.com", "series": "civilization_resilience", "profile": "honeypot" },
  { "domain": "climateinterventionism.com", "series": "civilization_resilience", "profile": "normal" },
  { "domain": "cognitiveassetclass.com", "series": "monetary_infrastructure", "profile": "normal" },
  { "domain": "computationalscarcity.com", "series": "monetary_infrastructure", "profile": "honeypot" },
  { "domain": "defaultpower.com", "series": "algorithmic_governance", "profile": "normal" },
  { "domain": "dollardisruption.com", "series": "monetary_infrastructure", "profile": "hot" },
  { "domain": "emotionalquantification.com", "series": "identity_data", "profile": "normal" },
  { "domain": "energyjurisdiction.com", "series": "monetary_infrastructure", "profile": "honeypot" },
  { "domain": "humanintelligenceisirreplaceable.com", "series": "human_manifesto", "profile": "hot" },
  { "domain": "invisibledetermination.com", "series": "algorithmic_governance", "profile": "normal" },
  { "domain": "lunarresourceprotocol.com", "series": "offworld_expansion", "profile": "normal" },
  { "domain": "modelautophagy.com", "series": "synthetic_systems", "profile": "hot" },
  { "domain": "offworldassetrights.com", "series": "offworld_expansion", "profile": "honeypot" },
  { "domain": "offworldsovereignty.com", "series": "offworld_expansion", "profile": "normal" },
  { "domain": "orbitallockdown.com", "series": "offworld_expansion", "profile": "hot" },
  { "domain": "organicdatarights.com", "series": "identity_data", "profile": "normal" },
  { "domain": "postfiatreservesystems.com", "series": "monetary_infrastructure", "profile": "normal" },
  { "domain": "posthumousidentity.com", "series": "identity_data", "profile": "normal" },
  { "domain": "posttruthresilience.com", "series": "civilization_resilience", "profile": "normal" },
  { "domain": "siliconmetabolism.com", "series": "synthetic_systems", "profile": "hot" },
  { "domain": "sovereignairesilience.com", "series": "synthetic_systems", "profile": "honeypot" },
  { "domain": "sovereigndigitalarchitecture.com", "series": "synthetic_systems", "profile": "normal" },
  { "domain": "strategicresourceresilience.com", "series": "civilization_resilience", "profile": "honeypot" },
  { "domain": "syntheticjurisdiction.com", "series": "synthetic_systems", "profile": "normal" },
  { "domain": "syntheticliability.com", "series": "synthetic_systems", "profile": "honeypot" },
  { "domain": "syntheticpollution.com", "series": "synthetic_systems", "profile": "hot" },
  { "domain": "syntheticrealitycrisis.com", "series": "synthetic_systems", "profile": "hot" },
  { "domain": "syntheticsolvency.com", "series": "monetary_infrastructure", "profile": "honeypot" },
  { "domain": "technologicalpathdependency.com", "series": "synthetic_systems", "profile": "normal" },
  { "domain": "theageoffusion.com", "series": "civilization_resilience", "profile": "hot" },
  { "domain": "theanswerisblowininthewind.com", "series": "human_manifesto", "profile": "normal" },
  { "domain": "thefirstmarscitizen.com", "series": "offworld_expansion", "profile": "hot" },
  { "domain": "thefutureisalreadyhereitisjustnotevenlydistributed.com", "series": "human_manifesto", "profile": "hot" },
  { "domain": "theincrementalism.com", "series": "civilization_resilience", "profile": "normal" },
  { "domain": "thepacificpivot.com", "series": "civilization_resilience", "profile": "hot" },
  { "domain": "thepowerofdefault.com", "series": "algorithmic_governance", "profile": "normal" },
  { "domain": "unannouncedsovereignty.com", "series": "algorithmic_governance", "profile": "normal" },
  { "domain": "volatilityasinfrastructure.com", "series": "monetary_infrastructure", "profile": "normal" }
]

def norm(x: str | None) -> str:
    return (x or "").strip()

def main():
    out = []
    seen = set()

    for it in DOMAINS_50:
        d = norm(it.get("domain")).lower()
        s = norm(it.get("series"))
        p = norm(it.get("profile")) or "normal"

        if not d:
            continue
        if d in seen:
            raise SystemExit(f"duplicate domain: {d}")
        if not s or s.lower() == "unknown":
            raise SystemExit(f"bad series for {d}: {s}")

        out.append({"domain": d, "series": s, "profile": p})
        seen.add(d)

    os.makedirs("config", exist_ok=True)

    with open("domains.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    with open(os.path.join("config","domains_50.fixed.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("written domains.json:", len(out))
    print("written config/domains_50.fixed.json:", len(out))
    print("series unique:", sorted(set(x["series"] for x in out)))

if __name__ == "__main__":
    main()
