"""
Check if chat monitoring is active and working
"""

import sys
from pathlib import Path

# Add bank_chatbot to path
sys.path.insert(0, str(Path(__file__).parent / "bank_chatbot"))

from app.database.postgres import get_db, ChatMessage, engine
from sqlalchemy import func, text

def check_monitoring_status():
    """Check if chat monitoring is active"""
    
    print("="*70)
    print("CHAT MONITORING STATUS CHECK")
    print("="*70)
    
    # Check database connection
    print("\n1. Database Connection:")
    if engine is None:
        print("   ❌ PostgreSQL engine not initialized")
        print("   ⚠️  Chat monitoring is NOT active")
        return False
    else:
        print("   ✓ PostgreSQL engine initialized")
    
    # Check if we can get a database session
    db = get_db()
    if db is None:
        print("   ❌ Cannot get database session")
        print("   ⚠️  Chat monitoring is NOT active")
        return False
    else:
        print("   ✓ Database session available")
    
    # Check if table exists and has data
    try:
        # Count total messages
        total_count = db.query(func.count(ChatMessage.id)).scalar()
        print(f"\n2. Message Storage:")
        print(f"   ✓ Total messages stored: {total_count:,}")
        
        # Get recent messages
        recent_messages = db.query(ChatMessage).order_by(
            ChatMessage.created_at.desc()
        ).limit(5).all()
        
        if recent_messages:
            print(f"\n3. Recent Messages (last 5):")
            for msg in recent_messages:
                preview = msg.message[:60].replace('\n', ' ')
                print(f"   [{msg.created_at}] {msg.role.upper()}: {preview}...")
        else:
            print("\n3. Recent Messages:")
            print("   No messages stored yet")
        
        # Count by role
        user_count = db.query(func.count(ChatMessage.id)).filter(
            ChatMessage.role == 'user'
        ).scalar()
        assistant_count = db.query(func.count(ChatMessage.id)).filter(
            ChatMessage.role == 'assistant'
        ).scalar()
        
        print(f"\n4. Message Statistics:")
        print(f"   User messages: {user_count:,}")
        print(f"   Assistant messages: {assistant_count:,}")
        
        # Count unique sessions
        session_count = db.query(func.count(func.distinct(ChatMessage.session_id))).scalar()
        print(f"   Unique sessions: {session_count:,}")
        
        db.close()
        
        print("\n" + "="*70)
        print("✓ CHAT MONITORING IS ACTIVE")
        print("="*70)
        print("\nAll conversations are being logged to PostgreSQL database.")
        print("Messages are stored with:")
        print("  - Session ID (for conversation tracking)")
        print("  - Role (user/assistant)")
        print("  - Message content")
        print("  - Timestamp")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error checking database: {e}")
        print("   ⚠️  Chat monitoring may not be working properly")
        if db:
            db.close()
        return False


if __name__ == "__main__":
    check_monitoring_status()

