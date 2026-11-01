"""Extract and structure store policies from PDF into clean Markdown.

This script parses 'data/politicas_da_loja.pdf' using pdfplumber to cleanly
extract text, tables, and section hierarchies. The resulting 'data/policies.md'
is structured with Markdown headings (## 1 to 10, ### subsections), GitHub-flavored
Markdown tables, and standardized lists. This ensures optimal readability for LLMs
and section-based policy tools.
"""

import argparse
import re
import unicodedata
from pathlib import Path
from typing import Any

import pdfplumber

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDF = REPO_ROOT / "data" / "politicas_da_loja.pdf"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "policies" / "policies.md"
DEFAULT_SECTIONS_DIR = REPO_ROOT / "data" / "policies"


def format_markdown_table(table_data: list[list[Any]]) -> str:
    """Convert raw 2D table cell data into a GitHub-flavored Markdown table."""
    if not table_data or len(table_data) < 1:
        return ""

    headers = [str(c or "").strip().replace("\n", " ") for c in table_data[0]]
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for row in table_data[1:]:
        cells = [str(c or "").strip().replace("\n", " ") for c in row]
        # Fix typo in table where e-mail has an accent
        cells = [
            c.replace("contato@empóriodamusica.com.br", "contato@emporiodamusica.com.br")
            for c in cells
        ]
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def slugify(text: str) -> str:
    """Convert a section title to a filename-friendly slug."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "_", text)


def extract_raw_layout(pdf_path: Path) -> str:
    """Extract raw layout text from each page for debugging or fallback comparison."""
    with pdfplumber.open(pdf_path) as pdf:
        pages = [page.extract_text(layout=True) or "" for page in pdf.pages]
    return "\n\n--- Page Break ---\n\n".join(pages)


def extract_structured_markdown(pdf_path: Path) -> tuple[str, list[dict[str, str]]]:
    """Extract and format structured Markdown from PDF with tables and headings."""
    with pdfplumber.open(pdf_path) as pdf:
        raw_elements = []

        # Page 1 is the cover; processed separately into metadata header
        for page_idx, page in enumerate(pdf.pages):
            if page_idx == 0:
                continue

            tables = page.find_tables()
            tables = sorted(tables, key=lambda t: t.bbox[1])
            y0 = 0.0

            for table in tables:
                top_crop = page.crop((0, y0, page.width, table.bbox[1]))
                text = top_crop.extract_text() or ""
                if text.strip():
                    raw_elements.append(("text", text))

                table_md = format_markdown_table(table.extract())
                if table_md:
                    raw_elements.append(("table", table_md))
                y0 = table.bbox[3]

            bottom_crop = page.crop((0, y0, page.width, page.height))
            text = bottom_crop.extract_text() or ""
            if text.strip():
                raw_elements.append(("text", text))

    out_blocks = []

    # Cover metadata header
    header = (
        "# Empório da Música — Manual de Políticas e Procedimentos\n\n"
        "> **Atendimento ao Cliente**  \n"
        "> Versão 2.1 — Junho de 2025 (Documento interno — Uso restrito da equipe de atendimento)  \n"
        "> Rua 14 de Maio, 3200 — Centro, Campo Grande – MS – CEP 79202-333  \n"
        "> Telefone / WhatsApp: (67) 3341-4444 | E-mail: contato@emporiodamusica.com.br\n\n"
        "---"
    )
    out_blocks.append(header)

    current_item: str | None = None
    current_item_type: str | None = None

    def flush_item() -> None:
        nonlocal current_item, current_item_type
        if current_item:
            out_blocks.append(current_item)
            current_item = None
            current_item_type = None

    for elem_type, content in raw_elements:
        if elem_type == "table":
            flush_item()
            out_blocks.append(content)
            continue

        for line in content.splitlines():
            s = line.strip()
            if not s:
                flush_item()
                continue

            # Skip running headers and footers
            if s == "Empório da Música Manual de Políticas e Procedimentos":
                continue
            if re.match(r"^Página\s+\d+$", s):
                continue
            if s.startswith("Empório da Música — Sua música começa aqui.") or s.startswith(
                "Última atualização:"
            ):
                continue

            # Subsections (e.g., '1.1 Missão' or '4.2 Trocas por Defeito')
            m_sub = re.match(r"^([1-9]|10)\.(\d+)\s+(.*)$", s)
            if m_sub:
                flush_item()
                out_blocks.append(f"### {m_sub.group(1)}.{m_sub.group(2)} {m_sub.group(3)}")
                continue

            # Numbered workflow list items (e.g. '1. Saudação: ...')
            m_num_item = re.match(r"^(\d+)\.\s+([A-ZÁÉÍÓÚ][a-zA-Zà-ú\s]+:)\s*(.*)$", s)
            if m_num_item:
                flush_item()
                current_item_type = "numbered"
                current_item = (
                    f"{m_num_item.group(1)}. **{m_num_item.group(2)}** {m_num_item.group(3)}".strip()
                )
                continue

            # Main section titles (e.g., '1. Sobre a Empório da Música')
            m_sec = re.match(r"^([1-9]|10)\.\s+(.*)$", s)
            if m_sec:
                flush_item()
                out_blocks.append(f"## {m_sec.group(1)}. {m_sec.group(2)}")
                continue

            # Bullet items
            if s.startswith("•") or s.startswith("-"):
                flush_item()
                current_item_type = "bullet"
                bullet_text = re.sub(r"^[•\-]\s*", "", s)
                current_item = f"- {bullet_text}"
                continue

            # Labeled rule items (e.g. 'Tom de voz:', 'Cumulatividade:', 'Produto fora de estoque:')
            m_label = re.match(r"^([A-ZÁÉÍÓÚ][a-zA-Zà-ú\s/–—]{2,30}:)\s*(.*)$", s)
            if m_label:
                flush_item()
                current_item_type = "p"
                label = m_label.group(1)
                rest = m_label.group(2)
                current_item = f"**{label}** {rest}".strip()
                continue

            # Flow continuation lines or join paragraphs
            if current_item_type in ("bullet", "numbered"):
                if current_item.rstrip().endswith((".", ";", "!", "?")):
                    flush_item()
                    current_item_type = "p"
                    current_item = s
                else:
                    current_item += " " + s
            elif current_item_type == "p":
                current_item += " " + s
            else:
                current_item_type = "p"
                current_item = s

    flush_item()
    full_markdown = "\n\n".join(out_blocks)

    # Parse individual sections for validation and optional export
    sections = []
    pattern = r"(##\s+(\d+)\.\s+([^\n]+))\n\n(.*?)(?=\n\n##\s+\d+\.|\Z)"
    for match in re.finditer(pattern, full_markdown, re.DOTALL):
        heading, sec_num, sec_title, sec_body = match.groups()
        sections.append({
            "number": sec_num,
            "title": sec_title.strip(),
            "content": f"{heading}\n\n{sec_body.strip()}",
        })

    return full_markdown, sections


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract and structure store policies from PDF")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF, help="Path to policies PDF")
    parser.add_argument(
        "--output", "-o", type=Path, default=DEFAULT_OUTPUT, help="Output markdown path"
    )
    parser.add_argument(
        "--split-sections",
        action="store_true",
        help="Also export individual section markdown files into data/policies/",
    )
    parser.add_argument(
        "--force", "-f", action="store_true", help="Force overwrite output file if it exists"
    )
    parser.add_argument(
        "--raw", action="store_true", help="Dump raw layout-extracted text instead of structured"
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        raise FileNotFoundError(f"PDF file not found: {args.pdf}")

    print(f"Reading PDF from: {args.pdf}")

    if args.raw:
        content = extract_raw_layout(args.pdf)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(f"Saved raw text extraction to: {args.output}")
        return

    if args.output.exists() and not args.force:
        print(f"Output file already exists at: {args.output}")
        print("Use --force (or -f) to overwrite with newly extracted structured Markdown.")
        return

    full_markdown, sections = extract_structured_markdown(args.pdf)

    # Save structured markdown
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(full_markdown, encoding="utf-8")
    print(f"Successfully generated structured policies at: {args.output}")
    print(f"Summary: {len(sections)} sections, {len(full_markdown.splitlines())} lines, {len(full_markdown)} characters.")

    # Validate section presence
    expected_sections = 10
    if len(sections) != expected_sections:
        print(f"Warning: expected {expected_sections} sections, but detected {len(sections)}.")
    else:
        print("Validation: all 10 policy sections verified successfully:")
        for sec in sections:
            print(f"  - Section {sec['number']}: {sec['title']}")

    # Export split sections if requested
    if args.split_sections:
        DEFAULT_SECTIONS_DIR.mkdir(parents=True, exist_ok=True)
        for sec in sections:
            sec_num_str = sec["number"].zfill(2)
            sec_filename = f"{sec_num_str}_{slugify(sec['title'])}.md"
            sec_path = DEFAULT_SECTIONS_DIR / sec_filename
            sec_path.write_text(sec["content"] + "\n", encoding="utf-8")
        print(f"Exported {len(sections)} individual section files to: {DEFAULT_SECTIONS_DIR}")


if __name__ == "__main__":
    main()
