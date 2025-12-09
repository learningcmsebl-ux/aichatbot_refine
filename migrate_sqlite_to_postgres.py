"""
Migrate SQLite data to PostgreSQL
This script migrates phonebook and analytics data from SQLite to PostgreSQL
"""
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import sys

load_dotenv()

def migrate_phonebook():
    """Migrate phonebook data from SQLite to PostgreSQL"""
    print("=" * 60)
    print("Migrating Phonebook Data")
    print("=" * 60)
    print()
    
    # Check if SQLite database exists
    sqlite_path = "chatbot_convert/phonebook.db"
    if not os.path.exists(sqlite_path):
        print(f"✗ SQLite phonebook not found at: {sqlite_path}")
        return False
    
    # Connect to SQLite
    print(f"Reading from SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    
    # Count records
    sqlite_cursor.execute("SELECT COUNT(*) FROM employees")
    count = sqlite_cursor.fetchone()[0]
    print(f"Found {count} employee records in SQLite")
    print()
    
    if count == 0:
        print("No data to migrate")
        sqlite_conn.close()
        return True
    
    # Connect to PostgreSQL
    print("Connecting to PostgreSQL...")
    try:
        from phonebook_postgres import PhoneBookDB
        
        database_url = os.getenv(
            'PHONEBOOK_DB_URL',
            os.getenv('POSTGRES_DB_URL') or 
            f"postgresql://{os.getenv('POSTGRES_USER', 'chatbot_user')}:"
            f"{os.getenv('POSTGRES_PASSWORD', 'chatbot_password_123')}@"
            f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
            f"{os.getenv('POSTGRES_PORT', '5432')}/"
            f"{os.getenv('POSTGRES_DB', 'chatbot_db')}"
        )
        
        pg_db = PhoneBookDB(database_url)
        print("✓ Connected to PostgreSQL")
        print()
        
        # Check if PostgreSQL already has data
        with pg_db.get_session() as session:
            from phonebook_postgres import Employee
            existing_count = session.query(Employee).count()
            if existing_count > 0:
                response = input(f"PostgreSQL already has {existing_count} records. Overwrite? (y/N): ")
                if response.lower() != 'y':
                    print("Migration cancelled")
                    return False
                print("Clearing existing data...")
                session.query(Employee).delete()
                session.commit()
        
        # Read all records from SQLite
        print("Reading records from SQLite...")
        sqlite_cursor.execute("SELECT * FROM employees")
        records = sqlite_cursor.fetchall()
        
        # Insert into PostgreSQL
        print(f"Migrating {len(records)} records to PostgreSQL...")
        migrated = 0
        failed = 0
        
        with pg_db.get_session() as session:
            from phonebook_postgres import Employee
            
            for record in records:
                try:
                    employee = Employee(
                        employee_id=record['employee_id'],
                        full_name=record['full_name'],
                        first_name=record.get('first_name'),
                        last_name=record.get('last_name'),
                        designation=record.get('designation'),
                        department=record.get('department'),
                        division=record.get('division'),
                        email=record.get('email'),
                        telephone=record.get('telephone'),
                        pabx=record.get('pabx'),
                        ip_phone=record.get('ip_phone'),
                        mobile=record.get('mobile'),
                        group_email=record.get('group_email')
                    )
                    session.add(employee)
                    migrated += 1
                    
                    if migrated % 100 == 0:
                        print(f"  Migrated {migrated}/{len(records)} records...")
                        session.commit()
                        
                except Exception as e:
                    failed += 1
                    print(f"  ⚠ Failed to migrate {record.get('full_name', 'unknown')}: {e}")
                    continue
            
            session.commit()
        
        sqlite_conn.close()
        
        print()
        print(f"✓ Migration complete!")
        print(f"  Migrated: {migrated} records")
        if failed > 0:
            print(f"  Failed: {failed} records")
        print()
        
        # Verify
        with pg_db.get_session() as session:
            from phonebook_postgres import Employee
            pg_count = session.query(Employee).count()
            print(f"✓ Verification: PostgreSQL now has {pg_count} records")
            print()
        
        return True
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sqlite_conn.close()
        return False


def migrate_analytics():
    """Migrate analytics data from SQLite to PostgreSQL"""
    print("=" * 60)
    print("Migrating Analytics Data")
    print("=" * 60)
    print()
    
    # Check if SQLite database exists
    sqlite_path = "chatbot_convert/analytics/conversations.db"
    if not os.path.exists(sqlite_path):
        print(f"✗ SQLite analytics not found at: {sqlite_path}")
        return False
    
    # Connect to SQLite
    print(f"Reading from SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    
    # Count records
    sqlite_cursor.execute("SELECT COUNT(*) FROM conversations")
    conv_count = sqlite_cursor.fetchone()[0]
    
    sqlite_cursor.execute("SELECT COUNT(*) FROM questions")
    questions_count = sqlite_cursor.fetchone()[0]
    
    sqlite_cursor.execute("SELECT COUNT(*) FROM performance_metrics")
    metrics_count = sqlite_cursor.fetchone()[0]
    
    print(f"Found:")
    print(f"  Conversations: {conv_count}")
    print(f"  Questions: {questions_count}")
    print(f"  Performance Metrics: {metrics_count}")
    print()
    
    if conv_count == 0 and questions_count == 0 and metrics_count == 0:
        print("No data to migrate")
        sqlite_conn.close()
        return True
    
    # Connect to PostgreSQL
    print("Connecting to PostgreSQL...")
    try:
        from conversation_analytics_postgres import _init_database, _get_session, Conversation, Question, PerformanceMetric
        
        database_url = os.getenv(
            'ANALYTICS_DB_URL',
            os.getenv('POSTGRES_DB_URL') or 
            f"postgresql://{os.getenv('POSTGRES_USER', 'chatbot_user')}:"
            f"{os.getenv('POSTGRES_PASSWORD', 'chatbot_password_123')}@"
            f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
            f"{os.getenv('POSTGRES_PORT', '5432')}/"
            f"{os.getenv('POSTGRES_DB', 'chatbot_db')}"
        )
        
        _init_database(database_url)
        print("✓ Connected to PostgreSQL")
        print()
        
        # Check if PostgreSQL already has data
        with _get_session() as session:
            existing_conv = session.query(Conversation).count()
            if existing_conv > 0:
                response = input(f"PostgreSQL already has {existing_conv} conversations. Overwrite? (y/N): ")
                if response.lower() != 'y':
                    print("Migration cancelled")
                    return False
                print("Clearing existing data...")
                session.query(Conversation).delete()
                session.query(Question).delete()
                session.query(PerformanceMetric).delete()
                session.commit()
        
        # Migrate conversations
        if conv_count > 0:
            print(f"Migrating {conv_count} conversations...")
            sqlite_cursor.execute("SELECT * FROM conversations")
            conversations = sqlite_cursor.fetchall()
            
            migrated = 0
            failed = 0
            
            with _get_session() as session:
                for record in conversations:
                    try:
                        # Parse datetime
                        created_at = datetime.fromisoformat(record['created_at']) if record['created_at'] else datetime.utcnow()
                        
                        conversation = Conversation(
                            session_id=record['session_id'],
                            user_message=record['user_message'],
                            assistant_response=record['assistant_response'],
                            is_answered=record['is_answered'],
                            knowledge_base=record.get('knowledge_base'),
                            response_time_ms=record.get('response_time_ms'),
                            created_at=created_at
                        )
                        session.add(conversation)
                        migrated += 1
                        
                        if migrated % 50 == 0:
                            print(f"  Migrated {migrated}/{len(conversations)} conversations...")
                            session.commit()
                            
                    except Exception as e:
                        failed += 1
                        print(f"  ⚠ Failed to migrate conversation {record.get('id', 'unknown')}: {e}")
                        continue
                
                session.commit()
            
            print(f"  ✓ Migrated {migrated} conversations")
            if failed > 0:
                print(f"  ⚠ Failed: {failed} conversations")
            print()
        
        # Migrate questions
        if questions_count > 0:
            print(f"Migrating {questions_count} questions...")
            sqlite_cursor.execute("SELECT * FROM questions")
            questions = sqlite_cursor.fetchall()
            
            migrated = 0
            failed = 0
            
            with _get_session() as session:
                for record in questions:
                    try:
                        first_asked = datetime.fromisoformat(record['first_asked']) if record['first_asked'] else datetime.utcnow()
                        last_asked = datetime.fromisoformat(record['last_asked']) if record['last_asked'] else datetime.utcnow()
                        
                        question = Question(
                            question_text=record['question_text'],
                            normalized_question=record.get('normalized_question'),
                            total_asked=record['total_asked'],
                            answered_count=record['answered_count'],
                            unanswered_count=record['unanswered_count'],
                            first_asked=first_asked,
                            last_asked=last_asked
                        )
                        session.add(question)
                        migrated += 1
                        
                    except Exception as e:
                        failed += 1
                        print(f"  ⚠ Failed to migrate question: {e}")
                        continue
                
                session.commit()
            
            print(f"  ✓ Migrated {migrated} questions")
            if failed > 0:
                print(f"  ⚠ Failed: {failed} questions")
            print()
        
        # Migrate performance metrics
        if metrics_count > 0:
            print(f"Migrating {metrics_count} performance metrics...")
            sqlite_cursor.execute("SELECT * FROM performance_metrics")
            metrics = sqlite_cursor.fetchall()
            
            migrated = 0
            failed = 0
            
            with _get_session() as session:
                for record in metrics:
                    try:
                        # Parse date
                        from datetime import date as date_type
                        metric_date = date_type.fromisoformat(record['date']) if record['date'] else date_type.today()
                        
                        metric = PerformanceMetric(
                            date=metric_date,
                            total_conversations=record['total_conversations'],
                            answered_count=record['answered_count'],
                            unanswered_count=record['unanswered_count'],
                            avg_response_time_ms=record.get('avg_response_time_ms')
                        )
                        session.add(metric)
                        migrated += 1
                        
                    except Exception as e:
                        failed += 1
                        print(f"  ⚠ Failed to migrate metric: {e}")
                        continue
                
                session.commit()
            
            print(f"  ✓ Migrated {migrated} performance metrics")
            if failed > 0:
                print(f"  ⚠ Failed: {failed} metrics")
            print()
        
        sqlite_conn.close()
        
        print("=" * 60)
        print("✓ Analytics migration complete!")
        print("=" * 60)
        print()
        
        # Verify
        with _get_session() as session:
            pg_conv = session.query(Conversation).count()
            pg_questions = session.query(Question).count()
            pg_metrics = session.query(PerformanceMetric).count()
            print(f"✓ Verification:")
            print(f"  Conversations: {pg_conv}")
            print(f"  Questions: {pg_questions}")
            print(f"  Performance Metrics: {pg_metrics}")
            print()
        
        return True
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sqlite_conn.close()
        return False


def main():
    """Main migration function"""
    print()
    print("=" * 60)
    print("SQLite to PostgreSQL Migration")
    print("=" * 60)
    print()
    
    # Check what needs to be migrated
    phonebook_exists = os.path.exists("chatbot_convert/phonebook.db")
    analytics_exists = os.path.exists("chatbot_convert/analytics/conversations.db")
    
    if not phonebook_exists and not analytics_exists:
        print("No SQLite databases found to migrate")
        print("  Expected:")
        print("    - chatbot_convert/phonebook.db")
        print("    - chatbot_convert/analytics/conversations.db")
        return
    
    print("Found SQLite databases:")
    if phonebook_exists:
        print("  ✓ phonebook.db")
    if analytics_exists:
        print("  ✓ analytics/conversations.db")
    print()
    
    # Migrate phonebook
    if phonebook_exists:
        success = migrate_phonebook()
        if not success:
            print("Phonebook migration failed. Continue with analytics? (y/N): ", end="")
            response = input()
            if response.lower() != 'y':
                return
    
    # Migrate analytics
    if analytics_exists:
        success = migrate_analytics()
        if not success:
            print("Analytics migration failed")
            return
    
    print()
    print("=" * 60)
    print("✓ All migrations complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Update your application code to use PostgreSQL implementations")
    print("2. Test the application")
    print("3. Verify data integrity")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Migration error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

