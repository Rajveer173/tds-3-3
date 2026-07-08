# Invoice Extract API

A `POST /extract` endpoint that reads raw invoice text and returns 6 structured
fields: `invoice_no`, `date`, `vendor`, `amount`, `tax`, `currency`.

## Files
- `main.py` — FastAPI app, CORS enabled (`allow_origins=["*"]`)
- `extractor.py` — regex-based field extraction logic
- `requirements.txt` — dependencies
- `samples.json` — the sample invoices used for local testing

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Test it:

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"invoice_text": "Invoice No: INV-2026-0041\nDate: 15 March 2026\nVendor: TechParts Pvt Ltd\nSubtotal: Rs. 2,199.00\nGST (18%): Rs. 395.82"}'
```

Expected:
```json
{"invoice_no":"INV-2026-0041","date":"2026-03-15","vendor":"TechParts Pvt Ltd","amount":2199.0,"tax":395.82,"currency":"INR"}
```

## Deploying publicly (pick one)

I can't create a public URL for you directly from this chat sandbox (no
outbound access to hosting providers), so use one of these — all free/fast:

### Option A — Cloudflare Tunnel (matches the task's own suggestion)
```bash
# in one terminal
uvicorn main:app --host 0.0.0.0 --port 8000

# in another terminal
cloudflared tunnel --url http://localhost:8000
```
`cloudflared` prints a public `https://<random>.trycloudflare.com` URL that
proxies straight to your local server. Your base URL for submission is that
link (endpoint: `<that-url>/extract`).

### Option B — Render.com (free tier, persistent)
1. Push this folder to a GitHub repo.
2. On render.com → New → Web Service → connect the repo.
3. Build command: `pip install -r requirements.txt`
   Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Deploy → Render gives you `https://<app>.onrender.com`.

### Option C — Railway / Fly.io
Same idea: push the repo, set the start command to
`uvicorn main:app --host 0.0.0.0 --port $PORT`, and use the platform's
generated public URL.

Whichever you choose, your submission URL is the base (e.g.
`https://xyz.trycloudflare.com`), and the grader will call
`POST https://xyz.trycloudflare.com/extract`.

## Design notes
- Numbers are parsed to handle both Western (`2,199.00`) and Indian
  lakh-style (`1,40,000.00`) thousands separators.
- Dates handle `YYYY-MM-DD`, `DD Month YYYY`, `DD/MM/YYYY`, and
  `Month DD, YYYY`, all normalized to `YYYY-MM-DD`.
- `amount` is strictly the subtotal line (before tax); `tax` is pulled from
  GST/IGST/CGST/SGST/VAT/Tax lines specifically, so the grand `TOTAL` line is
  never mistaken for either.
- Every field defaults to `null` if not found — all 6 keys are always present
  in the response.
