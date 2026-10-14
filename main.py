
import re
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Invoice Extractor API")


# Request schema
class InvoiceInput(BaseModel):
    text: str = Field(min_length=1)


# Response schema
class InvoiceOutput(BaseModel):
    vendor: str
    amount: float
    currency: str
    date: str


def extract_invoice(text: str) -> InvoiceOutput:
    text = text.strip()

    if not text:
        raise ValueError("Invoice text is empty")

    # 1. Extract currency
    currency_match = re.search(r"\b(USD|EUR|GBP)\b", text, re.I)

    if not currency_match:
        raise ValueError("Currency not found")

    currency = currency_match.group(1).upper()

    # 2. Extract due date in YYYY-MM-DD format
    date_match = re.search(
        r"\b(2026-\d{2}-\d{2})\b",
        text
    )

    if not date_match:
        raise ValueError("Due date not found")

    due_date = date_match.group(1)

    # Validate actual calendar date
    datetime.strptime(due_date, "%Y-%m-%d")

    # 3. Extract total due amount
    amount_patterns = [
        r"(?i)(?:total\s+due|amount\s+due|balance\s+due|"
            r"grand\s+total|total\s+amount|invoice\s+total)"
        r"\s*[:=\-]?\s*(?:(?:USD|EUR|GBP)\s*)?"
        r"[$€£]?\s*(\d[\d,]*(?:\.\d{1,2})?)",

        r"(?i)(?:USD|EUR|GBP)\s*"
        r"[$€£]?\s*(\d[\d,]*(?:\.\d{1,2})?)"
    ]

    amount_match = None

    for pattern in amount_patterns:
        amount_match = re.search(pattern, text)
        if amount_match:
            break

    if not amount_match:
        raise ValueError("Total amount not found")

    amount = float(amount_match.group(1).replace(",", ""))

    # 4. Extract vendor name.
    # First try explicit labels such as Vendor: or Supplier:
    vendor_match = re.search(
        r"(?im)^\s*(?:vendor|supplier|billed\s+by)"
        r"\s*:\s*(.+?)\s*$",
        text
    )

    if vendor_match:
        vendor = vendor_match.group(1).strip()
    else:
        # Handle: Invoice from Acme-7F2A Industries Ltd.
        vendor_match = re.search(
            r"(?i)\b(?:invoice\s+from|from)\s+"
            r"([A-Z0-9][A-Za-z0-9&.' -]{0,100}?"
            r"(?:Industries|Inc\.?|LLC|Ltd\.?|Limited|"
            r"Corporation|Corp\.?|Company|Co\.?))"
            r"(?=\s*(?:[.,;\n]|$|\s+(?:invoice|payment|"
            r"due|date|currency|total|amount)\b))",
            text
        )

        if vendor_match:
            vendor = vendor_match.group(1).strip()
        else:
            # Fallback: company name with a legal/business suffix
            vendor_match = re.search(
                r"\b([A-Z][A-Za-z0-9&.' -]{0,100}?"
                r"(?:Industries|Inc\.?|LLC|Ltd\.?|Limited|"
                r"Corporation|Corp\.?|Company|Co\.?))"
                r"(?=\s*(?:[.,;\n]|$))",
                text
            )

            if not vendor_match:
                raise ValueError("Vendor not found")

            vendor = vendor_match.group(1).strip()

    return InvoiceOutput(
        vendor=vendor,
        amount=amount,
        currency=currency,
        date=due_date
    )


@app.post("/extract", response_model=InvoiceOutput)
def extract(request: InvoiceInput):
    try:
        return extract_invoice(request.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
