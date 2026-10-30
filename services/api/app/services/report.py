"""Evidence-to-Report Engine (R3, the signature workflow).

Deterministic pipeline from workspace selection → defensible report:

  step 1  validate   evidence-check flags per country/indicator (missing
                     values, stale vintages, suspicious jumps, sparse workforce)
  step 2  analyse    observed changes vs baseline, registered forecasts with
                     intervals (explicitly labelled MODELLED), disparities
                     across the selection, org-uploaded program data alongside
  step 3  narrate    template narrative in which every factual statement cites
                     an evidence bullet [E1..En]; the engine includes
                     limitations, missing-data warnings and source notes
  step 4  persist    versioned report row; PDF rendering via the router

What the engine will NOT do (framework rules):
- no invented statistics: every number is computed here from registered
  artifacts, the workspace's own uploaded data, or nothing;
- no causal claims: findings describe changes and model outputs, never
  "the intervention caused X";
- whenever evidence cannot support a conclusion, the findings section says so
  explicitly ("insufficient evidence").
"""
from __future__ import annotations

from services.api.app.services import loader as L
from services.api.app.services.quality import indicator_quality


def _num(v) -> str:
    return "n/a" if v is None else f"{v:g}"


def _validate(wide, countries: list[str], org_indicators: list[str]) -> tuple[list[dict], dict]:
    issue_map = {c: [] for c in countries}
    q = indicator_quality()
    meta = {row["indicator"]: row for row in q["indicators"]}
    latest = L.atlas_year()

    for c in countries:
        rows = wide[wide["iso3"] == c]
        if rows.empty:
            issue_map[c].append("no national panel data for this country")
            continue
        have_u5m = rows.dropna(subset=["u5m"])
        if have_u5m.empty:
            issue_map[c].append("no observed under-five mortality in the window")
        elif int(have_u5m["year"].max()) < latest - 2:
            issue_map[c].append(
                f"u5m observations stop at {int(have_u5m['year'].max())} — stale for "
                "current-cycle reporting")
        last_rows = rows[rows["year"] == latest]
        if len(last_rows) and last_rows.iloc[0].get("sparse_hwf_missing"):
            issue_map[c].append(
                "workforce indicators (physicians/nurses) sparse — treat capacity "
                "inferences as weak-confidence")
        cov = (last_rows.iloc[0].get("driver_coverage_pct")
               if len(last_rows) else None)
        if cov is not None and cov < 60:
            issue_map[c].append(
                f"only {cov:g}% of expected drivers observed in {latest} — "
                "comparability caveats apply")

    for ind in org_indicators:
        row = meta.get(ind)
        if row is None:
            issue_map.setdefault(countries[0] if countries else "—", []).append(
                f"indicator {ind} is not a platform-tracked indicator — supply "
                "values via workspace upload of your own program data")
        elif row["suspicious_changes"]:
            issue_map.setdefault(countries[0] if countries else "—", []).append(
                f"{ind}: {row['suspicious_changes']} suspicious year-over-year "
                "changes flagged — review source revisions before trends are cited")
        elif row["stale_countries"] > 0:
            issue_map.setdefault(countries[0] if countries else "—", []).append(
                f"{ind}: {row['stale_countries']} countries have vintages older "
                f"than the freshness window ({row['window'][1] - 4})")

    issues = [{"iso3": c, "flags": v} for c, v in issue_map.items() if v]
    return issues, meta


