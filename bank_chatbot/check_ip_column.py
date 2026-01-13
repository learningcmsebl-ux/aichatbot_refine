"""
Check if client_ip column exists in analytics_conversations table
"""

import sys
from pathlib import Path

# Add bank_chatbot to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database.postgres import get_db, engine
from sqlalchemy import inspect, text

def check_ip_column():
    """Check if client_ip column exists"""
    if not engine:
        print("❌ Database engine not initialized")
        return False
    
    try:
        db = get_db()
        if not db:
            print("❌ Cannot get database session")
            return False
        
        # Check if table exists
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'analytics_conversations' not in tables:
            print("❌ analytics_conversations table does not exist")
            print("   The table will be created when you restart the backend")
            db.close()
            return False
        
        # Check columns
        columns = inspector.get_columns('analytics_conversations')
        column_names = [col['name'] for col in columns]
        
        print("Columns in analytics_conversations table:")
        for col in column_names:
            marker = "✓" if col == "client_ip" else " "
            print(f"  {marker} {col}")
        
        if 'client_ip' in column_names:
            print("\n✅ client_ip column exists!")
            
            # Check if there are any conversations with IP
            result = db.execute(text("SELECT COUNT(*) FROM analytics_conversations WHERE client_ip IS NOT NULL"))
            count = result.scalar()
            print(f"   Conversations with IP: {count}")
            
            db.close()
            return True
        else:
            print("\n❌ client_ip column does NOT exist")
            print("   Restart the backend to create the column")
            db.close()
            return False
            
    except Exception as e:
        print(f"❌ Error checking column: {e}")
        if db:
            db.close()
        return False

if __name__ == "__main__":
    check_ip_column()

