"""Quick check for ConversationLog table"""
import os
import sys

# Add bank_chatbot to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot'))

# Set environment
os.chdir('bank_chatbot')

from app.database.postgres import get_db
from app.services.analytics import ConversationLog
from sqlalchemy import inspect

print("Checking ConversationLog table...")
db = get_db()
if db:
    try:
        inspector = inspect(db.bind)
        tables = inspector.get_table_names()
        print(f"Available tables: {tables}")
        
        if 'analytics_conversations' in tables:
            print("✓ analytics_conversations table exists")
            count = db.query(ConversationLog).count()
            print(f"✓ Record count: {count}")
            
            if count > 0:
                # Show first few records
                records = db.query(ConversationLog).order_by(ConversationLog.created_at.desc()).limit(3).all()
                print(f"\nRecent records:")
                for r in records:
                    print(f"  - ID: {r.id}, Session: {r.session_id[:20]}..., IP: {r.client_ip}, Created: {r.created_at}")
        else:
            print("✗ analytics_conversations table DOES NOT EXIST")
            print("  This means the table was not created during init_db()")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
else:
    print("✗ Could not get database connection")

