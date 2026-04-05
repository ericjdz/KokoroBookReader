"""Multi-format document extraction (EPUB, DOCX, TXT)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DocumentExtractionResult:
    text: str
    page_count: int
    format: str  # "pdf", "epub", "docx", "txt"


@dataclass
class PdfSentenceExtractionResult:
    sentences: list[str]
    chunk_to_page: dict[int, int]
    page_count: int


def extract_txt(path: str) -> DocumentExtractionResult:
    """Extract text from a plain text file."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return DocumentExtractionResult(text=text, page_count=1, format="txt")


def extract_epub(path: str) -> DocumentExtractionResult:
    """Extract text from an EPUB file."""
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError(
            "EPUB support requires ebooklib and beautifulsoup4. "
            "Install with: pip install ebooklib beautifulsoup4"
        )

    book = epub.read_epub(path)
    chapters = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        html_content = item.get_content().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator="\n")
        if text.strip():
            chapters.append(text)

    full_text = "\n\n".join(chapters)
    return DocumentExtractionResult(
        text=full_text, page_count=len(chapters), format="epub"
    )


def extract_docx(path: str) -> DocumentExtractionResult:
    """Extract text from a DOCX file."""
    try:
        import docx
    except ImportError:
        raise ImportError(
            "DOCX support requires python-docx. "
            "Install with: pip install python-docx"
        )

    doc = docx.Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    full_text = "\n\n".join(paragraphs)
    return DocumentExtractionResult(
        text=full_text, page_count=max(1, len(paragraphs) // 30), format="docx"
    )


def extract_document(path: str) -> DocumentExtractionResult:
    """Extract text from any supported document format.

    Auto-detects format from file extension.
    """
    ext = Path(path).suffix.lower()

    if ext == ".pdf":
        import fitz

        document = fitz.open(str(path))
        pages = [page.get_text("text") for page in document]
        result = DocumentExtractionResult(
            text="\n".join(pages), page_count=document.page_count, format="pdf"
        )
        document.close()
        return result
    elif ext == ".epub":
        return extract_epub(path)
    elif ext == ".docx":
        return extract_docx(path)
    elif ext == ".txt":
        return extract_txt(path)
    else:
        raise ValueError(
            f"Unsupported file format: {ext}. "
            "Supported formats: .pdf, .epub, .docx, .txt"
        )


def extract_pdf_sentences_with_page_map(path: str) -> PdfSentenceExtractionResult:
    """Extract PDF into sentence chunks with deterministic chunk-to-page mapping."""
    import fitz
    from audiobook import clean_and_chunk

    document = fitz.open(str(path))
    try:
        sentences: list[str] = []
        chunk_to_page: dict[int, int] = {}

        for page_index, page in enumerate(document):
            page_text = page.get_text("text")
            page_sentences = clean_and_chunk(page_text)
            for sentence in page_sentences:
                chunk_index = len(sentences)
                sentences.append(sentence)
                chunk_to_page[chunk_index] = page_index

        return PdfSentenceExtractionResult(
            sentences=sentences,
            chunk_to_page=chunk_to_page,
            page_count=document.page_count,
        )
    finally:
        document.close()
