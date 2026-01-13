"""
Add client_ip column to analytics_conversations table if it doesn't exist
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database.postgres import engine, get_db
from sqlalchemy import text, inspect

def add_ip_column():
    """Add client_ip column if it doesn't exist"""
    if not engine:
        print("❌ Database engine not initialized")
        print("   Make sure the backend is running")
        return False
    
    try:
        db = get_db()
        if not db:
            print("❌ Cannot get database session")
            return False
        
        # Check if table exists
        inspector = inspect(engine)
        if 'analytics_conversations' not in inspector.get_table_names():
            print("❌ analytics_conversations table does not exist")
            print("   Restart the backend to create all tables")
            db.close()
            return False
        
        # Check if column exists
        columns = inspector.get_columns('analytics_conversations')
        column_names = [col['name'] for col in columns]
        
        if 'client_ip' in column_names:
            print("✅ client_ip column already exists")
            
            # Check how many conversations have IP
            result = db.execute(text("""
                SELECT COUNT(*) as total,
                       COUNT(client_ip) as with_ip,
                       COUNT(CASE WHEN client_ip IS NULL THEN 1 END) as without_ip
                FROM analytics_conversations
            """))
            row = result.fetchone()
            print(f"   Total conversations: {row[0]}")
            print(f"   With IP address: {row[1]}")
            print(f"   Without IP address: {row[2]}")
            
            db.close()
            return True
        else:
            print("⚠️  client_ip column does NOT exist")
            print("   Adding column...")
            
            # Add the column
            db.execute(text("""
                ALTER TABLE analytics_conversations 
                ADD COLUMN client_ip VARCHAR(45)
            """))
            
            # Create index
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_analytics_client_ip 
                ON analytics_conversations(client_ip)
            """))
            
            db.commit()
            print("✅ client_ip column added successfully!")
            print("   Index created")
            
            db.close()
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        if db:
            db.rollback()
            db.close()
        return False

if __name__ == "__main__":
    add_ip_column()

