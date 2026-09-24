"""Deterministic quote pre-flight: approval level, breaches, status, alternative.

Every threshold comes from reference/approval_policy.yaml. Inputs are the
Apollo-verified segment, the rep's segment, the effective (blended) discount
from pricing.py, payment terms, and the extraction's open questions / nulls.

Status precedence: Blocked on Open Questions > Needs Approval > Ready.

CLI:  python scripts/preflight.py <extraction.json> [--refresh-apollo]
      verified segment from apollo_client (cached), effective discount from pricing.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path
from typing import Optional

import yaml

import apollo_client
import pricing

POLICY = Path(__file__).resolve().parent.parent / "reference" / "approval_policy.yaml"
BLOCKED, NEEDS_APPROVAL, READY = "Blocked on Open Questions", "Needs Approval", "Ready"
UNVERIFIED = "Unverified"
NET_RE = re.compile(r"^\s*net\s*-?\s*(\d+)\s*(days?)?\s*$", re.IGNORECASE)


class PolicyError(ValueError):
    pass


# --- policy ---------------------------------------------------------------------------

def load_policy(path: Path = POLICY) -> dict:
    p = yaml.safe_load(Path(path).read_text())
    levels = p["levels"]
    for seg, cfg in p["segments"].items():
        prev = Fraction(-1)
        for band in cfg["bands"]:
            if band["level"] not in levels:
                raise PolicyError(f"{seg}: unknown level {band['level']!r}")
            mx = pricing.to_fraction(band["max_discount_pct"], f"{seg} band")
            if mx <= prev:
                raise PolicyError(f"{seg}: bands must be ascending")
            prev = mx
        if pricing.to_fraction(cfg["ceiling_pct"], f"{seg} ceiling") != prev:
            raise PolicyError(f"{seg}: ceiling_pct {cfg['ceiling_pct']} must equal the last "
                              f"band's max_discount_pct {prev}")
    if p["above_ceiling"]["level"] not in levels or p["payment_terms"]["min_level"] not in levels:
        raise PolicyError("above_ceiling / payment_terms level not in levels")
    if p["status_precedence"] != [BLOCKED, NEEDS_APPROVAL, READY]:
        raise PolicyError(f"status_precedence must be {[BLOCKED, NEEDS_APPROVAL, READY]}")
    return p


def discount_approval(policy: dict, segment: str, discount_pct):
    """Return (level, ceiling_breached) for a discount in a segment. Exact comparison."""
    if segment not in policy["segments"]:
        raise PolicyError(f"no bands for segment {segment!r}")
    d = pricing.to_fraction(discount_pct, "discount")
    for band in policy["segments"][segment]["bands"]:
        if d <= pricing.to_fraction(band["max_discount_pct"], "band"):
            return band["level"], False
    return policy["above_ceiling"]["level"], True


def payment_terms_days(terms) -> Optional[int]:
    m = NET_RE.match(str(terms)) if terms is not None else None
    return int(m.group(1)) if m else None


def _max_level(policy: dict, *levels) -> Optional[str]:
    known = [lv for lv in levels if lv is not None]
    return max(known, key=policy["levels"].index) if known else None


def _overall_level(policy, segment, discount, terms_breached):
    if discount is None or segment is None:
        return None, False
    level, ceiling_breached = discount_approval(policy, segment, discount)
    if terms_breached:
        level = _max_level(policy, level, policy["payment_terms"]["min_level"])
    return level, ceiling_breached


def _terms_breached(policy, terms) -> bool:
    if terms is None:
        return False
    days = payment_terms_days(terms)
    return days is None or days > policy["payment_terms"]["standard_max_days"]


def _pct_out(f) -> Optional[float]:
    if f is None:
        return None
    return float(pricing._dec(f).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# --- core evaluation (pure) -----------------------------------------------------------

def evaluate(policy: dict, *, rep_segment, verified_segment, effective_discount_pct,
             payment_terms, blocked_fields, open_questions=None) -> dict:
    segments = policy["segments"]
    rep = rep_segment if rep_segment in segments else None
    verified = verified_segment if verified_segment in segments else None
    discount = None if effective_discount_pct is None else \
        pricing.to_fraction(effective_discount_pct, "effective discount")
    reasons, breaches = [], []

    mismatch = bool(rep and verified and rep != verified)
    if verified:
        band_segment = verified
    else:
        band_segment = rep
        reasons.append("Apollo has no employee count for this account: segment unverified, "
                       f"bands taken from the rep's segment ({rep or 'not stated'}); "
                       "Deal Desk to confirm")
    if mismatch:
        reasons.append(f"Rep segment {rep} differs from Apollo-verified {verified}: "
                       f"bands and price book use {verified}; Deal Desk review")
    if rep_segment is not None and rep is None:
        reasons.append(f"Rep segment {rep_segment!r} is not a known segment")

    terms_breached = _terms_breached(policy, payment_terms)
    if payment_terms is None:
        reasons.append("Payment terms not stated; standard "
                       f"{policy['payment_terms']['standard']} will apply unless agreed otherwise")
    elif terms_breached:
        breaches.append(policy["payment_terms"]["threshold"])
        reasons.append(f"Payment terms {payment_terms} exceed standard "
                       f"{policy['payment_terms']['standard']}: at least "
                       f"{policy['payment_terms']['min_level']} approval")

    level, ceiling_breached = _overall_level(policy, band_segment, discount, terms_breached)
    if discount is not None and band_segment is not None:
        d_level, _ = discount_approval(policy, band_segment, discount)
        if ceiling_breached:
            breaches.insert(0, policy["above_ceiling"]["threshold"])
            reasons.append(f"Effective discount {_pct_out(discount):.2f}% exceeds the "
                           f"{band_segment} ceiling of {segments[band_segment]['ceiling_pct']}%: "
                           f"{d_level} approval")
        else:
            reasons.append(f"Effective discount {_pct_out(discount):.2f}% is in the "
                           f"{band_segment} {d_level} band")
    elif discount is None:
        reasons.append("Effective discount unknown: approval level cannot be computed")

    rep_level = None
    if mismatch and discount is not None:
        rep_level, _ = _overall_level(policy, rep, discount, terms_breached)
        reasons.append(f"On the rep's {rep} segment this would need {rep_level} approval")

    blocked = list(dict.fromkeys(blocked_fields or []))
    if blocked:
        status = BLOCKED
        reasons.insert(0, "Blocked: pricing-critical field(s) unresolved: " + ", ".join(blocked))
    elif (level is None or level != policy["levels"][0] or breaches or mismatch
          or not verified):
        status = NEEDS_APPROVAL
    else:
        status = READY

    return {
        "rep_segment": rep_segment,
        "verified_segment": verified or UNVERIFIED,
        "band_segment": band_segment,
        "segment_mismatch": mismatch,
        "effective_discount_pct": _pct_out(discount),
        "approval_level_required": level,
        "approval_level_on_rep_segment": rep_level,
        "thresholds_breached": breaches,
        "preflight_status": status,
        "blocked_fields": blocked,
        "open_questions": list(open_questions or []),
        "reasons": reasons,
        "_discount": discount,
        "_terms_breached": terms_breached,
        "_payment_terms": payment_terms,
    }


# --- extraction helpers ----------------------------------------------------------------

def blocked_fields(extraction: dict, policy: dict = None) -> list:
    policy = policy or load_policy()
    blocking = pricing.blocking_fields(extraction)
    return [f for f in policy["pricing_critical_fields"]
            if f in blocking or pricing.field_value(extraction, f) is None]


def _tcv(extraction, segment, discount, catalog):
    if extraction is None or segment is None:
        return None
    r = pricing.price_extraction(extraction, segment, discount_pct=discount, catalog=catalog)
    return r["totals"]["tcv"] if r["status"] == "priced" else None


def _diff(a, b):
    if a is None or b is None:
        return None
    return float(Decimal(str(a)) - Decimal(str(b)))


def suggest(policy: dict, core: dict, extraction: dict = None, catalog: dict = None,
            requested_discount=None) -> Optional[dict]:
    """Deterministic alternative(s); TCV deltas computed with pricing.py when priceable."""
    options = []
    seg = core["band_segment"]
    discount = core["_discount"]
    terms_breached = core["_terms_breached"]
    new_discount, new_terms_breached = discount, terms_breached
    # Price alternatives the same way the quote is priced: a deal-wide discount.
    base_tcv = _tcv(extraction, seg, requested_discount, catalog) \
        if requested_discount is not None else None

    if core["blocked_fields"]:
        options.append({"type": "resolve_open_questions", "fields": core["blocked_fields"],
                        "text": "Resolve before the quote can be priced or sent: "
                                + ", ".join(core["blocked_fields"])})

    if seg and discount is not None:
        cfg = policy["segments"][seg]
        rep_max = cfg["bands"][0]["max_discount_pct"]
        if policy["above_ceiling"]["threshold"] in core["thresholds_breached"]:
            target, kind = cfg["ceiling_pct"], "hold_discount_at_ceiling"
        elif core["approval_level_required"] != policy["levels"][0] and \
                discount > pricing.to_fraction(rep_max, "rep max"):
            target, kind = rep_max, "discount_at_rep_limit"
        else:
            target = None
        if target is not None:
            new_discount = pricing.to_fraction(target, "target")
            level, _ = _overall_level(policy, seg, new_discount, terms_breached)
            alt_tcv = _tcv(extraction, seg, target, catalog)
            options.append({"type": kind, "discount_pct": target, "approval_level": level,
                            "tcv_at_requested": base_tcv, "tcv_at_alternative": alt_tcv,
                            "tcv_difference": _diff(alt_tcv, base_tcv)})

    if terms_breached:
        new_terms_breached = False
        level, _ = _overall_level(policy, seg, discount, False)
        options.append({"type": "standard_payment_terms",
                        "payment_terms": policy["payment_terms"]["standard"],
                        "approval_level": level})

    if core["segment_mismatch"]:
        rep_tcv = _tcv(extraction, core["rep_segment"], requested_discount, catalog)
        ver_tcv = _tcv(extraction, seg, requested_discount, catalog)
        options.append({"type": "requote_on_verified_segment", "price_book": seg,
                        "tcv_on_rep_segment_book": rep_tcv,
                        "tcv_on_verified_segment_book": ver_tcv,
                        "tcv_difference": _diff(ver_tcv, rep_tcv)})
    elif core["verified_segment"] == UNVERIFIED:
        options.append({"type": "verify_segment",
                        "text": "Confirm company headcount (Apollo has none) before approval"})

    if not options:
        return None
    all_level, _ = _overall_level(policy, seg, new_discount, new_terms_breached)
    return {"summary": _summary(options, seg), "options": options,
            "approval_level_if_all_applied": all_level}


def _money_str(x):
    return "n/a" if x is None else f"${x:,.2f}"


def _summary(options, seg) -> str:
    parts = []
    for o in options:
        t = o["type"]
        if t == "resolve_open_questions":
            parts.append(o["text"])
        elif t == "hold_discount_at_ceiling":
            parts.append(f"Hold the discount at the {seg} ceiling of {o['discount_pct']}% "
                         f"({o['approval_level']} approval; TCV {_money_str(o['tcv_at_alternative'])}, "
                         f"{_money_str(o['tcv_difference'])} more than requested) and offer the "
                         "difference as a non-price concession, e.g. price protection across the term")
        elif t == "discount_at_rep_limit":
            tcv = "" if o["tcv_at_alternative"] is None else \
                f" (TCV {_money_str(o['tcv_at_alternative'])})"
            parts.append(f"at {o['discount_pct']}% the deal needs only {o['approval_level']} "
                         f"approval{tcv}")
        elif t == "standard_payment_terms":
            parts.append(f"Move payment terms to {o['payment_terms']}")
        elif t == "requote_on_verified_segment":
            parts.append(f"Requote on the {o['price_book']} price book (TCV "
                         f"{_money_str(o['tcv_on_verified_segment_book'])} vs "
                         f"{_money_str(o['tcv_on_rep_segment_book'])} on the rep's book)")
        else:
            parts.append(o.get("text", t))
    return "; ".join(parts) + "."


def public(result: dict) -> dict:
    return {k: v for k, v in result.items() if not k.startswith("_")}


def preflight_extraction(extraction: dict, verified_segment, policy: dict = None,
                         catalog: dict = None) -> dict:
    policy = policy or load_policy()
    catalog = catalog or pricing.load_catalog()
    rep = pricing.field_value(extraction, "rep_stated_segment")
    band_segment = verified_segment if verified_segment in policy["segments"] else \
        (rep if rep in policy["segments"] else None)
    requested = pricing.field_value(extraction, "requested_discount_pct")

    blocked = blocked_fields(extraction, policy)
    priced = None
    if band_segment:
        priced = pricing.price_extraction(extraction, band_segment, catalog=catalog)
        if priced["status"] == "blocked":
            blocked += [f for f in priced["blocked_fields"] if f not in blocked]
    else:
        blocked.append("segment")

    if priced and priced["status"] == "priced":
        discount = Fraction(priced["totals"]["blended_discount_pct_exact"])
        source = "computed"
    elif requested is not None:
        discount, source = pricing.to_fraction(requested, "requested discount"), "requested"
    else:
        discount, source = None, None

    core = evaluate(policy, rep_segment=rep, verified_segment=verified_segment,
                    effective_discount_pct=discount,
                    payment_terms=pricing.field_value(extraction, "payment_terms"),
                    blocked_fields=blocked, open_questions=extraction.get("open_questions"))
    core["effective_discount_source"] = source
    core["suggested_alternative"] = suggest(policy, core, extraction, catalog, requested)
    core["pricing"] = priced
    return public(core)


def run(extraction: dict, refresh_apollo: bool = False) -> dict:
    """Pre-flight with the verified segment looked up in Apollo (cache first)."""
    domain = pricing.field_value(extraction, "account_domain")
    apollo = None
    if domain:
        try:
            apollo = apollo_client.organization_summary(domain, refresh=refresh_apollo)
        except (apollo_client.ApolloError, ValueError) as e:
            apollo = {"domain": domain, "error": str(e), "verified_segment": None}
    result = preflight_extraction(extraction, (apollo or {}).get("verified_segment"))
    result["apollo"] = apollo
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the quote pre-flight on an extraction")
    parser.add_argument("extraction", type=Path)
    parser.add_argument("--refresh-apollo", action="store_true",
                        help="re-fetch the organization from Apollo (1 credit)")
    args = parser.parse_args(argv)
    extraction = json.loads(args.extraction.read_text())
    print(json.dumps(run(extraction, args.refresh_apollo), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
