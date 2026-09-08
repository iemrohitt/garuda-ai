from pypdf import PdfReader


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from all pages of a PDF.
    """

    reader = PdfReader(file_path)

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text.strip()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping chunks.

    chunk_size: Maximum number of words in each chunk.
    overlap: Number of words repeated between consecutive chunks.
    """

    words = text.split()

    chunks = []

    start = 0

    while start < len(words):
        end = start + chunk_size

        chunk = " ".join(words[start:end])

        chunks.append(chunk)

        start += chunk_size - overlap

    return chunks