"""
Test if ConversationLog table exists and can be written to
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database.postgres import get_db, engine
from app.services.analytics import ConversationLog
from sqlalchemy import inspect, text

def test_conversation_log():
    """Test ConversationLog table"""
    if not engine:
        print("ERROR: Database engine not initialized")
        return False
    
    try:
        db = get_db()
        if not db:
            print("ERROR: Cannot get database session")
            return False
        
        # Check if table exists
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print("=" * 70)
        print("CONVERSATION LOG TABLE TEST")
        print("=" * 70)
        
        if 'analytics_conversations' not in tables:
            print("\nERROR: analytics_conversations table does NOT exist!")
            print("Available tables:", tables)
            print("\nThe table should be created when the backend starts.")
            print("Make sure the backend was restarted after adding ConversationLog model.")
            db.close()
            return False
        
        print("\n✓ analytics_conversations table exists")
        
        # Check columns
        columns = inspector.get_columns('analytics_conversations')
        column_names = [col['name'] for col in columns]
        print(f"✓ Table has {len(columns)} columns: {', '.join(column_names)}")
        
        # Check if client_ip column exists
        if 'client_ip' in column_names:
            print("✓ client_ip column exists")
        else:
            print("WARNING: client_ip column does NOT exist")
        
        # Count existing records
        result = db.execute(text("SELECT COUNT(*) FROM analytics_conversations"))
        count = result.scalar()
        print(f"\nCurrent records in table: {count}")
        
        # Try to insert a test record
        print("\nTesting insert...")
        try:
            test_conv = ConversationLog(
                session_id="test_session_123",
                user_message="Test message",
                assistant_response="Test response",
                is_answered=1,
                client_ip="127.0.0.1"
            )
            db.add(test_conv)
            db.commit()
            print("✓ Successfully inserted test record")
            
            # Verify it was saved
            result = db.execute(text("SELECT COUNT(*) FROM analytics_conversations WHERE session_id = 'test_session_123'"))
            verify_count = result.scalar()
            if verify_count > 0:
                print("✓ Test record verified in database")
                
                # Clean up test record
                db.execute(text("DELETE FROM analytics_conversations WHERE session_id = 'test_session_123'"))
                db.commit()
                print("✓ Test record cleaned up")
            else:
                print("WARNING: Test record not found after insert")
            
        except Exception as insert_error:
            print(f"ERROR: Failed to insert test record: {insert_error}")
            import traceback
            traceback.print_exc()
            db.rollback()
            db.close()
            return False
        
        db.close()
        print("\n" + "=" * 70)
        print("TEST PASSED: ConversationLog table is working correctly!")
        print("=" * 70)
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        if db:
            db.close()
        return False

if __name__ == "__main__":
    test_conversation_log()

