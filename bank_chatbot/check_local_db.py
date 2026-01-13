"""
Script to check local PostgreSQL database for data
"""

import psycopg2
from psycopg2 import sql
import sys

def check_local_database():
    """Check local PostgreSQL database for data"""
    print("=" * 60)
    print("Local PostgreSQL Database Data Check")
    print("=" * 60)
    
    # Try to connect to local PostgreSQL
    connection_configs = [
        {
            "host": "localhost",
            "port": 5432,
            "database": "bank_chatbot",
            "user": "postgres",
            "password": "changeme"
        },
        {
            "host": "localhost",
            "port": 5432,
            "database": "postgres",
            "user": "postgres",
            "password": "changeme"
        }
    ]
    
    conn = None
    for config in connection_configs:
        try:
            print(f"\nTrying to connect to: {config['host']}:{config['port']}/{config['database']}")
            conn = psycopg2.connect(**config)
            print("✓ Connected successfully!")
            break
        except psycopg2.OperationalError as e:
            print(f"✗ Connection failed: {e}")
            continue
        except Exception as e:
            print(f"✗ Error: {e}")
            continue
    
    if conn is None:
        print("\n✗ Could not connect to any PostgreSQL database")
        print("\nPlease check:")
        print("1. Is PostgreSQL running? (docker ps)")
        print("2. Are the connection credentials correct?")
        return
    
    try:
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'chat_messages'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            print("\n✗ Table 'chat_messages' does not exist")
            print("\nAvailable tables:")
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = cursor.fetchall()
            for table in tables:
                print(f"  - {table[0]}")
            return
        
        print("✓ Table 'chat_messages' exists")
        print()
        
        # Count total messages
        cursor.execute("SELECT COUNT(*) FROM chat_messages;")
        total_count = cursor.fetchone()[0]
        print(f"Total Messages: {total_count}")
        
        if total_count == 0:
            print("\n⚠ Database is empty - no messages found")
        else:
            print(f"\n✓ Database contains {total_count} message(s)")
            print()
            
            # Get unique session IDs
            cursor.execute("SELECT COUNT(DISTINCT session_id) FROM chat_messages;")
            unique_sessions = cursor.fetchone()[0]
            print(f"Unique Sessions: {unique_sessions}")
            print()
            
            # Show sample messages
            print("Sample Messages (last 10):")
            print("-" * 60)
            cursor.execute("""
                SELECT id, session_id, role, message, created_at
                FROM chat_messages
                ORDER BY created_at DESC
                LIMIT 10;
            """)
            messages = cursor.fetchall()
            
            for msg in reversed(messages):
                msg_id, session_id, role, message, created_at = msg
                print(f"[{created_at}] "
                      f"Session: {session_id[:8]}... | "
                      f"Role: {role:10} | "
                      f"Message: {message[:50]}...")
            print("-" * 60)
            print()
            
            # Count by role
            cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE role = 'user';")
            user_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE role = 'assistant';")
            assistant_count = cursor.fetchone()[0]
            
            print(f"User Messages: {user_count}")
            print(f"Assistant Messages: {assistant_count}")
            print()
            
            # Show oldest and newest messages
            cursor.execute("""
                SELECT MIN(created_at), MAX(created_at)
                FROM chat_messages;
            """)
            oldest, newest = cursor.fetchone()
            
            if oldest and newest:
                print(f"Oldest Message: {oldest}")
                print(f"Newest Message: {newest}")
        
    except Exception as e:
        print(f"✗ Error querying database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()
            print("\n✓ Database connection closed")

if __name__ == "__main__":
    check_local_database()

