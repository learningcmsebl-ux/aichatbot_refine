"""
Phonebook integration status helper.
"""

def show_status() -> None:
    print("=" * 70)
    print("Chatbot Phonebook Integration")
    print("=" * 70)
    print()
    print("Legacy chatbot_convert has been removed.")
    print("The current system (bank_chatbot) already uses PostgreSQL phonebook.")
    print()
    print("Check current integration in:")
    print("  - bank_chatbot/app/services/chat_orchestrator.py")
    print()


if __name__ == "__main__":
    show_status()
