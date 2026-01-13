"""
Check conversations in database and verify client_ip column
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database.postgres import get_db, engine
from sqlalchemy import text, inspect

def check_conversations():
    """Check conversations and IP tracking"""
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
            print("   Restart the backend to create the table")
            db.close()
            return False
        
        # Check columns
        columns = inspector.get_columns('analytics_conversations')
        column_names = [col['name'] for col in columns]
        
        print("=" * 70)
        print("CONVERSATIONS DATABASE CHECK")
        print("=" * 70)
        
        # Check if client_ip column exists
        has_ip_column = 'client_ip' in column_names
        print(f"\n✓ client_ip column exists: {has_ip_column}")
        
        if not has_ip_column:
            print("\n⚠️  client_ip column is missing!")
            print("   Restart the backend to create the column")
            db.close()
            return False
        
        # Count conversations
        result = db.execute(text("SELECT COUNT(*) FROM analytics_conversations"))
        total = result.scalar()
        print(f"\n✓ Total conversations: {total}")
        
        if total == 0:
            print("\n⚠️  No conversations in database yet")
            print("   Send a test message from the chatbot to create a conversation")
            db.close()
            return False
        
        # Count with IP
        result = db.execute(text("""
            SELECT COUNT(*) FROM analytics_conversations 
            WHERE client_ip IS NOT NULL
        """))
        with_ip = result.scalar()
        print(f"✓ Conversations with IP: {with_ip}")
        
        # Count without IP
        result = db.execute(text("""
            SELECT COUNT(*) FROM analytics_conversations 
            WHERE client_ip IS NULL
        """))
        without_ip = result.scalar()
        print(f"✓ Conversations without IP: {without_ip}")
        
        # Show sample conversations
        if total > 0:
            print("\n" + "=" * 70)
            print("SAMPLE CONVERSATIONS (last 5):")
            print("=" * 70)
            result = db.execute(text("""
                SELECT id, session_id, user_message, client_ip, created_at
                FROM analytics_conversations
                ORDER BY created_at DESC
                LIMIT 5
            """))
            rows = result.fetchall()
            for i, row in enumerate(rows, 1):
                print(f"\n{i}. ID: {row[0]}")
                print(f"   Session: {row[1]}")
                print(f"   Message: {row[2][:50]}..." if len(row[2]) > 50 else f"   Message: {row[2]}")
                print(f"   IP: {row[3] or 'NULL'}")
                print(f"   Time: {row[4]}")
        
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
    check_conversations()

