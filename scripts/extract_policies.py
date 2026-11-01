"""Extract store policies from PDF into Markdown using pypdf.

This script extracts text from 'data/politicas_da_loja.pdf' using pypdf's
layout mode. The resulting 'data/policies.md' is reviewed and structured
into 10 numbered sections for the agent's section-based policy tool.
"""

import argparse
from pathlib import Path
from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDF = REPO_ROOT / "data" / "politicas_da_loja.pdf"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "policies.md"


def extract_pages(pdf_path: Path) -> list[str]:
    """Extract layout-preserving text from each page in the PDF."""
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        # extraction_mode="layout" preserves spacing, lists, and tables better
        text = page.extract_text(extraction_mode="layout")
        pages.append(text)
    return pages


def clean_extracted_text(pages: list[str]) -> str:
    """Perform initial cleanup: remove running headers and page number footers."""
    cleaned_lines = []
    for page in pages:
        for line in page.splitlines():
            stripped = line.strip()
            # Remove running header present on pages 2-8
            if stripped == "Empório da Música Manual de Políticas e Procedimentos":
                continue
            # Remove page number footers (e.g. 'Página 2')
            if stripped.startswith("Página ") and stripped[7:].isdigit():
                continue
            cleaned_lines.append(line)
        cleaned_lines.append("")

    return "\n".join(cleaned_lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract store policies PDF to Markdown")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF, help="Path to policies PDF")
    parser.add_argument(
        "--output", "-o", type=Path, default=DEFAULT_OUTPUT, help="Output markdown path"
    )
    parser.add_argument(
        "--raw", action="store_true", help="Dump raw extracted text to output file"
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        raise FileNotFoundError(f"PDF file not found: {args.pdf}")

    print(f"Reading PDF from: {args.pdf}")
    pages = extract_pages(args.pdf)
    print(f"Extracted {len(pages)} pages successfully.")

    if args.raw or not args.output.exists():
        content = clean_extracted_text(pages)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(f"Saved extracted text to: {args.output}")
        print("Next step: review sections, headings, and tables in data/policies.md.")
    else:
        print(f"Output file already exists at: {args.output}")
        print("To overwrite with raw extraction, pass --raw.")


if __name__ == "__main__":
    main()

