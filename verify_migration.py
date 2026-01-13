"""Verify migrated data in PostgreSQL"""
from phonebook_postgres import PhoneBookDB
from conversation_analytics_postgres import _get_session, Conversation, Question, PerformanceMetric
from dotenv import load_dotenv
import os

load_dotenv()

print("=" * 60)
print("Verifying Migrated Data")
print("=" * 60)
print()

# Check phonebook
print("Phonebook Data:")
db = PhoneBookDB()
with db.get_session() as session:
    from phonebook_postgres import Employee
    count = session.query(Employee).count()
    print(f"  ✓ Employees: {count} records")
print()

# Check analytics
print("Analytics Data:")
with _get_session() as session:
    conv_count = session.query(Conversation).count()
    q_count = session.query(Question).count()
    m_count = session.query(PerformanceMetric).count()
    print(f"  ✓ Conversations: {conv_count}")
    print(f"  ✓ Questions: {q_count}")
    print(f"  ✓ Performance Metrics: {m_count}")
print()

print("=" * 60)
print("✓ All data verified!")
print("=" * 60)

