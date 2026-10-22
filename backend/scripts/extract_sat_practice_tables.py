"""
Task 8 — build app/modules/results/data/sat_paper_practice_tables.json from
the official College Board "Scoring Your Paper SAT Practice Test #N" PDFs.

Deterministic: reads the PDF text layer with poppler's `pdftotext` (no OCR,
no AI model) in two independent modes (-layout and -raw) and refuses to
write anything unless both modes yield exactly the same rows. Only the
LAST page carrying "Raw Score Conversion Table: Section Scores" is used —
the guides' own instructions point there ("…on page 5"); the small table on
page 2 is an illustration and is ignored.

The PDFs themselves are NOT stored in the repository; their SHA-256 is.

Usage (from backend/):
    python scripts/extract_sat_practice_tables.py OUT.json VERIFIED_AT 4=/path/guide4.pdf 5=/path/guide5.pdf ...
"""
import hashlib
import json
import re
import subprocess
import sys

TITLE = "Raw Score Conversion Table: Section Scores"
RW_MAX, MATH_MAX = 66, 54
GUIDE_URL = "https://satsuite.collegeboard.org/media/pdf/scoring-sat-practice-test-{n}-digital.pdf"


def _run(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def _page_count(pdf: str) -> int:
    return int(re.search(r"Pages:\s+(\d+)", _run("pdfinfo", pdf)).group(1))


def _table_page(pdf: str) -> int:
    pages = [p for p in range(1, _page_count(pdf) + 1) if TITLE in _run("pdftotext", "-layout", "-f", str(p), "-l", str(p), pdf, "-")]
    if not pages:
        raise SystemExit(f"{pdf}: no conversion table page")
    return pages[-1]


def _rows(text: str, after_title: bool = True) -> tuple[dict, dict, str]:
    """Rows after the table title: 'raw rwL rwU mL mU' blocks (5 numbers) or
    'raw rwL rwU' (3 numbers, R&W only); a line may hold two blocks.
    -raw output puts the title after the rows, so it is parsed whole
    (after_title=False); the two results must still be identical."""
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if TITLE in l) if after_title else -1
    rw: dict[int, tuple[int, int]] = {}
    math: dict[int, tuple[int, int]] = {}
    footer = ""
    for line in lines[start + 1:]:
        if "College Board" in line:
            footer = re.sub(r"\s+", " ", line.strip())
            if rw:          # -layout: footer follows the table; -raw: it may come first
                break
            continue
        parts = line.split()
        if not parts or not all(re.fullmatch(r"\d+", p) for p in parts):
            continue
        if len(parts) <= 2:  # page number / stray label, never a table row
            continue
        vals = [int(p) for p in parts]
        if len(vals) == 10:
            blocks = [vals[:5], vals[5:]]
        elif len(vals) == 8:
            blocks = [vals[:5], vals[5:]]
        elif len(vals) in (5, 3):
            blocks = [vals]
        else:
            raise SystemExit(f"unexpected table line: {line!r}")
        for b in blocks:
            if b[0] in rw:
                raise SystemExit(f"duplicate raw {b[0]}")
            rw[b[0]] = (b[1], b[2])
            if len(b) == 5:
                math[b[0]] = (b[3], b[4])
    return rw, math, footer


def _check(name: str, table: dict, max_raw: int) -> list[dict]:
    if sorted(table) != list(range(max_raw + 1)):
        raise SystemExit(f"{name}: raw scores are not exactly 0..{max_raw}")
    anomalies = []
    prev = None
    for raw in range(max_raw + 1):
        lower, upper = table[raw]
        if not (200 <= lower <= upper <= 800) or lower % 10 or upper % 10:
            raise SystemExit(f"{name}: invalid range at raw {raw}: {lower}-{upper}")
        if prev is not None:
            for field, i in (("lower", 0), ("upper", 1)):
                if table[raw][i] < prev[i]:
                    anomalies.append({"raw": raw, "field": field, "previous_raw_value": prev[i], "value": table[raw][i]})
        prev = table[raw]
    return anomalies


def extract(n: int, pdf: str, verified_at: str) -> dict:
    page = _table_page(pdf)
    layout = _rows(_run("pdftotext", "-layout", "-f", str(page), "-l", str(page), pdf, "-"))
    raw_mode = _rows(_run("pdftotext", "-raw", "-f", str(page), "-l", str(page), pdf, "-"), after_title=False)
    if layout[0] != raw_mode[0] or layout[1] != raw_mode[1]:
        raise SystemExit(f"test {n}: -layout and -raw extractions differ — not writing")
    rw, math, footer = layout
    m = re.search(r"©\s*(\d{4}) College Board\.\s+(\S+)", footer)
    if not m:
        raise SystemExit(f"test {n}: footer not recognised: {footer!r}")
    page1 = [l.strip() for l in _run("pdftotext", "-layout", "-f", "1", "-l", "1", pdf, "-").splitlines() if l.strip()]
    title = " ".join(page1[:2])
    if title != f"Scoring Your Paper SAT Practice Test #{n}":
        raise SystemExit(f"test {n}: unexpected guide title {title!r}")
    info = _run("pdfinfo", pdf)
    sections = {}
    for key, table, max_raw in (("reading_writing", rw, RW_MAX), ("math", math, MATH_MAX)):
        sections[key] = {
            "raw_min": 0, "raw_max": max_raw,
            "entries": [{"raw": r, "lower": table[r][0], "upper": table[r][1]} for r in range(max_raw + 1)],
            "source_anomalies": _check(f"test {n} {key}", table, max_raw),
        }
    return {
        "form_id": f"sat_practice_test_{n}",
        "practice_test_number": n,
        "guide_title": title,
        "pdf_metadata_title": re.search(r"Title:\s+(.*)", info).group(1).strip(),
        "document_code": m.group(2),
        "copyright_year": int(m.group(1)),
        "source_url": GUIDE_URL.format(n=n),
        "pdf_sha256": hashlib.sha256(open(pdf, "rb").read()).hexdigest(),
        "table_page": page,
        "verified_at": verified_at,
        "verification_method": "pdftotext -layout and -raw of the conversion-table page; both identical",
        "scope": "paper (nonadaptive) version of the digital SAT practice test; practice estimate, not an official SAT score",
        "sections": sections,
    }


def main() -> None:
    out, verified_at, *pairs = sys.argv[1:]
    forms = {}
    for pair in pairs:
        n, pdf = pair.split("=", 1)
        forms[f"sat_practice_test_{int(n)}"] = extract(int(n), pdf, verified_at)
    dataset = {
        "dataset": "sat_paper_practice_tables",
        "description": ("Official College Board raw-score conversion tables (lower/upper section score) for the paper "
                        "(nonadaptive) versions of the digital SAT Practice Tests. Exact values, not interpolated."),
        "rules": {"reading_writing_raw": "0-66 (two modules of 0-33)", "math_raw": "0-54 (two modules of 0-27)",
                  "total_range": "sum of the two section lower values .. sum of the two section upper values"},
        "forms": forms,
    }
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(dataset, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    for f in forms.values():
        notes = [f"{k}: {a}" for k, s in f["sections"].items() for a in s["source_anomalies"]]
        print(f"{f['form_id']}: {f['document_code']} (© {f['copyright_year']}) page {f['table_page']} anomalies={notes or 'none'}")


if __name__ == "__main__":
    main()
