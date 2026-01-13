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
                print(f"PostgreSQL already has {existing_count} records.")
                print("Clearing existing data...")
                session.query(Employee).delete()
                session.commit()
                print("✓ Existing data cleared")
        
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
                    # sqlite3.Row uses bracket notation, not .get()
                    employee = Employee(
                        employee_id=record['employee_id'] if 'employee_id' in record.keys() else None,
                        full_name=record['full_name'],
                        first_name=record['first_name'] if 'first_name' in record.keys() else None,
                        last_name=record['last_name'] if 'last_name' in record.keys() else None,
                        designation=record['designation'] if 'designation' in record.keys() else None,
                        department=record['department'] if 'department' in record.keys() else None,
                        division=record['division'] if 'division' in record.keys() else None,
                        email=record['email'] if 'email' in record.keys() else None,
                        telephone=record['telephone'] if 'telephone' in record.keys() else None,
                        pabx=record['pabx'] if 'pabx' in record.keys() else None,
                        ip_phone=record['ip_phone'] if 'ip_phone' in record.keys() else None,
                        mobile=record['mobile'] if 'mobile' in record.keys() else None,
                        group_email=record['group_email'] if 'group_email' in record.keys() else None
                    )
                    session.add(employee)
                    migrated += 1
                    
                    if migrated % 100 == 0:
                        print(f"  Migrated {migrated}/{len(records)} records...")
                        session.commit()
                        
                except Exception as e:
                    failed += 1
                    full_name = record['full_name'] if 'full_name' in record.keys() else 'unknown'
                    print(f"  ⚠ Failed to migrate {full_name}: {e}")
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
                print(f"PostgreSQL already has {existing_conv} conversations.")
                print("Clearing existing data...")
                session.query(Conversation).delete()
                session.query(Question).delete()
                session.query(PerformanceMetric).delete()
                session.commit()
                print("✓ Existing data cleared")
        
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
                        created_at_str = record['created_at'] if 'created_at' in record.keys() and record['created_at'] else None
                        created_at = datetime.fromisoformat(created_at_str) if created_at_str else datetime.utcnow()
                        
                        conversation = Conversation(
                            session_id=record['session_id'],
                            user_message=record['user_message'],
                            assistant_response=record['assistant_response'],
                            is_answered=record['is_answered'],
                            knowledge_base=record['knowledge_base'] if 'knowledge_base' in record.keys() else None,
                            response_time_ms=record['response_time_ms'] if 'response_time_ms' in record.keys() else None,
                            created_at=created_at
                        )
                        session.add(conversation)
                        migrated += 1
                        
                        if migrated % 50 == 0:
                            print(f"  Migrated {migrated}/{len(conversations)} conversations...")
                            session.commit()
                            
                    except Exception as e:
                        failed += 1
                        conv_id = record['id'] if 'id' in record.keys() else 'unknown'
                        print(f"  ⚠ Failed to migrate conversation {conv_id}: {e}")
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
                        first_asked_str = record['first_asked'] if 'first_asked' in record.keys() and record['first_asked'] else None
                        last_asked_str = record['last_asked'] if 'last_asked' in record.keys() and record['last_asked'] else None
                        first_asked = datetime.fromisoformat(first_asked_str) if first_asked_str else datetime.utcnow()
                        last_asked = datetime.fromisoformat(last_asked_str) if last_asked_str else datetime.utcnow()
                        
                        question = Question(
                            question_text=record['question_text'],
                            normalized_question=record['normalized_question'] if 'normalized_question' in record.keys() else None,
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
                        date_str = record['date'] if 'date' in record.keys() and record['date'] else None
                        metric_date = date_type.fromisoformat(date_str) if date_str else date_type.today()
                        
                        metric = PerformanceMetric(
                            date=metric_date,
                            total_conversations=record['total_conversations'],
                            answered_count=record['answered_count'],
                            unanswered_count=record['unanswered_count'],
                            avg_response_time_ms=record['avg_response_time_ms'] if 'avg_response_time_ms' in record.keys() else None
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
            print("⚠ Phonebook migration failed. Continuing with analytics...")
    
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

