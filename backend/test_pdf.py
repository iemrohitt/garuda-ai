from rag.engine import extract_text_from_pdf


pdf_path = "documents/Cloud Computing.pdf"
text = extract_text_from_pdf(pdf_path)

print("\n--- EXTRACTED TEXT ---\n")
print(text[:3000])