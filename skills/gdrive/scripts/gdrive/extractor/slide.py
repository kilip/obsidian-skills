"""Text extractor for PowerPoint presentations (.pptx, .ppt)."""


def extract(path: str) -> str:
    """Extract text from all slides of a .pptx file."""
    from pptx import Presentation

    prs = Presentation(path)
    slides = []
    for i, slide in enumerate(prs.slides, 1):
        title = None
        bullets = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if not text:
                    continue
                
                if title is None:
                    title = text
                else:
                    bullets.append(text)
        
        if title or bullets:
            header = f"## Slide {i}"
            if title:
                header += f": {title}"
            
            content = [header]
            for b in bullets:
                content.append(f"- {b}")
            
            slides.append("\n".join(content))
            
    return "\n\n".join(slides)
