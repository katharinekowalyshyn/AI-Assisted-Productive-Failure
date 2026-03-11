from llmproxy import LLMProxy
from time import sleep
from pathlib import Path
import csv

client = LLMProxy()

SESSION_ID = "HW4_Session"
MODEL = "4o-mini"

print("\n" + "=" * 70)
print("PART 2: Exploring RAG")
print("=" * 70)

RAG_SESSION = "HW4_RAG"

handbook_path = Path(__file__).parent.parent.parent / "cs_handbook.pdf"
print("\nUploading handbook PDF to RAG session...")
print(f"Looking for file at: {handbook_path}")
if not handbook_path.exists():
    print(f"ERROR: File not found at {handbook_path}")
    print("Please make sure cs_handbook.pdf is in the root directory of the project.")
    exit(1)

upload_response = client.upload_file(
    file_path=str(handbook_path),
    session_id=RAG_SESSION,
    description="CS Supplemental Graduate Student Handbook",
    strategy="smart",
)
print(f"Upload response: {upload_response}")

print("Waiting for document indexing...")
sleep(20)

# --- Experiment 1: RAG on vs off ---
print("\n--- Experiment 1: RAG On vs Off ---")
rag_question = "How many courses do master's students need to complete?"

for rag_on in [False, True]:
    label = "RAG ON" if rag_on else "RAG OFF"
    response = client.generate(
        model=MODEL,
        system="You are a helpful assistant. Answer based on the provided context if available.",
        query=rag_question,
        temperature=0.0,
        lastk=0,
        session_id=RAG_SESSION,
        rag_usage=rag_on,
        rag_threshold=0.5,
        rag_k=5,
    )
    result = response.get("result", "ERROR")
    print(f"\n  [{label}] Q: {rag_question}")
    print(f"  [{label}] A: {result}")

# --- Experiment 2: Threshold tuning ---
print("\n\n--- Experiment 2: Threshold Tuning ---")
threshold_question = "What do you need to do to graduate with a PhD in computer science?"
thresholds = [0.3, 0.5, 0.7, 0.9]

for threshold in thresholds:
    response = client.generate(
        model=MODEL,
        system="You are a helpful assistant. Answer based on the provided context if available.",
        query=threshold_question,
        temperature=0.0,
        lastk=0,
        session_id=RAG_SESSION,
        rag_usage=True,
        rag_threshold=threshold,
        rag_k=5,
    )
    result = response.get("result", "ERROR")
    print(f"\n  [threshold={threshold}] Q: {threshold_question}")
    print(f"  [threshold={threshold}] A: {result}")

# --- Experiment 3: Unanswerable question ---
print("\n\n--- Experiment 3: Unanswerable Question ---")
unanswerable = "What is the dress code policy for the CS department?"

response = client.generate(
    model=MODEL,
    system="You are a helpful assistant. Answer based on the provided context if available. If the information is not in the context, say so.",
    query=unanswerable,
    temperature=0.0,
    lastk=0,
    session_id=RAG_SESSION,
    rag_usage=True,
    rag_threshold=0.5,
    rag_k=5,
)
result = response.get("result", "ERROR")
print(f"\n  Q: {unanswerable}")
print(f"  A: {result}")

# --- Optional: Inspect rag_context ---
print("\n\n--- Optional: Inspecting RAG Context ---")
rag_context = client.retrieve(
    query=rag_question,
    session_id=RAG_SESSION,
    rag_threshold=0.5,
    rag_k=5,
)
print(f"  Retrieved context for '{rag_question}':")
print(f"  {rag_context}")


# =============================================================================
# PART 3: Mini-Benchmark
# =============================================================================
# 5 test questions based on the handbook:
#   - 2+ factual (have a correct answer)
#   - 2+ non-factual (advice, explanation, summary)
#   - 1+ the handbook probably can't answer
# =============================================================================

print("\n" + "=" * 70)
print("PART 3: Mini-Benchmark")
print("=" * 70)

benchmark_questions = [
    {
        "question": "How many courses do master's students need to complete?",
        "type": "Factual",
        "expected": "10 courses",
        "criteria": "Must state 10 courses",
    },
    {
        "question": "What are the core competency requirements for the PhD degree?",
        "type": "Factual",
        "expected": "4 core courses: Algorithms, Operating Systems, Theory of Computation, and Programming Languages",
        "criteria": "Must list all 4 courses correctly",
    },
    {
        "question": "What advice would you give a new master's student about choosing between the thesis and non-thesis track?",
        "type": "Non-factual",
        "expected": "N/A - should provide balanced advice mentioning both options",
        "criteria": "Relevance to handbook content, mentions both tracks, provides useful guidance",
    },
    {
        "question": "Summarize the academic probation policy.",
        "type": "Non-factual",
        "expected": "N/A - should summarize the key points about grades below B- and GPA requirements",
        "criteria": "Completeness (covers triggers, consequences, timeline), accuracy to handbook",
    },
    {
        "question": "What programming languages are used in the required coursework?",
        "type": "Factual (Unanswerable)",
        "expected": "The handbook does not specify programming languages for coursework",
        "criteria": "Should acknowledge the info is not in the document, not hallucinate",
    },
]

benchmark_results = []

for bq in benchmark_questions:
    print(f"\n  Running: {bq['question']}")
    response = client.generate(
        model=MODEL,
        system="You are a helpful academic advisor in the Tufts University Computer Science Department. Answer based on the provided context. If the information is not available in the context, clearly state that.",
        query=bq["question"],
        temperature=0.0,
        lastk=0,
        session_id=RAG_SESSION,
        rag_usage=True,
        rag_threshold=0.5,
        rag_k=5,
    )
    result = response.get("result", "ERROR")
    print(f"  Answer: {result}")

    benchmark_results.append({
        "Question": bq["question"],
        "Type": bq["type"],
        "Expected Answer / Criteria": bq["expected"] if bq["type"] == "Factual" or "Unanswerable" in bq["type"] else bq["criteria"],
        "Actual Answer": result,
        "Score": "[FILL IN AFTER REVIEW]",
        "Why It Failed (if applicable)": "[FILL IN AFTER REVIEW]",
    })

# Save benchmark results to CSV for easy review
benchmark_csv = Path(__file__).parent / "hw4_benchmark.csv"
with open(benchmark_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=benchmark_results[0].keys())
    writer.writeheader()
    writer.writerows(benchmark_results)

print(f"\n  Benchmark results saved to: {benchmark_csv}")

# Print benchmark table
print("\n--- Benchmark Table ---")
print(f"{'Question':<60} | {'Type':<25} | {'Score':<15}")
print("-" * 105)
for row in benchmark_results:
    print(f"{row['Question']:<60} | {row['Type']:<25} | {row['Score']:<15}")

print("\n--- Part 3 Analysis ---")
print("\n" + "=" * 70)
print("HW4 Complete — Review outputs above for your PDF report.")
print("Benchmark CSV saved for table formatting.")
print("=" * 70)
