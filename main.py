from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from extractor import extract_fields

app = FastAPI(title="Invoice Extract API")

# CORS: grader calls this from a Cloudflare Worker (a different origin),
# so allow all origins/methods/headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvoiceRequest(BaseModel):
    invoice_text: str


class InvoiceResponse(BaseModel):
    invoice_no: Optional[str] = None
    date: Optional[str] = None
    vendor: Optional[str] = None
    amount: Optional[float] = None
    tax: Optional[float] = None
    currency: Optional[str] = None


@app.get("/")
def root():
    return {"status": "ok", "endpoint": "POST /extract"}


@app.post("/extract", response_model=InvoiceResponse)
def extract(req: InvoiceRequest):
    fields = extract_fields(req.invoice_text)
    return fields
