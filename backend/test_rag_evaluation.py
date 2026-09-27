from rag.engine import search_documents


# =========================================================
# RAG EVALUATION QUESTIONS
# =========================================================

TEST_CASES = [
    {
        "category": "Relevant",
        "question": "What is cloud computing?",
        "expected_relevant": True,
    },
    {
        "category": "Relevant",
        "question": "What are the advantages of using cloud computing?",
        "expected_relevant": True,
    },
    {
        "category": "Relevant",
        "question": "What are the characteristics of cloud computing?",
        "expected_relevant": True,
    },
    {
        "category": "Irrelevant",
        "question": "Who won the FIFA World Cup in 2018?",
        "expected_relevant": False,
    },
    {
        "category": "Irrelevant",
        "question": "What is the capital of France?",
        "expected_relevant": False,
    },
]


# =========================================================
# CONFIGURATION
# =========================================================

DOCUMENT_NAME = "Cloud Computing.pdf"
TOP_K = 3
DISTANCE_THRESHOLD = 0.90


# =========================================================
# RUN EVALUATION
# =========================================================

def run_evaluation():

    print()
    print("=" * 70)
    print("GARUDA AI - RAG EVALUATION")
    print("=" * 70)

    print(f"Document: {DOCUMENT_NAME}")
    print(f"Top K: {TOP_K}")
    print(f"Distance threshold: {DISTANCE_THRESHOLD}")

    total_tests = len(TEST_CASES)
    passed_tests = 0

    print()

    for index, test_case in enumerate(TEST_CASES, start=1):

        question = test_case["question"]
        expected_relevant = test_case["expected_relevant"]

        results = search_documents(
            query=question,
            top_k=TOP_K,
            document_name=DOCUMENT_NAME,
            distance_threshold=DISTANCE_THRESHOLD,
        )

        retrieved_count = len(results)

        # -------------------------------------------------
        # Determine whether retrieval matched expectation
        # -------------------------------------------------

        actual_relevant = retrieved_count > 0

        passed = actual_relevant == expected_relevant

        if passed:
            passed_tests += 1

        # -------------------------------------------------
        # Print result
        # -------------------------------------------------

        print("-" * 70)

        print(f"Test {index}: {test_case['category']}")

        print(f"Question: {question}")

        print(
            f"Expected relevant: {expected_relevant}"
        )

        print(
            f"Retrieved chunks: {retrieved_count}"
        )

        print(
            f"Result: {'PASS' if passed else 'FAIL'}"
        )

        # -------------------------------------------------
        # Print retrieved chunks
        # -------------------------------------------------

        if results:

            print("Retrieved sources:")

            for result_number, result in enumerate(
                results,
                start=1
            ):

                metadata = result["metadata"]
                distance = result["distance"]

                print(
                    f"  {result_number}. "
                    f"Page={metadata.get('page')} | "
                    f"Chunk={metadata.get('chunk')} | "
                    f"Distance={distance:.4f}"
                )

        else:

            print("Retrieved sources: None")

    # =====================================================
    # FINAL SUMMARY
    # =====================================================

    accuracy = (
        passed_tests / total_tests
    ) * 100

    print()
    print("=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    print(
        f"Tests passed: {passed_tests}/{total_tests}"
    )

    print(
        f"Evaluation accuracy: {accuracy:.2f}%"
    )

    print("=" * 70)
    print()


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    run_evaluation()