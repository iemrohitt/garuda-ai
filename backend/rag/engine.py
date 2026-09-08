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