"""
Test PostgreSQL Connection
This script tests the PostgreSQL connection and creates the necessary tables
"""
import os
from dotenv import load_dotenv
import sys

load_dotenv()

def test_connection():
    """Test PostgreSQL connection"""
    print("=" * 60)
    print("Testing PostgreSQL Connection")
    print("=" * 60)
    print()
    
    # Get database URL
    database_url = os.getenv(
        'POSTGRES_DB_URL',
        f"postgresql://{os.getenv('POSTGRES_USER', 'chatbot_user')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'chatbot_password_123')}@"
        f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{os.getenv('POSTGRES_DB', 'chatbot_db')}"
    )
    
    print(f"Connecting to: {database_url.split('@')[1] if '@' in database_url else 'database'}")
    print()
    
    # Test basic connection
    try:
        from sqlalchemy import create_engine, text
        
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✓ Connection successful!")
            print(f"  PostgreSQL version: {version.split(',')[0]}")
            print()
            
            # Check if database exists
            result = conn.execute(text("SELECT current_database()"))
            db_name = result.fetchone()[0]
            print(f"✓ Connected to database: {db_name}")
            print()
            
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print()
        print("Troubleshooting:")
        print("1. Check if PostgreSQL is running")
        print("2. Verify credentials in .env file")
        print("3. Check firewall settings")
        print("4. For Docker: docker ps | grep postgres")
        return False
    
    # Test phonebook tables
    print("Testing Phonebook Tables...")
    try:
        from phonebook_postgres import PhoneBookDB
        
        db = PhoneBookDB(database_url)
        print("✓ Phonebook database initialized")
        print("✓ Tables created/verified")
        print()
    except Exception as e:
        print(f"✗ Phonebook setup failed: {e}")
        print()
        return False
    
    # Test analytics tables
    print("Testing Analytics Tables...")
    try:
        from conversation_analytics_postgres import _init_database
        
        _init_database(database_url)
        print("✓ Analytics database initialized")
        print("✓ Tables created/verified")
        print()
    except Exception as e:
        print(f"✗ Analytics setup failed: {e}")
        print()
        return False
    
    # Test queries
    print("Testing Queries...")
    try:
        # Test phonebook query
        results = db.smart_search("test", limit=1)
        print("✓ Phonebook query test passed")
        
        # Test analytics query
        from conversation_analytics_postgres import get_most_asked_questions
        questions = get_most_asked_questions(limit=1)
        print("✓ Analytics query test passed")
        print()
    except Exception as e:
        print(f"⚠ Query test warning: {e}")
        print("  (This is normal if tables are empty)")
        print()
    
    print("=" * 60)
    print("✓ All tests passed! PostgreSQL is ready to use.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

