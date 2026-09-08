import chromadb
from sentence_transformers import SentenceTransformer


# --------------------------------------------------
# 1. Load embedding model
# --------------------------------------------------

embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


# --------------------------------------------------
# 2. Create local ChromaDB
# --------------------------------------------------

chroma_client = chromadb.PersistentClient(
    path="./chroma_db"
)


# --------------------------------------------------
# 3. Create collection
# --------------------------------------------------

collection = chroma_client.get_or_create_collection(
    name="garuda_documents"
)


# --------------------------------------------------
# 4. Create embedding
# --------------------------------------------------

def create_embedding(text):

    return embedding_model.encode(
        text
    ).tolist()


# --------------------------------------------------
# 5. Split text into chunks
# --------------------------------------------------

def chunk_text(
    text,
    chunk_size=500,
    overlap=50
):

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end]

        if chunk.strip():
            chunks.append(
                chunk.strip()
            )

        start += chunk_size - overlap

    return chunks


# --------------------------------------------------
# 6. Store document chunks
# --------------------------------------------------

def add_document(
    text,
    document_name
):

    chunks = chunk_text(text)

    embeddings = []

    for chunk in chunks:

        embedding = create_embedding(
            chunk
        )

        embeddings.append(
            embedding
        )

    ids = [
        f"{document_name}_{i}"
        for i in range(len(chunks))
    ]

    metadatas = [
        {
            "source": document_name
        }
        for _ in chunks
    ]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas
    )

    return {
        "document": document_name,
        "chunks": len(chunks)
    }


# --------------------------------------------------
# 7. Search documents
# --------------------------------------------------

def search_documents(
    query,
    top_k=3
):

    query_embedding = create_embedding(
        query
    )

    results = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=top_k
    )

    return results

