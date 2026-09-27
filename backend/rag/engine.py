from sentence_transformers import SentenceTransformer
import chromadb
import re


# =========================================================
# EMBEDDING MODEL
# =========================================================

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


# =========================================================
# CHROMADB
# =========================================================

chroma_client = chromadb.PersistentClient(path="chroma_db")

collection = chroma_client.get_or_create_collection(
    name="garuda_documents"
)


# =========================================================
# TEXT CLEANING
# =========================================================

def clean_text(text: str) -> str:
    """
    Clean extracted PDF text while preserving paragraph structure.
    """

    if not text:
        return ""

    # Normalize different line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove excessive spaces/tabs
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# =========================================================
# PARAGRAPH-AWARE CHUNKING
# =========================================================

def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> list[str]:
    """
    Split text into paragraph-aware chunks.

    Instead of blindly splitting every 500 words, this function
    tries to keep paragraphs together while still maintaining
    a maximum chunk size.

    chunk_size:
        Maximum approximate number of words per chunk.

    overlap:
        Approximate number of words carried from the previous
        chunk into the next chunk.
    """

    text = clean_text(text)

    if not text:
        return []

    # Split using blank lines as paragraph boundaries
    paragraphs = re.split(r"\n\s*\n", text)

    paragraphs = [
        paragraph.strip()
        for paragraph in paragraphs
        if paragraph.strip()
    ]

    chunks = []
    current_words = []

    for paragraph in paragraphs:

        paragraph_words = paragraph.split()

        # -----------------------------------------------------
        # If the paragraph itself is larger than chunk_size,
        # split that paragraph into smaller pieces.
        # -----------------------------------------------------

        if len(paragraph_words) > chunk_size:

            # First store whatever we already accumulated
            if current_words:
                chunks.append(" ".join(current_words))
                current_words = []

            start = 0

            while start < len(paragraph_words):

                end = start + chunk_size

                piece = paragraph_words[start:end]

                if piece:
                    chunks.append(" ".join(piece))

                # Maintain overlap for very large paragraphs
                start += max(1, chunk_size - overlap)

            continue

        # -----------------------------------------------------
        # Add paragraph to current chunk if it fits
        # -----------------------------------------------------

        if len(current_words) + len(paragraph_words) <= chunk_size:

            current_words.extend(paragraph_words)

        else:

            # Save current chunk
            if current_words:
                chunks.append(" ".join(current_words))

            # Start new chunk with current paragraph
            current_words = paragraph_words.copy()

    # ---------------------------------------------------------
    # Save final chunk
    # ---------------------------------------------------------

    if current_words:
        chunks.append(" ".join(current_words))

    # ---------------------------------------------------------
    # Add controlled overlap between normal chunks
    # ---------------------------------------------------------

    final_chunks = []

    for i, chunk in enumerate(chunks):

        if i == 0:
            final_chunks.append(chunk)
            continue

        previous_words = final_chunks[-1].split()

        overlap_words = previous_words[-overlap:] if overlap > 0 else []

        current_words = chunk.split()

        combined = overlap_words + current_words

        # Avoid creating an unnecessarily large chunk
        if len(combined) <= chunk_size + overlap:
            final_chunks.append(" ".join(combined))
        else:
            final_chunks.append(chunk)

    return final_chunks


# =========================================================
# CREATE EMBEDDINGS
# =========================================================

def create_embeddings(chunks: list[str]):
    """
    Create embeddings for a list of text chunks.
    """

    if not chunks:
        return []

    embeddings = embedding_model.encode(
        chunks,
        convert_to_numpy=True
    )

    return embeddings


# =========================================================
# STORE CHUNKS
# =========================================================

def store_chunks(
    chunks,
    embeddings,
    document_name: str = "document",
    page_numbers=None
):
    """
    Store chunks and metadata inside ChromaDB.
    """

    if not chunks:
        return 0

    if page_numbers is None:
        page_numbers = [None] * len(chunks)

    ids = []
    metadatas = []

    for i, page_number in enumerate(page_numbers):

        ids.append(
            f"{document_name}_chunk_{i}"
        )

        metadata = {
            "document": document_name,
            "chunk": i
        }

        if page_number is not None:
            metadata["page"] = page_number

        metadatas.append(metadata)

    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings.tolist(),
        metadatas=metadatas
    )

    return len(chunks)