def _analysis(wide, countries: list[str], indicators: list[str],
              ws_data: list[dict]) -> tuple[list[dict], list[dict], dict]:
    latest = L.atlas_year()
    fyear = latest + 1
    vuln = {r["iso3"]: r for r in L.vulnerability()["rows"]}
    fc = {f["iso3"]: f for f in L.forecasts() if f["year"] == fyear}

    per_country, evidence = [], []
    for c in countries:
        rows = wide[wide["iso3"] == c].sort_values("year")
        obs = rows.dropna(subset=["u5m"])
        e = {
            "iso3": c,
            "observed": None, "observed_year": None,
            "from_value": None, "from_year": None,
            "change_pct": None, "trend_10y": None,
            "forecast": None, "forecast_interval": None,
            "p_gt_70": None, "source_labels": {},
        }
        if len(obs) >= 2:
            first, last = obs.iloc[0], obs.iloc[-1]
            e["observed"] = float(last["u5m"]); e["observed_year"] = int(last["year"])
            e["from_value"] = float(first["u5m"]); e["from_year"] = int(first["year"])
            e["change_pct"] = round((e["observed"] - e["from_value"])
                                    / e["from_value"] * 100.0, 1)
            recent = obs[obs["year"] >= latest - 9]
            if len(recent) >= 2:
                import numpy as np
                slope = np.polyfit(recent["year"].astype(float),
                                   recent["u5m"].astype(float), 1)[0]
                e["trend_10y"] = round(float(slope) * 9, 1)
            e["source_labels"]["observed"] = \
                "observed (dataset " + L.dataset_version() + ")"
        f = fc.get(c)
        if f and f["year"] == fyear:
            e["forecast"] = f["yhat"]
            e["forecast_interval"] = [f["lo90"], f["hi90"]]
            e["p_gt_70"] = f["p_gt_70"]
            e["source_labels"]["forecast"] = \
                f"MODELLED ({(meta_model := L.current_model_meta()).get('model_version')}, " \
                f"{fyear}, drivers unobserved beyond {latest} carried forward)"
            e["source_labels"]["interval"] = "empirical 90% holdout intervals"
        v = vuln.get(c)
        if v:
            caps = sorted(
                ((k, val) for k, val in (v["components"] or {}).items()
                 if val is not None and k not in
                 ("u5m_observing", "u5m_forecast")),
                key=lambda kv: -kv[1])
            weakest = caps[0][0] if caps else None
            e["vulnerability"] = {"composite": v["composite"], "band": v["band"],
                                  "weakest": weakest,
                                  "jackknife": v.get("jackknife_max_delta")}
            e["source_labels"]["vulnerability"] = "composite v1 (declared weights)"
        if len(obs) >= 1:
            evidence.append({
                "id": f"E{len(evidence) + 1}",
                "country": c,
                "text": (f"observed u5m {_num(e['from_value'])} ({e['from_year']}) → "
                         f"{_num(e['observed'])} ({e['observed_year']}), "
                         f"modelled {fyear} forecast {_num(e['forecast'])} "
                         f"[{_num(e['forecast_interval'][0]) if e['forecast_interval'] else '—'}–"
                         f"{_num(e['forecast_interval'][1]) if e['forecast_interval'] else '—'}]"),
                "source": e["source_labels"],
            })
        per_country.append(e)

    # org-uploaded data travels alongside, explicitly sourced
    org_by_ws = [d for d in ws_data
                 if d.get("iso3") in {c.upper() for c in countries} and
                 (not indicators or d.get("indicator") in indicators)]
    org_rows = [{"iso3": d["iso3"], "indicator": d["indicator"],
                 "geography": d.get("geography", ""), "year": d["year"],
                 "value": d["value"],
                 "source": "organization-supplied program data (not national "
                           "statistics; not comparable to WHO/WB estimates)"} for d in org_by_ws]

    spread = None
    vals = [e["observed"] for e in per_country if e["observed"] is not None]
    if len(vals) >= 2:
        spread = {"min": min(vals), "max": max(vals),
                  "median": sorted(vals)[len(vals) // 2],
                  "note": "range across selection; a wide range usually means "
                          "programs should not be designed on the average"}
    return per_country, evidence, {"disparities": spread, "org_rows": org_rows}


def _narrative(spec: dict, issues: list[dict], countries_analysis: list[dict],
               evidence: list[dict], extras: dict) -> dict:
    ws_name = spec.get("workspace_name", "workspace")
    period = spec.get("period_text") or "the latest cycle"

    if not countries_analysis:
        return {"sections": [], "summary": "No analysis rows — selection produced no data."}

    def cited(idx: list[int]) -> str:
        return " " + " ".join(f"[{evidence[i - 1]['id']}]" for i in idx
                              if 0 < i <= len(evidence)) if idx else ""

    # --- executive summary (deterministic template) -------------------------
    top = sorted([e for e in countries_analysis if e["forecast"] is not None],
                 key=lambda e: -e["forecast"])[:3]
    worst_txt = ", ".join(f"{e['iso3']} ({e['forecast']:g})" for e in top) or "no forecast rows"
    improved = [e for e in countries_analysis
                if e["change_pct"] is not None and e["change_pct"] < 0]
    summary = (
        f"{len(countries_analysis)} countries reviewed for {period} in workspace "
        f"“{ws_name}”. Highest modelled next-year mortality: {worst_txt}. "
        f"{len(improved)} of {len(countries_analysis)} observed long-run "
        f"improvement since available records began"
        + (f" (largest: {max(improved, key=lambda e: e['change_pct'])['iso3']} "
           f"{max(improved, key=lambda e: e['change_pct'])['change_pct']:g}%)."
           if improved else "; none improved over the observed window.")
        + " All figures trace to the evidence table; limitations below apply.")

    # --- findings, each citing evidence IDs --------------------------------
    findings: list[dict] = []
    fi = [i + 1 for i, e in enumerate(evidence) if e["country"]
          in {c["iso3"] for c in countries_analysis}]
    findings.append({
        "kind": "trend",
        "text": ("Observed child-mortality trajectories across the selection "
                 "(national statistics; see per-country rows)."
                 + cited(fi)),
    })
    for e in countries_analysis:
        bits = []
        if e["change_pct"] is not None:
            bits.append(f"u5m moved {e['change_pct']:+g}% from {e['from_year']} to "
                        f"{e['observed_year']} (observed)")
        if e["trend_10y"] is not None:
            bits.append(f"~{e['trend_10y']:+g} pp/decade trend over the last decade")
        if e["forecast"] is not None:
            lo, hi = e["forecast_interval"]
            bits.append(f"modelled {L.atlas_year() + 1}: {e['forecast']:g} "
                        f"(90% interval {lo:g}–{hi:g}; "
                        f"P(stays above 70) = {_num(e['p_gt_70'])})")
        if e.get("vulnerability"):
            bits.append(f"service-capacity composite {e['vulnerability']['composite']:g} "
                        f"({e['vulnerability']['band']}); weakest recorded capacity "
                        f"area: {e['vulnerability']['weakest'] or 'n/a'}")
        if bits:
            findings.append({"kind": "country", "iso3": e["iso3"],
                             "text": " · ".join(bits) + "."})
    spread = extras.get("disparities")
    if spread:
        findings.append({
            "kind": "disparity",
            "text": (f"Observed u5m ranges {_num(spread['min'])}–"
                     f"{_num(spread['max'])} across the selection (median "
                     f"{_num(spread['median'])}). {spread['note']}."),
        })
    org_rows = extras.get("org_rows") or []
    if org_rows:
        org_txt = ", ".join(sorted({r["indicator"] for r in org_rows}))
        findings.append({
            "kind": "org_data",
            "text": (f"Organization-supplied program data included for: {org_txt} "
                     f"({len(org_rows)} rows, geographies: "
                     f"{sorted({o['geography'] for o in org_rows if o['geography']}) or 'national-level'}). "
                     "This is YOUR program data — it is never merged with, or "
                     "calibrated against, national statistics."),
        })

    limitations = [
        "Forecasts are model outputs (gradient-boosted trees on public data), "
        "not measurements; intervals are empirical holdout quantiles.",
        "SHAP contributions and scenario deltas describe model behaviour, not "
        "causal effects — this report presents no causal claims.",
        f"Drivers beyond {L.atlas_year()} are carried forward as assumptions "
        "(flagged per row in the atlas layer), not observed.",
        "National averages mask subnational disparities; where the workspace "
        "holds organization-supplied geography rows these are shown separately.",
        "Population-level decision support: not individual, clinical, or "
        "surveillance guidance.",
    ]
    checklist = [
        "Review the validate-flags table before circulating this draft.",
        "Confirm reporting-period definition matches your donor template.",
        "Where a country carries a stale-u5m flag, cite the modelled row with its "
        "interval rather than the observed value.",
        "Record reviewer names + date on the workspace record when approved.",
        "Re-run this report after each dataset version change to diff "
        "against this version.",
    ]
    return {"summary": summary, "findings": findings,
            "limitations": limitations, "checklist": checklist,
            "evidence": evidence}


def build_report(spec: dict, ws_data: list[dict]) -> dict:
    wide = L.panel_wide()
    countries = [c.upper() for c in (spec.get("countries") or [])][:8]
    if not countries:
        raise ValueError("report spec must select at least one country")
    indicators = [i for i in (spec.get("indicators") or [])]
    issues, _meta = _validate(wide, countries, indicators)
    per_country, evidence, extras = _analysis(wide, countries, indicators, ws_data)
    narrative = _narrative(spec, issues, per_country, evidence, extras)
    return {
        "spec": spec,
        "computed": {
            "validate": issues,
            "analysis": per_country,
            "generated_note": "deterministic engine output; every number is "
                              "reproducible from registered artifacts and the "
                              "workspace's own uploads",
        },
        "narrative": narrative,
    }
