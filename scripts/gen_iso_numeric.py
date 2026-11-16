"""Write frontend/src/lib/iso-numeric.ts from the shared table (one source of truth)."""

from pathlib import Path

from whitespace_shared.country_codes import ISO_NUMERIC

OUT = Path(__file__).resolve().parents[1] / "frontend/src/lib/iso-numeric.ts"
rows = "\n".join(f'  {code}: "{num}",' for code, num in sorted(ISO_NUMERIC.items()))
OUT.write_text(
    "// ISO3 -> ISO 3166-1 numeric (world map outlines). Generated from\n"
    "// shared/src/whitespace_shared/country_codes.py by `make gen-client`; do not edit.\n\n"
    f"export const ISO_NUMERIC: Record<string, string> = {{\n{rows}\n}};\n"
)
