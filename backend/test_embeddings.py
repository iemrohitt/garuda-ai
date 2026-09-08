from rag.engine import (
    extract_text_from_pdf,
    chunk_text,
    create_embeddings,
    store_chunks
)


# PDF location
pdf_path = "documents/Cloud Computing.pdf"


# 1. Extract text
text = extract_text_from_pdf(pdf_path)

print("Text extracted successfully.")
print("Total characters:", len(text))


# 2. Create chunks
chunks = chunk_text(text)

print("Total chunks:", len(chunks))


# 3. Create embeddings
embeddings = create_embeddings(chunks)

print("Embedding shape:", embeddings.shape)


# 4. Store chunks in ChromaDB
stored = store_chunks(
    chunks,
    embeddings
)

print("Chunks stored in ChromaDB:", stored)