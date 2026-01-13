"""
Master import script for all 4 product lines
1. Applies schema extension (adds product_line column)
2. Deletes ALL existing data from card_fee_master
3. Imports all 4 product lines in sequence
4. Provides summary report

Usage:
    python import_all_product_lines.py          # Interactive mode
    python import_all_product_lines.py --yes    # Non-interactive mode

Environment Variables:
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
    OR
    FEE_ENGINE_DB_URL (full connection string)
    OR
    POSTGRES_DB_URL (full connection string)
"""
import sys
import os
from pathlib import Path
from sqlalchemy import text

# Load environment variables from .env file FIRST (before importing fee_engine_service)
try:
    from dotenv import load_dotenv
    # Try loading from project root
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment variables from: {env_path}")
    # Also try from bank_chatbot directory (where .env likely is)
    env_path_chatbot = Path(__file__).parent.parent.parent / 'bank_chatbot' / '.env'
    if env_path_chatbot.exists():
        load_dotenv(env_path_chatbot)
        print(f"Loaded environment variables from: {env_path_chatbot}")
    # Also try from fee_engine directory
    env_path_local = Path(__file__).parent / '.env'
    if env_path_local.exists():
        load_dotenv(env_path_local)
        print(f"Loaded environment variables from: {env_path_local}")
except ImportError:
    pass  # dotenv not available, use system environment variables

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from fee_engine_service import CardFeeMaster, SessionLocal, engine

