"""A minimal PDF writer for fixtures (Helvetica, one text line per `Tj`), so tests can make
real PDFs without a PDF library. Regenerate the committed fixture PDFs with
`uv run python tests/pdfgen.py`."""

from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def _escape(line: str) -> str:
    return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[str]) -> bytes:
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    kids, n = [], 4
    for text in pages:
        ops = ["BT", "/F1 10 Tf", "13 TL", "40 800 Td"]
        ops += [f"({_escape(line)}) Tj T*" for line in text.splitlines()]
        stream = "\n".join([*ops, "ET"]).encode("latin-1")
        objs[n] = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                   b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % (n + 1))
        objs[n + 1] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
        kids.append(n)
        n += 2
    refs = " ".join(f"{k} 0 R" for k in kids).encode()
    objs[2] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (refs, len(kids))
    out, offsets = b"%PDF-1.4\n", {}
    for i in sorted(objs):
        offsets[i] = len(out)
        out += b"%d 0 obj\n%s\nendobj\n" % (i, objs[i])
    xref, size = len(out), max(objs) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % size
    out += b"".join(b"%010d 00000 n \n" % offsets[i] for i in range(1, size))
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)
    return out


def write_fixtures() -> None:
    funding = FIXTURES / "funding"
    for name in ("deliverable_knitpass_d2_1", "deliverable_sortwise_d3_2"):
        pages = (funding / f"{name}.txt").read_text(encoding="utf-8").split("\n\f\n")
        (funding / f"{name}.pdf").write_bytes(make_pdf(pages))


if __name__ == "__main__":
    write_fixtures()
