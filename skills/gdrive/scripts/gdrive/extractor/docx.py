"""Text extractor for Word documents (.docx, .doc)."""


def extract(path: str) -> str:
    """Extract plain text from a .docx file."""
    from docx import Document

    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
