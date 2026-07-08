from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dateutil import parser
import re

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InvoiceRequest(BaseModel):
    invoice_text: str


def clean_amount(value):
    if value is None:
        return None

    value = value.replace(",", "")
    value = re.sub(r"[^\d.]", "", value)

    try:
        return float(value)
    except:
        return None


def parse_date(text):
    try:
        return parser.parse(text, dayfirst=True).date().isoformat()
    except:
        return None


@app.post("/extract")
def extract(req: InvoiceRequest):

    text = req.invoice_text

    result = {
        "invoice_no": None,
        "date": None,
        "vendor": None,
        "amount": None,
        "tax": None,
        "currency": None
    }

    # Invoice Number
    patterns = [
        r"Invoice\s*No[:\s]*([A-Za-z0-9\-\/]+)",
        r"Ref[:\s]*([A-Za-z0-9\-\/]+)"
    ]

    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            result["invoice_no"] = m.group(1).strip()
            break

    # Vendor
    vendor_patterns = [
        r"Vendor[:\s]*(.+)",
        r"^(.*?)\s+[—-]\s+Tax Invoice"
    ]

    for p in vendor_patterns:
        m = re.search(p, text, re.I | re.M)
        if m:
            result["vendor"] = m.group(1).strip()
            break

    # Date
    date_patterns = [
        r"Date[:\s]*(.+)",
        r"Issued[:\s]*(.+)"
    ]

    for p in date_patterns:
        m = re.search(p, text, re.I)
        if m:
            result["date"] = parse_date(m.group(1))
            break

    # Subtotal
    m = re.search(r"Subtotal.*?Rs\.?\s*([\d,]+\.\d+)", text, re.I)
    if m:
        result["amount"] = clean_amount(m.group(1))

    # Tax
    m = re.search(
        r"(?:GST|CGST|SGST|IGST|Tax).*?Rs\.?\s*([\d,]+\.\d+)",
        text,
        re.I,
    )
    if m:
        result["tax"] = clean_amount(m.group(1))

    # Currency
    m = re.search(r"Currency[:\s]*([A-Z]{3})", text)
    if m:
        result["currency"] = m.group(1)
    elif "Rs" in text or "₹" in text:
        result["currency"] = "INR"

    return result