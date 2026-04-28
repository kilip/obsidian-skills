"""
Dispatcher: route extract_text() calls to the correct format-specific extractor.

Submodules:
  extractor.docx  — Word documents (.docx, .doc)
  extractor.pdf   — PDF documents (.pdf)
  extractor.xlsx  — Excel spreadsheets (.xlsx, .xls)
  extractor.slide — PowerPoint presentations (.pptx, .ppt)
"""

from gdrive.extractor import docx as _docx
from gdrive.extractor import pdf as _pdf
from gdrive.extractor import slide as _slide
from gdrive.extractor import xlsx as _xlsx


def extract_text(path: str, mime_type: str) -> str:
    """
    Dispatch text extraction to the correct submodule based on MIME type.

    Raises:
        NotImplementedError: if no extractor supports the given MIME type.
    """
    if "wordprocessingml" in mime_type or mime_type == "application/msword":
        return _docx.extract(path)
    if mime_type == "application/pdf":
        return _pdf.extract(path)
    if "spreadsheetml" in mime_type or mime_type == "application/vnd.ms-excel":
        return _xlsx.extract(path)
    if "presentationml" in mime_type or mime_type == "application/vnd.ms-powerpoint":
        return _slide.extract(path)
    raise NotImplementedError(f"No extractor for MIME type: {mime_type}")
