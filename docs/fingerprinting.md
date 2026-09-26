# TC-FP-1 fingerprint contract

`documentHash = SHA256(original uploaded bytes)`. No PDF rewriting occurs. A trailing
newline or PDF metadata edit changes that hash. The business fingerprint never includes
the PDF bytes, filename, storage key, document hash, due date or database/asset ID.

## Canonical identity

Keys are serialized in exactly this order, as compact JSON with no spaces, encoded as
UTF-8 with no BOM or trailing newline:

```json
{"version":"TC-FP-1","exporterId":"ORG_EXPORTER_ALPHA","buyerId":"BUYER-DE-001","invoiceNumber":"EXP-2026-1042","currency":"EUR","amountMinor":1080000,"invoiceDate":"2026-09-21"}
```

SHA-256 of those bytes:
`febfe7ea6bba251d86dcbc6444a714a1da9e2797ec8959f5ae910a3d2140453b`.

- Exporter identity comes from the authenticated organization, never uploaded metadata.
- IDs: trim surrounding whitespace, uppercase ASCII letters, preserve digits/hyphens/
  underscores. Reject internal whitespace, unsupported punctuation and non-ASCII lookalikes.
- Invoice numbers: remove whitespace, uppercase ASCII letters, preserve leading zeros.
  Plain alphanumeric inputs normalize to `[A-Z0-9]`. Preserve `-`, `/`, `.`, `_` because
  their business meaning is not known; do not collapse distinct invoice identifiers.
  Other punctuation and non-ASCII characters are rejected. At least one letter/digit
  is required. ` exp - 2026 - 1042 ` equals `EXP-2026-1042`; `EXP20261042` is distinct.
- Currency: trim, uppercase, validate against the locked ISO-4217 dataset. Reject codes
  without defined minor units (such as XAU), rather than assuming two decimals.
- Amount: accept plain positive decimal text, at most 19 integer and 4 fractional digits.
  Convert using the currency's exponent and Decimal, without rounding. Reject fractional
  minor units, floats, booleans, grouping, exponent notation, zero, negatives, nonfinite
  values, and values outside positive signed 64-bit range. Trailing zero decimals are
  allowed within those input limits. EUR/INR use 2 minor digits; JPY uses 0; KWD uses 3.
- Dates: trim and require valid ISO `YYYY-MM-DD`; no timestamps, timezone conversion,
  numeric timestamps or locale-dependent parsing. Due date is validated but is not identity.

Currency metadata is supplied by the pinned [iso4217 package](https://github.com/dahlia/iso4217).
PDF structural validation uses [pypdf PdfReader](https://pypdf.readthedocs.io/en/6.13.0/modules/PdfReader.html).
Changes to this canonicalization contract require a new fingerprint version and explicit
migration/interoperability planning, rather than silently rehashing existing records.

This is deterministic identity within the supported input convention, not proof of a
commercial invoice's authenticity or a guarantee against off-network fraud.
