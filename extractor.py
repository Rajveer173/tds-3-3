"""
Invoice field extraction logic.

Uses layered regex heuristics (not a single rigid pattern) so it copes with
varied plain-text invoice layouts: label:value lines, aligned dot-leaders,
different date formats, and the Indian lakh-style number grouping
(e.g. 1,40,000.00) as well as standard thousands grouping (2,199.00).
"""

import re
from datetime import datetime
from typing import Optional


MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _to_number(raw: str) -> Optional[float]:
    """Convert a currency-formatted number string (Indian or Western grouping)
    into a float. Returns None if it can't be parsed."""
    if raw is None:
        return None
    cleaned = raw.strip()
    # drop currency symbols/words and stray spaces
    cleaned = re.sub(r"(rs\.?|inr|usd|\$|₹|eur|€|gbp|£)", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", "").strip()
    # keep only leading numeric portion (handles trailing text like "/hr")
    m = re.match(r"[-+]?\d+(\.\d+)?", cleaned)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _line_amount(raw: str) -> Optional[float]:
    """Extract the actual currency amount from a captured label line,
    ignoring any percentage-rate figures like '18%' or '(19%)' that may
    appear before or alongside the amount (e.g. 'GST 19%: Rs. 779.00',
    'Tax (18%) Rs. 395.82'). Picks the last remaining numeric token, since
    the rate — if present — comes before the amount in every format seen."""
    if raw is None:
        return None
    # strip out percentage mentions entirely, parens or not
    cleaned = re.sub(r"\(?\s*\d+(?:\.\d+)?\s*%\s*\)?", " ", raw)
    # drop currency symbols/words
    cleaned = re.sub(r"(rs\.?|inr|usd|\$|₹|eur|€|gbp|£)", " ", cleaned, flags=re.IGNORECASE)
    nums = re.findall(r"\d[\d,]*(?:\.\d+)?", cleaned)
    if not nums:
        return None
    last = nums[-1].replace(",", "")
    try:
        return float(last)
    except ValueError:
        return None


def _parse_date(raw: str) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()

    # ISO: 2026-01-22
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", raw)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return datetime(y, mo, d).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # 15 March 2026 / 15-Mar-2026 / 15/03/2026
    m = re.match(r"^(\d{1,2})[\s\-/]+([A-Za-z]+|\d{1,2})[\s\-/]+(\d{4})$", raw)
    if m:
        day, mon, year = m.groups()
        day = int(day)
        year = int(year)
        if mon.isdigit():
            month = int(mon)
        else:
            month = MONTHS.get(mon.lower())
        if month:
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except ValueError:
                return None

    # March 15, 2026
    m = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$", raw)
    if m:
        mon, day, year = m.groups()
        month = MONTHS.get(mon.lower())
        if month:
            try:
                return datetime(int(year), month, int(day)).strftime("%Y-%m-%d")
            except ValueError:
                return None

    return None


def _find_first(patterns, text, flags=re.IGNORECASE | re.MULTILINE):
    for pat in patterns:
        m = re.search(pat, text, flags)
        if m:
            return m.group(1).strip()
    return None


def extract_invoice_no(text: str) -> Optional[str]:
    patterns = [
        r"\binvoice\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Za-z0-9/_\-\.]+)",
        r"\bref\.?\s*(?:no\.?)?\s*[:\-]?\s*([A-Za-z0-9/_\-\.]+)",
        r"\bbill\s*(?:no\.?)?\s*[:\-]?\s*([A-Za-z0-9/_\-\.]+)",
    ]
    val = _find_first(patterns, text)
    if val:
        val = val.strip().rstrip(".,")
    return val


def extract_date(text: str) -> Optional[str]:
    patterns = [
        r"(?:^|\n)\s*invoice\s*date\b\s*[:\-]?\s*([^\n]+)",
        r"(?:^|\n)\s*dated\b\s*[:\-]?\s*([^\n]+)",
        r"(?:^|\n)\s*date\b\s*[:\-]?\s*([^\n]+)",
        r"(?:^|\n)\s*issued\b\s*[:\-]?\s*([^\n]+)",
    ]
    raw = _find_first(patterns, text)
    if not raw:
        return None
    raw = raw.strip()
    return _parse_date(raw)


def extract_vendor(text: str) -> Optional[str]:
    patterns = [
        r"(?:^|\n)\s*vendor\b\s*[:\-]?\s*([^\n]+)",
        r"(?:^|\n)\s*from\b\s*[:\-]?\s*([^\n]+)",
        r"(?:^|\n)\s*seller\b\s*[:\-]?\s*([^\n]+)",
        r"(?:^|\n)\s*supplier\b\s*[:\-]?\s*([^\n]+)",
    ]
    val = _find_first(patterns, text)
    if val:
        return val.strip()

    # Fallback: first non-empty line, if it doesn't look like a label:value
    # line (invoice no, date, ref, bill-to, etc.) or a generic document title.
    skip_labels = re.compile(
        r"^(invoice|tax\s*invoice|receipt|bill\s*to|client|customer|date|"
        r"ref\.?|dated|invoice\s*no\.?|invoice\s*number|invoice\s*#|"
        r"sub\s*-?\s*total|total|amount|due|balance|currency|"
        r"gst|igst|cgst|sgst|vat|tax|service\s*tax|"
        r"item(?:s)?|qty|quantity|description|price|rate)\b\s*[:\-]?",
        re.IGNORECASE,
    )
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if skip_labels.match(ln):
            continue
        cleaned = re.split(r"[—\-]\s*(tax\s*invoice|invoice|receipt)", ln, flags=re.IGNORECASE)[0].strip()
        if cleaned:
            return cleaned
        break
    return None


def extract_amount(text: str) -> Optional[float]:
    """Subtotal before tax."""
    patterns = [
        r"(?:^|\n)\s*sub\s*-?\s*total\b\s*[:\-.]*\s*([^\n]+)",
    ]
    raw = _find_first(patterns, text)
    if raw:
        return _line_amount(raw)
    return None


def extract_tax(text: str) -> Optional[float]:
    patterns = [
        r"(?:^|\n)\s*(?:gst|igst|cgst|sgst|vat|tax|service\s*tax)\b\s*(?:\([^)]*\))?\s*[:\-.]*\s*([^\n]+)",
    ]
    raw = _find_first(patterns, text)
    if raw:
        return _line_amount(raw)
    return None


def extract_currency(text: str) -> Optional[str]:
    m = re.search(r"(?:^|\n)\s*currency\s*[:\-]?\s*([A-Za-z]{3})", text, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    # Infer from symbols/words present in the text
    if re.search(r"\brs\.?\b|₹|\binr\b", text, re.IGNORECASE):
        return "INR"
    if re.search(r"\$|\busd\b", text, re.IGNORECASE):
        return "USD"
    if re.search(r"€|\beur\b", text, re.IGNORECASE):
        return "EUR"
    if re.search(r"£|\bgbp\b", text, re.IGNORECASE):
        return "GBP"
    return None


def extract_fields(invoice_text: str) -> dict:
    text = invoice_text or ""
    return {
        "invoice_no": extract_invoice_no(text),
        "date": extract_date(text),
        "vendor": extract_vendor(text),
        "amount": extract_amount(text),
        "tax": extract_tax(text),
        "currency": extract_currency(text),
    }