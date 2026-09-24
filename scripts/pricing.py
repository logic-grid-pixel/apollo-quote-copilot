"""Deterministic quote pricing. The model never computes a number; this does.

List prices come from reference/price_books.yaml for the deal's segment book.
All arithmetic is exact (fractions); money is rounded to cents and discounts to
two decimals only when the result is output.

Definitions
  line list    = unit list price x quantity x (months in the year / 12) for annual
                 lines; one-time lines are charged once, in year 1
  line net     = line list x (1 - line discount %)
                 discount precedence: per-line > per-year > deal-wide
  list TCV     = sum of line list over every year
  TCV          = sum of line net over every year
  ACV          = net of RECURRING lines / term in years (one-time excluded)
  blended disc = 1 - TCV / list TCV   (value-weighted, NOT an average of yearly %)

Ramps: "Additional Seats" quantity per year comes from the ramp schedule.

CLI:  python scripts/pricing.py <extraction.json> --segment Mid-Market [--discount-pct 12]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

import yaml

CATALOG = Path(__file__).resolve().parent.parent / "reference" / "price_books.yaml"
SEGMENTS = ("SMB", "Mid-Market", "Enterprise")
SEAT_PRODUCT = "Additional Seats"
MAX_TERM_MONTHS = 120
# Fields pricing itself needs. start_date is pricing-critical for the pre-flight
# (a quote cannot go out without it) but does not change any number here.
PRICING_FIELDS = ("products", "seat_count", "term_months", "requested_discount_pct")

CENT = Decimal("0.01")


class PricingError(ValueError):
    """Invalid pricing request (a bug in the caller, not an open question)."""


# --- helpers -------------------------------------------------------------------

def load_catalog(path: Path = CATALOG) -> dict:
    cfg = yaml.safe_load(Path(path).read_text())
    products = {p["name"]: {"code": p["code"], "unit": p["unit"],
                            "billing": p.get("billing", "annual")}
                for p in cfg["products"]}
    for name, p in products.items():
        if p["billing"] not in ("annual", "one_time"):
            raise PricingError(f"{name}: unknown billing '{p['billing']}' in {path}")
    return {"products": products, "books": cfg["price_books"]}


def to_fraction(x, what: str) -> Fraction:
    if isinstance(x, bool) or x is None:
        raise PricingError(f"{what} must be a number, got {x!r}")
    if isinstance(x, Fraction):
        return x
    try:
        return Fraction(str(x)) if isinstance(x, (float, str, Decimal)) else Fraction(x)
    except (ValueError, TypeError, ZeroDivisionError):
        raise PricingError(f"{what} must be a number, got {x!r}")


def _pct(x, what: str) -> Fraction:
    p = to_fraction(x, what)
    if p < 0 or p > 100:
        raise PricingError(f"{what} must be between 0 and 100, got {x!r}")
    return p


def _dec(f: Fraction) -> Decimal:
    return Decimal(f.numerator) / Decimal(f.denominator)


def money(f: Fraction) -> float:
    return float(_dec(f).quantize(CENT, rounding=ROUND_HALF_UP))


def pct2(f: Fraction) -> float:
    return float(_dec(f).quantize(CENT, rounding=ROUND_HALF_UP))


def fraction_str(f: Fraction) -> str:
    return f"{f.numerator}/{f.denominator}"


# --- core ------------------------------------------------------------------------

def _year_months(term_months: int) -> list:
    n = math.ceil(term_months / 12)
    return [min(12, term_months - 12 * i) for i in range(n)]


def _validate(req: dict, catalog: dict):
    segment = req.get("segment")
    if segment not in SEGMENTS:
        raise PricingError(f"segment must be one of {SEGMENTS}, got {segment!r}")
    term = req.get("term_months")
    if isinstance(term, bool) or not isinstance(term, int) or not 1 <= term <= MAX_TERM_MONTHS:
        raise PricingError(f"term_months must be an integer 1-{MAX_TERM_MONTHS}, got {term!r}")
    lines = req.get("lines") or []
    if not lines:
        raise PricingError("at least one line is required")
    seen = set()
    for ln in lines:
        name = ln.get("product")
        if name not in catalog["products"]:
            raise PricingError(f"unknown product {name!r}")
        if name not in catalog["books"].get(segment, {}):
            raise PricingError(f"{name!r} has no price in the {segment} book")
        if name in seen:
            raise PricingError(f"duplicate line for {name!r}")
        seen.add(name)
        q = ln.get("quantity")
        if isinstance(q, bool) or not isinstance(q, int) or q < 1:
            raise PricingError(f"{name}: quantity must be a positive integer, got {q!r}")


def _ramp_by_year(req: dict, n_years: int) -> dict:
    ramp = req.get("ramp")
    if not ramp:
        return {}
    seats_line = next((ln for ln in req["lines"] if ln["product"] == SEAT_PRODUCT), None)
    if seats_line is None:
        raise PricingError(f"a ramp needs an '{SEAT_PRODUCT}' line")
    by_year = {}
    for step in ramp:
        year, seats = step.get("year"), step.get("seats")
        if not isinstance(year, int) or not isinstance(seats, int) or seats < 1:
            raise PricingError(f"invalid ramp step {step!r}")
        by_year[year] = seats
    missing = [y for y in range(1, n_years + 1) if y not in by_year]
    if missing:
        raise PricingError(f"ramp has no seat count for year(s) {missing}")
    extra = [y for y in by_year if y > n_years or y < 1]
    if extra:
        raise PricingError(f"ramp has year(s) {extra} outside a {n_years}-year term")
    if by_year[1] != seats_line["quantity"]:
        raise PricingError(f"ramp year 1 ({by_year[1]}) != {SEAT_PRODUCT} quantity "
                           f"({seats_line['quantity']})")
    return by_year


def _discount_for(req: dict, product: str, year: int) -> Fraction:
    line_d = req.get("line_discounts") or {}
    if product in line_d:
        return _pct(line_d[product], f"line discount for {product}")
    year_d = {int(k): v for k, v in (req.get("year_discounts") or {}).items()}
    if year in year_d:
        return _pct(year_d[year], f"year {year} discount")
    if req.get("discount_pct") is not None:
        return _pct(req["discount_pct"], "discount_pct")
    raise PricingError(f"no discount given for {product} in year {year}")


def price_quote(req: dict, catalog: dict = None) -> dict:
    """Price a validated request. Raises PricingError on invalid input.

    req: {segment, term_months, lines: [{product, quantity}], ramp?: [{year, seats}],
          discount_pct?, year_discounts?: {year: pct}, line_discounts?: {product: pct}}
    """
    catalog = catalog or load_catalog()
    _validate(req, catalog)
    segment, term = req["segment"], req["term_months"]
    book = catalog["books"][segment]
    months = _year_months(term)
    ramp = _ramp_by_year(req, len(months))

    years, list_tcv, net_tcv = [], Fraction(0), Fraction(0)
    rec_list, rec_net, one_list, one_net = Fraction(0), Fraction(0), Fraction(0), Fraction(0)
    for i, m in enumerate(months):
        year = i + 1
        y_list, y_net, y_lines = Fraction(0), Fraction(0), []
        for ln in req["lines"]:
            name = ln["product"]
            billing = catalog["products"][name]["billing"]
            if billing == "one_time" and year != 1:
                continue
            qty = ramp.get(year, ln["quantity"]) if name == SEAT_PRODUCT else ln["quantity"]
            unit = to_fraction(book[name], f"{segment} price for {name}")
            proration = Fraction(m, 12) if billing == "annual" else Fraction(1)
            disc = _discount_for(req, name, year)
            lst = unit * qty * proration
            net = lst * (1 - disc / 100)
            y_list += lst
            y_net += net
            if billing == "annual":
                rec_list, rec_net = rec_list + lst, rec_net + net
            else:
                one_list, one_net = one_list + lst, one_net + net
            y_lines.append({
                "year": year, "product": name,
                "product_code": catalog["products"][name]["code"], "billing": billing,
                "quantity": qty, "unit_list_price": money(unit),
                "months": m if billing == "annual" else None,
                "proration": float(proration), "discount_pct": pct2(disc),
                "list_total": money(lst), "net_total": money(net),
            })
        list_tcv += y_list
        net_tcv += y_net
        years.append({"year": year, "months": m, "lines": y_lines,
                      "list_total": money(y_list), "net_total": money(y_net)})

    blended = (1 - net_tcv / list_tcv) * 100 if list_tcv else Fraction(0)
    term_years = Fraction(term, 12)
    return {
        "status": "priced",
        "segment": segment,
        "price_book": segment,
        "currency": "USD",
        "term_months": term,
        "ramped": bool(ramp),
        "years": years,
        "totals": {
            "list_tcv": money(list_tcv),
            "tcv": money(net_tcv),
            "acv": money(rec_net / term_years),
            "recurring_list": money(rec_list),
            "recurring_net": money(rec_net),
            "one_time_list": money(one_list),
            "one_time_net": money(one_net),
            "discount_amount": money(list_tcv - net_tcv),
            "blended_discount_pct": pct2(blended),
            "blended_discount_pct_exact": fraction_str(blended),
        },
    }


# --- extraction -> request -------------------------------------------------------

def field_value(extraction: dict, field: str):
    f = extraction.get(field)
    return f.get("value") if isinstance(f, dict) else f


def blocking_fields(extraction: dict) -> set:
    return {q.get("field") for q in extraction.get("open_questions") or []
            if q.get("blocking")}


def request_from_extraction(extraction: dict, segment: str, discount_pct=None,
                            catalog: dict = None) -> dict:
    """Build a pricing request, or a blocked result naming what is missing.

    Never fills a pricing field with a guess: a null value or a blocking open
    question on products / seat_count / term_months / requested_discount_pct
    (the latter only when no --discount-pct override is given) blocks pricing.
    """
    catalog = catalog or load_catalog()
    blocking = blocking_fields(extraction)
    blocked, reasons, assumptions = [], [], []

    def block(field, why):
        if field not in blocked:
            blocked.append(field)
        reasons.append(f"{field}: {why}")

    needed = [f for f in PRICING_FIELDS
              if not (f == "requested_discount_pct" and discount_pct is not None)]
    for f in needed:
        if f in blocking:
            block(f, "blocking open question")
        elif field_value(extraction, f) is None:
            block(f, "not stated (null); will not guess")

    seat_count = field_value(extraction, "seat_count")
    products = field_value(extraction, "products") or []
    lines = []
    for p in products:
        name, qty = p.get("name"), p.get("quantity")
        if name not in catalog["products"]:
            block("products", f"unknown product {name!r}")
            continue
        if name == SEAT_PRODUCT:
            if qty is None:
                qty = seat_count
            elif seat_count is not None and qty != seat_count:
                block("seat_count", f"{SEAT_PRODUCT} quantity {qty} != seat_count {seat_count}")
        elif qty is None and catalog["products"][name]["unit"] == "Each":
            qty = 1
            assumptions.append(f"{name}: quantity not stated, priced as 1 (single subscription)")
        if qty is not None:
            lines.append({"product": name, "quantity": qty})
    if seat_count is not None and products and not any(
            p.get("name") == SEAT_PRODUCT for p in products):
        lines.append({"product": SEAT_PRODUCT, "quantity": seat_count})
        assumptions.append(f"seat_count {seat_count} added as {SEAT_PRODUCT} "
                           "(seats are always sold as Additional Seats)")

    ramp = field_value(extraction, "ramp")
    if "ramp" in blocking:
        block("ramp", "blocking open question")
    if ramp:
        first = next((s.get("seats") for s in ramp if s.get("year") == 1), None)
        if seat_count is not None and first != seat_count:
            block("ramp", f"ramp year 1 seats {first} != seat_count {seat_count}")

    if blocked:
        return {"status": "blocked", "blocked_fields": blocked, "reasons": reasons}

    discount = discount_pct if discount_pct is not None \
        else field_value(extraction, "requested_discount_pct")
    return {"status": "ok", "assumptions": assumptions, "request": {
        "segment": segment, "term_months": field_value(extraction, "term_months"),
        "lines": [ln for ln in lines if ln["quantity"] is not None],
        "ramp": ramp or None, "discount_pct": discount}}


def price_extraction(extraction: dict, segment: str, discount_pct=None,
                     catalog: dict = None) -> dict:
    catalog = catalog or load_catalog()
    built = request_from_extraction(extraction, segment, discount_pct, catalog)
    if built["status"] == "blocked":
        return {**built, "segment": segment}
    try:
        result = price_quote(built["request"], catalog)
    except PricingError as e:
        return {"status": "blocked", "segment": segment, "blocked_fields": ["request"],
                "reasons": [f"invalid pricing input: {e}"]}
    result["assumptions"] = built["assumptions"]
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Price an extraction deterministically")
    parser.add_argument("extraction", type=Path)
    parser.add_argument("--segment", required=True, choices=SEGMENTS,
                        help="price book to use (normally the Apollo-verified segment)")
    parser.add_argument("--discount-pct", type=float, default=None,
                        help="deal-wide discount override; default is requested_discount_pct")
    args = parser.parse_args(argv)
    extraction = json.loads(args.extraction.read_text())
    print(json.dumps(price_extraction(extraction, args.segment, args.discount_pct), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
