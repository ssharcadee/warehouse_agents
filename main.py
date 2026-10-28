"""
Warehouse Multi-Agent Assistant: chat with a team of Gemini agents in the terminal.

Run:  python main.py
Needs a Gemini API key in the GEMINI_API_KEY environment variable
(free from https://aistudio.google.com/apikey).
"""

import os
import sys

from google import genai

from agents import MODEL, build_team

EXAMPLES = [
    "What items are running low?",
    "Where are the hard hats kept and how many do we have?",
    "What shipments are arriving this week?",
    "Restock anything low that isn't already covered by an incoming shipment.",
    "How much is our stock worth?",
]


def main():
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        sys.exit("Set your API key first, e.g.  export GEMINI_API_KEY=your_key_here\n"
                 "Get a free key at https://aistudio.google.com/apikey")

    client = genai.Client()  
    manager = build_team(client)

    print(f"\nWarehouse Multi-Agent Assistant  (model: {MODEL})")
    print("Try asking:")
    for e in EXAMPLES:
        print(f"  - {e}")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"quit", "exit", "q"}:
            break
        if not question:
            continue
        try:
            print(f"\nManager: {manager.ask(question)}\n")
        except Exception as err:  
            print(f"\n[Error] {err}\n")


if __name__ == "__main__":
    main()