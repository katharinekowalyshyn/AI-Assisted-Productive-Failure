from llmproxy import LLMProxy
from time import sleep
from pathlib import Path
import csv
import os

client = LLMProxy()

# Unique session ID for this homework
SESSION_ID = "HW4_Session"
MODEL = "4o-mini"

LASTK = 2                            # <-- Change to 0, 1, 5, etc.
MEMORY_SESSION = "HW4_Memory_lastk2"   # <-- Change to match lastk value

print("=" * 70)
print(f"PART 1: Exploring Memory (lastk = {LASTK})")
print("=" * 70)
print(f"Session: {MEMORY_SESSION}")
print("Type your questions one at a time. Type 'exit' to move on.\n")

while True:
    query_prompt = input("Enter your query or type EXIT to stop: ")
    if query_prompt.strip().lower() == "exit":
        break

    response = client.generate(
        model=MODEL,
        system="You are a helpful, concise assistant.",
        query=query_prompt,
        temperature=0.5,
        lastk=LASTK,
        session_id=MEMORY_SESSION,
        rag_usage=False,
    )

    if 'result' in response:
        print(f"\nResponse: {response.get('result')}\n")
    else:
        print(f"\nERROR: No result in response")
        print(f"Full response: {response}\n")