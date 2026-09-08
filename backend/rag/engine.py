from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import chromadb


# --------------------------------------------------
# EMBEDDING MODEL
# --------------------------------------------------

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


# --------------------------------------------------
# CHROMADB
# --------------------------------------------------

chroma_client = chromadb.PersistentClient(
    path="chroma_db"
)

collection = chroma_client.get_or_create_collection(
    name="garuda_documents"
)


# --------------------------------------------------
# PDF TEXT EXTRACTION
# --------------------------------------------------

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


# --------------------------------------------------
# TEXT CHUNKING
# --------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> list[str]:
    """
    Split text into overlapping chunks.

    chunk_size:
        Maximum number of words in each chunk.

    overlap:
        Number of words shared between consecutive chunks.
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


# --------------------------------------------------
# CREATE EMBEDDINGS
# --------------------------------------------------

def create_embeddings(chunks: list[str]):
    """
    Convert text chunks into numerical vectors.
    """

    embeddings = embedding_model.encode(
        chunks,
        convert_to_numpy=True
    )

    return embeddings


# --------------------------------------------------
# STORE CHUNKS IN CHROMADB
# --------------------------------------------------

def store_chunks(chunks: list[str], embeddings):
    """
    Store document chunks and their embeddings
    inside ChromaDB.
    """

    ids = [
        f"chunk_{i}"
        for i in range(len(chunks))
    ]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings.tolist()
    )

    return len(chunks)