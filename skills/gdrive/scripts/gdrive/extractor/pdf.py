"""Text extractor for PDF documents (.pdf)."""


def extract(path: str) -> str:
    """Extract plain text from a .pdf file, page by page."""
    import pdfplumber

    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n".join(pages)
