"""
Test the conversation history query directly
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database.postgres import get_db, engine
from app.services.analytics import ConversationLog
from sqlalchemy import text, inspect

def test_history_query():
    """Test the conversation history query"""
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
        if 'analytics_conversations' not in inspector.get_table_names():
            print("ERROR: analytics_conversations table does not exist")
            db.close()
            return False
        
        # Count total conversations
        result = db.execute(text("SELECT COUNT(*) FROM analytics_conversations"))
        total = result.scalar()
        print(f"Total conversations in database: {total}")
        
        if total == 0:
            print("No conversations found in database")
            db.close()
            return False
        
        # Try the actual query from get_conversation_history
        conversations = db.query(ConversationLog).order_by(
            ConversationLog.created_at.desc()
        ).limit(10).all()
        
        print(f"\nQuery returned {len(conversations)} conversations")
        
        if len(conversations) > 0:
            print("\nSample conversation:")
            conv = conversations[0]
            print(f"  ID: {conv.id}")
            print(f"  Session: {conv.session_id}")
            print(f"  Message: {conv.user_message[:50]}...")
            print(f"  IP: {conv.client_ip}")
            print(f"  Created: {conv.created_at}")
        
        # Test the exact query used in the function
        print("\nTesting direct SQL query:")
        result = db.execute(text("""
            SELECT id, session_id, user_message, client_ip, created_at
            FROM analytics_conversations
            ORDER BY created_at DESC
            LIMIT 5
        """))
        rows = result.fetchall()
        print(f"SQL query returned {len(rows)} rows")
        for row in rows:
            print(f"  ID: {row[0]}, Session: {row[1]}, IP: {row[4]}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        if db:
            db.close()
        return False

if __name__ == "__main__":
    test_history_query()

