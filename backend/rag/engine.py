from sentence_transformers import SentenceTransformer
import chromadb


# =========================================================
# EMBEDDING MODEL
# =========================================================

embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


# =========================================================
# CHROMADB
# =========================================================

chroma_client = chromadb.PersistentClient(
    path="chroma_db"
)

collection = chroma_client.get_or_create_collection(
    name="garuda_documents"
)


# =========================================================
# CHUNK TEXT
# =========================================================

def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> list[str]:

    if not text or not text.strip():
        return []

    words = text.split()

    chunks = []

    start = 0

    step = chunk_size - overlap

    while start < len(words):

        end = start + chunk_size

        chunk = " ".join(
            words[start:end]
        ).strip()

        if chunk:
            chunks.append(chunk)

        start += step

    return chunks


# =========================================================
# CREATE EMBEDDINGS
# =========================================================

def create_embeddings(chunks: list[str]):

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
# ADD DOCUMENT
# =========================================================

def add_document(
    text: str,
    document_name: str,
    page_number=None
):

    chunks = chunk_text(text)

    if not chunks:

        return {
            "document": document_name,
            "chunks": 0
        }

    embeddings = create_embeddings(
        chunks
    )

    page_numbers = [
        page_number
        for _ in chunks
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
# ADD MULTIPLE PAGES
# =========================================================

def add_pages(
    pages: list[dict],
    document_name: str
):
    """
    Add page-aware chunks for a PDF.

    If the same PDF is uploaded again, remove all
    previous chunks belonging to that document first.
    This prevents stale chunks from an older version
    of the PDF from remaining in ChromaDB.
    """

    # -----------------------------------------------------
    # Remove existing chunks for this document
    # -----------------------------------------------------

    collection.delete(
        where={
            "document": document_name
        }
    )


    # -----------------------------------------------------
    # Prepare chunks
    # -----------------------------------------------------

    all_chunks = []

    all_page_numbers = []

    for page in pages:

        page_number = page["page"]

        page_text = page["text"]

        chunks = chunk_text(
            page_text
        )

        for chunk in chunks:

            all_chunks.append(
                chunk
            )

            all_page_numbers.append(
                page_number
            )


    # -----------------------------------------------------
    # Check whether chunks were created
    # -----------------------------------------------------

    if not all_chunks:

        return {
            "document": document_name,
            "chunks": 0
        }


    # -----------------------------------------------------
    # Create embeddings
    # -----------------------------------------------------

    embeddings = create_embeddings(
        all_chunks
    )


    # -----------------------------------------------------
    # Store new chunks
    # -----------------------------------------------------

    stored_chunks = store_chunks(
        all_chunks,
        embeddings,
        document_name,
        all_page_numbers
    )


    # -----------------------------------------------------
    # Return result
    # -----------------------------------------------------

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
    if not query or not query.strip():
        return []

    query_embedding = embedding_model.encode(
        query,
        convert_to_numpy=True
    )

    where_filter = None

    if document_name:
        where_filter = {"document": document_name}

    if where_filter:
        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=where_filter
        )
    else:
        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k
        )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    retrieved_results = []

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