def apply_schema_extension():
    """Apply schema extension to add product_line column and fix column sizes"""
    print(f"\n{'='*70}")
    print("Step 1: Applying Schema Extension & Column Size Fixes")
    print(f"{'='*70}")
    
    schema_extension_path = Path(__file__).parent / "schema_extension.sql"
    
    if not schema_extension_path.exists():
        print(f"Warning: Schema extension file not found: {schema_extension_path}")
        print("Attempting to add column directly...")
        
        try:
            with engine.connect() as conn:
                # Check if column already exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'card_fee_master' 
                    AND column_name = 'product_line'
                """))
                
                if result.fetchone():
                    print("  Column 'product_line' already exists")
                else:
                    print("  Adding 'product_line' column...")
                    conn.execute(text("""
                        ALTER TABLE card_fee_master 
                        ADD COLUMN product_line VARCHAR(50) DEFAULT 'CREDIT_CARDS'
                    """))
                    conn.execute(text("""
                        ALTER TABLE card_fee_master 
                        ALTER COLUMN product_line SET NOT NULL
                    """))
                    conn.commit()
                    print("  [OK] Column added successfully")
                    
                    # Add index
                    try:
                        conn.execute(text("""
                            CREATE INDEX idx_fee_product_line 
                            ON card_fee_master(product_line)
                        """))
                        conn.commit()
                        print("  [OK] Index created")
                    except Exception as e:
                        print(f"  Warning: Could not create index (may already exist): {e}")
        except Exception as e:
            print(f"  Error applying schema extension: {e}")
            print("  Continuing anyway (column may already exist)...")
    else:
        print(f"  Reading schema extension from: {schema_extension_path.name}")
        with open(schema_extension_path, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        try:
            with engine.connect() as conn:
                # First, check if column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'card_fee_master' 
                    AND column_name = 'product_line'
                """))
                
                column_exists = result.fetchone() is not None
                
                if not column_exists:
                    print("  Adding 'product_line' column...")
                    # Add column
                    conn.execute(text("""
                        ALTER TABLE card_fee_master 
                        ADD COLUMN product_line VARCHAR(50) DEFAULT 'CREDIT_CARDS'
                    """))
                    # Update existing records
                    conn.execute(text("""
                        UPDATE card_fee_master 
                        SET product_line = 'CREDIT_CARDS' 
                        WHERE product_line IS NULL
                    """))
                    # Make NOT NULL
                    conn.execute(text("""
                        ALTER TABLE card_fee_master 
                        ALTER COLUMN product_line SET NOT NULL
                    """))
                    conn.commit()
                    print("  [OK] Column added successfully")
                else:
                    print("  Column 'product_line' already exists")
                
                # Now handle indexes - drop old index if it exists, then create new one
                try:
                    conn.execute(text("DROP INDEX IF EXISTS idx_fee_lookup"))
                    conn.commit()
                except Exception as e:
                    pass  # Ignore if doesn't exist
                
                # Create new index with product_line
                try:
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_fee_product_line 
                        ON card_fee_master(product_line)
                    """))
                    conn.execute(text("""
                        CREATE INDEX idx_fee_lookup 
                        ON card_fee_master(charge_type, product_line, card_category, card_network, card_product, status, effective_from, effective_to)
                    """))
                    conn.commit()
                    print("  [OK] Indexes created/updated")
                except Exception as e:
                    if 'already exists' not in str(e).lower():
                        print(f"  Warning: Could not create index: {e}")
                
                print("  [OK] Schema extension applied")
                
                # Apply column size fixes
                print("\n  Applying column size fixes...")
                try:
                    conn.execute(text("""
                        ALTER TABLE card_fee_master 
                        ALTER COLUMN charge_type TYPE VARCHAR(255)
                    """))
                    conn.execute(text("""
                        ALTER TABLE card_fee_master 
                        ALTER COLUMN card_product TYPE VARCHAR(100)
                    """))
                    conn.commit()
                    print("  [OK] Column sizes updated (charge_type: 255, card_product: 100)")
                except Exception as e:
                    if 'does not exist' not in str(e).lower() and 'already' not in str(e).lower():
                        print(f"  Warning: Could not update column sizes: {e}")
        except Exception as e:
            print(f"  Error applying schema extension: {e}")
            print("  Continuing anyway...")

def delete_all_data():
    """Delete ALL existing data from card_fee_master table"""
    print(f"\n{'='*70}")
    print("Step 2: Deleting All Existing Data")
    print(f"{'='*70}")
    
    # Use raw SQL to avoid ORM issues if product_line column doesn't exist yet
    try:
        with engine.connect() as conn:
            # Count existing records using raw SQL
            count_result = conn.execute(text("SELECT COUNT(*) FROM card_fee_master"))
            count = count_result.scalar()
            print(f"  Found {count} existing records")
            
            if count > 0:
                # Delete all records using raw SQL
                conn.execute(text("DELETE FROM card_fee_master"))
                conn.commit()
                print(f"  [OK] Deleted {count} records")
            else:
                print("  No existing records to delete")
    except Exception as e:
        print(f"  Error deleting data: {e}")
        raise

def import_all():
    """Import all product lines"""
    print(f"\n{'='*70}")
    print("Step 3: Importing All Product Lines")
    print(f"{'='*70}")
    
    importers = [
        ("Credit Cards", "import_credit_cards"),
        ("Skybanking", "import_skybanking"),
        ("Priority Banking", "import_priority_banking"),
        ("Retail Assets", "import_retail_assets"),
    ]
    
    results = {}
    
    for product_line_name, module_name in importers:
        try:
            print(f"\n  Importing {product_line_name}...")
            module = __import__(module_name, fromlist=[''])
            import_func = getattr(module, f"import_{module_name.replace('import_', '')}")
            import_func()
            results[product_line_name] = "Success"
        except Exception as e:
            print(f"  ✗ Error importing {product_line_name}: {e}")
            results[product_line_name] = f"Error: {e}"
            import traceback
            traceback.print_exc()
    
    return results

def generate_summary():
    """Generate summary report"""
    print(f"\n{'='*70}")
    print("Step 4: Summary Report")
    print(f"{'='*70}")
    
    db = SessionLocal()
    
    try:
        # Count by product line
        from sqlalchemy import func
        counts = db.query(
            CardFeeMaster.product_line,
            func.count(CardFeeMaster.fee_id).label('count')
        ).group_by(CardFeeMaster.product_line).all()
        
        print("\n  Records by Product Line:")
        total = 0
        for product_line, count in counts:
            print(f"    {product_line}: {count} records")
            total += count
        
        print(f"\n  Total: {total} records")
        
        # Count by status
        status_counts = db.query(
            CardFeeMaster.status,
            func.count(CardFeeMaster.fee_id).label('count')
        ).group_by(CardFeeMaster.status).all()
        
        print("\n  Records by Status:")
        for status, count in status_counts:
            print(f"    {status}: {count} records")
        
    except Exception as e:
        print(f"  Error generating summary: {e}")
    finally:
        db.close()

def main():
    """Main execution"""
    import sys
    
    print("="*70)
    print("Fee Engine - Import All Product Lines")
    print("="*70)
    print("\nThis script will:")
    print("  1. Apply schema extension (add product_line column)")
    print("  2. Delete ALL existing data from card_fee_master")
    print("  3. Import all 4 product lines:")
    print("     - Credit Cards")
    print("     - Skybanking")
    print("     - Priority Banking")
    print("     - Retail Assets/Loans")
    print("  4. Generate summary report")
    
    # Check for --yes flag or AUTO_IMPORT environment variable
    auto_confirm = '--yes' in sys.argv or '--y' in sys.argv or os.getenv('AUTO_IMPORT', '').lower() == 'true'
    
    if not auto_confirm:
        try:
            response = input("\nProceed? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("Cancelled.")
                return
        except (EOFError, KeyboardInterrupt):
            print("\nNon-interactive mode detected. Use --yes flag or set AUTO_IMPORT=true to proceed automatically.")
            return
    else:
        print("\nAuto-confirming (--yes flag or AUTO_IMPORT=true detected)...")
    
    try:
        # Step 1: Apply schema extension
        apply_schema_extension()
        
        # Step 2: Delete all data
        delete_all_data()
        
        # Step 3: Import all product lines
        results = import_all()
        
        # Step 4: Generate summary
        generate_summary()
        
        print(f"\n{'='*70}")
        print("Import Complete!")
        print(f"{'='*70}")
        
        print("\nImport Results:")
        for product_line, result in results.items():
            status = "[OK]" if result == "Success" else "[ERROR]"
            print(f"  {status} {product_line}: {result}")
        
    except Exception as e:
        print(f"\n[ERROR] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

