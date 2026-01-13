"""Migration script to add client_ip column to analytics_conversations table"""
import sys
import os
import asyncio

# Add bank_chatbot to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bank_chatbot'))

# Set environment
os.chdir('bank_chatbot')

from app.database.postgres import get_db, init_db
from sqlalchemy import text

print("=" * 60)
print("Adding client_ip column to analytics_conversations table")
print("=" * 60)

async def run_migration():
    # Initialize database first
    print("\n0. Initializing database connection...")
    await init_db()
    print("   [OK] Database initialized")
    
    try:
        db = get_db()
        if not db:
            print("ERROR: Could not get database connection")
            sys.exit(1)
        
        # Check if column already exists
        print("\n1. Checking if client_ip column exists...")
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='analytics_conversations' 
            AND column_name='client_ip'
        """)
        result = db.execute(check_query).fetchone()
        
        if result:
            print("   [OK] client_ip column already exists")
        else:
            print("   [MISSING] client_ip column does not exist - adding it...")
            
            # Add the column
            alter_query = text("""
                ALTER TABLE analytics_conversations 
                ADD COLUMN client_ip VARCHAR(45)
            """)
            db.execute(alter_query)
            db.commit()
            print("   [OK] client_ip column added successfully")
            
            # Create index on client_ip for better query performance
            print("\n2. Creating index on client_ip column...")
            try:
                index_query = text("""
                    CREATE INDEX idx_analytics_client_ip 
                    ON analytics_conversations(client_ip)
                """)
                db.execute(index_query)
                db.commit()
                print("   [OK] Index created successfully")
            except Exception as idx_error:
                # Index might already exist, that's okay
                if "already exists" in str(idx_error).lower():
                    print("   [INFO] Index already exists (skipping)")
                else:
                    print(f"   [WARNING] Could not create index: {idx_error}")
                    db.rollback()
        
        # Verify the column exists
        print("\n3. Verifying column was added...")
        verify_query = text("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns 
            WHERE table_name='analytics_conversations' 
            AND column_name='client_ip'
        """)
        result = db.execute(verify_query).fetchone()
        
        if result:
            print(f"   [OK] Column verified: {result[0]} ({result[1]})")
            if result[2]:
                print(f"   [OK] Max length: {result[2]} characters")
        else:
            print("   [ERROR] Column verification failed!")
        
        db.close()
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        if db:
            db.rollback()
            db.close()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_migration())
