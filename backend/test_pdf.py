from rag.engine import extract_text_from_pdf, chunk_text


pdf_path = "documents/Cloud Computing.pdf"

text = extract_text_from_pdf(pdf_path)

chunks = chunk_text(text)

print("\n--- PDF INFORMATION ---")
print(f"Total characters: {len(text)}")
print(f"Total chunks: {len(chunks)}")

print("\n--- FIRST CHUNK ---")
print(chunks[0])

print("\n--- SECOND CHUNK ---")
print(chunks[1])