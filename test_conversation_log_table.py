"""Test script to check ConversationLog table and create a test record"""
import sys
sys.path.insert(0, 'bank_chatbot')

from app.database.postgres import get_db, init_db
from app.services.analytics import ConversationLog, log_conversation
from sqlalchemy import inspect

print("=" * 60)
print("Testing ConversationLog Table")
print("=" * 60)

# Initialize database (creates tables if they don't exist)
print("\n1. Initializing database...")
init_db()
print("   ✓ Database initialized")

# Check if table exists
print("\n2. Checking if ConversationLog table exists...")
db = get_db()
if db:
    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    if 'analytics_conversations' in tables:
        print("   ✓ Table 'analytics_conversations' exists")
        
        # Check current record count
        count = db.query(ConversationLog).count()
        print(f"   ✓ Current records in table: {count}")
        
        # Check table structure
        columns = [col['name'] for col in inspector.get_columns('analytics_conversations')]
        print(f"   ✓ Table columns: {', '.join(columns)}")
        
        if 'client_ip' in columns:
            print("   ✓ 'client_ip' column exists")
        else:
            print("   ✗ 'client_ip' column MISSING!")
    else:
        print("   ✗ Table 'analytics_conversations' DOES NOT EXIST!")
        print(f"   Available tables: {', '.join(tables)}")
    
    db.close()
else:
    print("   ✗ Could not get database connection")

# Test creating a record
print("\n3. Testing log_conversation function...")
try:
    log_conversation(
        session_id="test_session_123",
        user_message="Test message for dashboard",
        assistant_response="This is a test response to verify ConversationLog is working.",
        knowledge_base="test",
        response_time_ms=500,
        client_ip="127.0.0.1"
    )
    print("   ✓ log_conversation() executed successfully")
    
    # Verify the record was created
    db = get_db()
    if db:
        test_record = db.query(ConversationLog).filter(
            ConversationLog.session_id == "test_session_123"
        ).first()
        
        if test_record:
            print("   ✓ Test record found in database")
            print(f"      - ID: {test_record.id}")
            print(f"      - Session ID: {test_record.session_id}")
            print(f"      - Client IP: {test_record.client_ip}")
            print(f"      - Created at: {test_record.created_at}")
        else:
            print("   ✗ Test record NOT found in database")
        
        db.close()
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)

