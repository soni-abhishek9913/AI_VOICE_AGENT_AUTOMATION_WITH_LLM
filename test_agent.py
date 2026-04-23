#TEST_AGENT.PY  — LLM-DRIVEN TEST HARNESS FOR HOSPITAL AGENT
import sys
from hospital_agent import HospitalAgent
import llm_interface as llm

AUTO_LANG = None
for i, arg in enumerate(sys.argv[1:], 1):
    if arg == "--lang" and i < len(sys.argv):
        AUTO_LANG = sys.argv[i + 1] if i + 1 < len(sys.argv) else None

print("=" * 60)
print("  ADAM Hospital Agent — LLM-Driven Test Mode")
print("=" * 60)
print("Commands: quit | reset | state | hist | ctx")
print("-" * 60)

agent = HospitalAgent()

if AUTO_LANG in ("en", "hi"):
    agent.set_language(AUTO_LANG)
    agent.state = "START"
    print(f"\n[Auto language: {'English' if AUTO_LANG == 'en' else 'Hindi'}]")
    first_reply = agent.handle("I want to book an appointment")
    print(f"\nADAM: {first_reply}\n")
else:
    opening = (
        "Hello, welcome to Anand Hospital. This is ADAM. "
        "Would you prefer to speak in English or Hindi? "
        "Kripya English ya Hindi chunein."
    )
    print(f"\nADAM: {opening}\n")

while True:
    try:
        user = input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nExiting.")
        break

    if not user:
        continue

    if user.lower() in ["quit", "exit", "q"]:
        print("Goodbye.")
        break

    if user.lower() == "reset":
        agent.reset()
        print("--- Conversation reset ---\n")
        continue

    if user.lower() == "state":
        print(f"  State : {agent.state}")
        print(f"  Lang  : {agent.lang}")
        print(f"  Data  : {agent.data}")
        print(f"  Docs  : {agent.temp_doctors}")
        continue

    if user.lower() == "hist":
        print("  Conversation history:")
        for i, turn in enumerate(llm._conversation):
            print(f"    [{i}] {turn['role'].upper()}: {turn['content'][:80]}")
        continue

    if user.lower() == "ctx":
        print(f"  LLM context : {llm._context}")
        print(f"  LLM lang    : {llm._lang}")
        continue

    try:
        response = agent.handle(user)
    except Exception as e:
        print(f"  [ERROR]: {e}")
        import traceback
        traceback.print_exc()
        continue

    print(f"\nADAM: {response}")
    print(f"      [state={agent.state}  data={agent.data}]\n")