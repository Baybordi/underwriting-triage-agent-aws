"""
PIPELINE 3 — Data Protection (runtime)

Masks personal data (PII) in the submission text BEFORE it is sent to the LLM.
We only hide personal details (email, phone, postcode). Business details needed
for the decision (business type, city, sum insured, year) are kept.

This protects customer/broker privacy and keeps PII out of the prompt and logs.
"""

import re

# ============================================================
# PATTERNS — what counts as personal data
# ============================================================
# Email, e.g. john@shop.co.uk
EMAIL = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

# UK phone, e.g. 07700 900123 or +44 7700 900123
PHONE = r"(\+44\s?|0)\d{3,4}[\s-]?\d{3}[\s-]?\d{3,4}"

# UK postcode, e.g. SW1A 1AA
POSTCODE = r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b"


# ============================================================
# THE MASKING FUNCTION
# ============================================================
def mask_pii(text):
    """
    Replace personal data with safe placeholders.
    Returns (masked_text, found) where 'found' lists what was masked.
    """
    found = []

    def replace(pattern, label, value):
        nonlocal text
        if re.search(pattern, value):
            text = re.sub(pattern, f"[{label}]", text)
            found.append(label)

    replace(EMAIL, "EMAIL", text)
    replace(PHONE, "PHONE", text)
    replace(POSTCODE, "POSTCODE", text)

    return text, found


# ============================================================
# QUICK TEST (run this file directly to see it work)
# ============================================================
if __name__ == "__main__":
    sample = (
        "Business: Bakery, Leeds LS1 4DY. Contact: jane@bakery.co.uk, "
        "phone 07700 900123. Sum insured 450000. Built 1998."
    )
    masked, found = mask_pii(sample)
    print("Original:", sample)
    print("Masked  :", masked)
    print("Masked fields:", found)