# =========================================================
# ADD SINGLE DOCUMENT
# =========================================================

def add_document(
    text: str,
    document_name: str,
    page_number=None
):
    """
    Add a single document to ChromaDB.
    """

    chunks = chunk_text(text)

    if not chunks:
        return {
            "document": document_name,
            "chunks": 0
        }

    embeddings = create_embeddings(chunks)

    page_numbers = [
        page_number for _ in chunks
    ]

    stored_chunks = store_chunks(
        chunks,
        embeddings,
        document_name,
        page_numbers
    )

    return {
        "document": document_name,
        "chunks": stored_chunks
    }


# =========================================================
# ADD PDF PAGES
# =========================================================

def add_pages(
    pages: list[dict],
    document_name: str
):
    """
    Add page-by-page PDF content.

    Existing chunks for the same document are deleted first
    so that re-uploading a PDF does not leave stale chunks.
    """

    # ---------------------------------------------------------
    # Delete old chunks for this document
    # ---------------------------------------------------------

    collection.delete(
        where={
            "document": document_name
        }
    )

    all_chunks = []
    all_page_numbers = []

    # ---------------------------------------------------------
    # Process each page separately
    # ---------------------------------------------------------

    for page in pages:

        page_number = page["page"]
        page_text = page["text"]

        chunks = chunk_text(page_text)

        for chunk in chunks:

            all_chunks.append(chunk)

            all_page_numbers.append(
                page_number
            )

    # ---------------------------------------------------------
    # No usable content
    # ---------------------------------------------------------

    if not all_chunks:

        return {
            "document": document_name,
            "chunks": 0
        }

    # ---------------------------------------------------------
    # Create embeddings
    # ---------------------------------------------------------

    embeddings = create_embeddings(
        all_chunks
    )

    # ---------------------------------------------------------
    # Store everything
    # ---------------------------------------------------------

    stored_chunks = store_chunks(
        all_chunks,
        embeddings,
        document_name,
        all_page_numbers
    )

    return {
        "document": document_name,
        "chunks": stored_chunks
    }


# =========================================================
# SEARCH DOCUMENTS
# =========================================================

def search_documents(
    query: str,
    top_k: int = 3,
    document_name: str | None = None,
    distance_threshold: float = 0.90
):
    """
    Search ChromaDB for relevant document chunks.

    Lower ChromaDB distance means greater similarity.
    """

    if not query or not query.strip():
        return []

    # ---------------------------------------------------------
    # Create query embedding
    # ---------------------------------------------------------

    query_embedding = embedding_model.encode(
        query,
        convert_to_numpy=True
    )

    # ---------------------------------------------------------
    # Optional document filter
    # ---------------------------------------------------------

    where_filter = None

    if document_name:
        where_filter = {
            "document": document_name
        }

    # ---------------------------------------------------------
    # Query ChromaDB
    # ---------------------------------------------------------

    if where_filter:

        results = collection.query(
            query_embeddings=[
                query_embedding.tolist()
            ],
            n_results=top_k,
            where=where_filter
        )

    else:

        results = collection.query(
            query_embeddings=[
                query_embedding.tolist()
            ],
            n_results=top_k
        )

    # ---------------------------------------------------------
    # Extract results
    # ---------------------------------------------------------

    documents = results.get(
        "documents",
        [[]]
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]]
    )[0]

    distances = results.get(
        "distances",
        [[]]
    )[0]

    retrieved_results = []

    # ---------------------------------------------------------
    # Apply relevance threshold
    # ---------------------------------------------------------

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):

        if distance <= distance_threshold:

            retrieved_results.append(
                {
                    "text": document,
                    "metadata": metadata or {},
                    "distance": distance
                }
            )

    return retrieved_results