from rag.engine import (
    extract_text_from_pdf,
    chunk_text,
    create_embeddings
)


pdf_path = "documents/Cloud Computing.pdf"

text = extract_text_from_pdf(pdf_path)

chunks = chunk_text(text)

embeddings = create_embeddings(chunks)

print("Total chunks:", len(chunks))
print("Embedding shape:", embeddings.shape)
print("First chunk:", chunks[0][:200])
print("First 10 embedding values:", embeddings[0][:10])