from rag.engine import search_documents


query = "What are the key characteristics of cloud computing?"


results = search_documents(
    query,
    top_k=3
)


print("\n--- QUESTION ---")
print(query)


print("\n--- RETRIEVED CHUNKS ---")

for i, result in enumerate(results, start=1):

    print(f"\n### CHUNK {i}")
    print(result)