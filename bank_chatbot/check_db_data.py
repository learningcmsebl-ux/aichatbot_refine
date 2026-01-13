"""
Script to check if PostgreSQL database has data
"""

import sys
from app.database.postgres import init_db, get_db, ChatMessage, engine, SessionLocal
from app.core.config import settings
import asyncio

async def check_database_data():
    """Check if database has any data"""
    print("=" * 60)
    print("PostgreSQL Database Data Check")
    print("=" * 60)
    print(f"Database Host: {settings.POSTGRES_HOST}")
    print(f"Database Port: {settings.POSTGRES_PORT}")
    print(f"Database Name: {settings.POSTGRES_DB}")
    print(f"Database User: {settings.POSTGRES_USER}")
    print("=" * 60)
    print()
    
    # Initialize database
    try:
        await init_db()
        print("✓ Database connection initialized")
    except Exception as e:
        print(f"✗ Failed to initialize database: {e}")
        return
    
    # Check if engine is available
    if engine is None:
        print("✗ Database engine is not available")
        print("  (Database connection failed during initialization)")
        return
    
    # Get database session
    db = get_db()
    if db is None:
        print("✗ Failed to get database session")
        return
    
    try:
        # Check if table exists
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'chat_messages' not in tables:
            print("✗ Table 'chat_messages' does not exist")
            print(f"  Available tables: {tables}")
            return
        
        print("✓ Table 'chat_messages' exists")
        print()
        
        # Count total messages
        total_count = db.query(ChatMessage).count()
        print(f"Total Messages: {total_count}")
        
        if total_count == 0:
            print("\n⚠ Database is empty - no messages found")
        else:
            print(f"\n✓ Database contains {total_count} message(s)")
            print()
            
            # Get unique session IDs
            session_ids = db.query(ChatMessage.session_id).distinct().all()
            unique_sessions = len(session_ids)
            print(f"Unique Sessions: {unique_sessions}")
            print()
            
            # Show sample messages
            print("Sample Messages (last 10):")
            print("-" * 60)
            recent_messages = db.query(ChatMessage).order_by(
                ChatMessage.created_at.desc()
            ).limit(10).all()
            
            for msg in reversed(recent_messages):
                print(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] "
                      f"Session: {msg.session_id[:8]}... | "
                      f"Role: {msg.role:10} | "
                      f"Message: {msg.message[:50]}...")
            print("-" * 60)
            print()
            
            # Count by role
            user_count = db.query(ChatMessage).filter(
                ChatMessage.role == 'user'
            ).count()
            assistant_count = db.query(ChatMessage).filter(
                ChatMessage.role == 'assistant'
            ).count()
            
            print(f"User Messages: {user_count}")
            print(f"Assistant Messages: {assistant_count}")
            print()
            
            # Show oldest and newest messages
            oldest = db.query(ChatMessage).order_by(
                ChatMessage.created_at.asc()
            ).first()
            newest = db.query(ChatMessage).order_by(
                ChatMessage.created_at.desc()
            ).first()
            
            if oldest and newest:
                print(f"Oldest Message: {oldest.created_at}")
                print(f"Newest Message: {newest.created_at}")
        
    except Exception as e:
        print(f"✗ Error querying database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        print("\n✓ Database session closed")

if __name__ == "__main__":
    asyncio.run(check_database_data())

