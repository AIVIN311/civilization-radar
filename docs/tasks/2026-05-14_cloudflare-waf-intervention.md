# 2026-05-14 Cloudflare WAF Intervention

## Goal
- Reduce malicious scanner traffic across the `xxvvv` account while preserving Civilization Radar's observation baseline and future interpretability.
- Preserve high-volume search and SEO crawler access when that access supports the broader "civilization caching" / semantic-seeding purpose.
- Record the intervention point so later traffic, month-end, or anomaly interpretation does not mistake post-filter data for an unchanged baseline.

## Allowed changes
- External Cloudflare WAF configuration only.
- Documentation note in `docs/tasks/`.
- No repository runtime, scoring, gate, kernel, database, or pipeline behavior changes.

## Do-not-touch list
- `persistence_v1.py`
- `metrics_v02.W` path assumptions
- strength / push / gate paths
- DB schema
- pipeline main flow
- output directory contract

## Intervention
- Account: `xxvvv`
- Scope applied: 67 Cloudflare zones, zone-level WAF custom rules.
- Account-level custom WAF was attempted first but Cloudflare returned `not entitled to use the phase http_request_firewall_custom`, so the safer available path was zone-level custom rules.

Rules applied to each zone:
- `CivRadar: block scanner paths`
  - Action: `block`
  - Paths: `/.env`, `/.git/config`, `/.git/*`, `/wp-login.php`, `/wp-admin/index.php`, `/wp-admin/*`, `/xmlrpc.php`
- `CivRadar: managed challenge generic non-browser clients`
  - Action: `managed_challenge`
  - User agents: empty user agent, `curl/`

Strategy correction:
- The initial high-volume bot challenge included `AhrefsBot`, `YandexBot`, and `YandexRenderResourcesBot`.
- After clarifying that SEO indexing and crawler ingestion are part of the semantic distribution path, those crawlers were removed from the challenge rule.
- The final active posture allows Ahrefs/Yandex-style indexing while continuing to challenge generic non-browser clients and block scanner paths.

## Verification steps
- Verified Cloudflare token status: active.
- Verified zone listing: 67 zones readable.
- Created zone-level WAF rules after account-level WAF custom phase was unavailable.
- Updated the bot challenge rule to remove Ahrefs/Yandex crawler matching and read back every zone's `http_request_firewall_custom` entrypoint.
- Confirmed both rules exist and are enabled in every zone.
- Confirmed no zone failed verification.
- Checked local git status before this note; unrelated pre-existing dirty/untracked files were present and were not modified.

## Results / notes
- Zones updated: 67 / 67.
- Rules created: 134.
- Bot challenge rules updated: 67 / 67.
- Final verification passed: 67 / 67.
- This is an observation-environment intervention, not a Radar pipeline change.
- Future Cloudflare traffic comparisons should treat 2026-05-14 03:18 Asia/Taipei as a filtering boundary.
- Post-intervention decreases in scanner-path, curl, and empty user-agent requests should be interpreted as policy effects, not organic demand changes.
- AhrefsBot, YandexBot, and YandexRenderResourcesBot traffic should remain interpretable as crawler distribution / indexing pressure, not as human demand.

## Follow-ups
- Review Cloudflare analytics after 24 hours and again after 7 days.
- If cache hit rate remains low after bot pressure drops, review cache rules separately from WAF controls.
- If Ahrefs/Yandex traffic becomes operationally harmful, prefer a narrower rate limit over a blanket challenge so semantic distribution remains available.
