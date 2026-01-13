"""
Import Skybanking Certificate Fees from Excel to database
"""
import pandas as pd
import sys
import os
from datetime import datetime
from decimal import Decimal
from sqlalchemy import create_engine, Column, String, Date, Integer, DECIMAL, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
def get_database_url():
    """Get database URL from environment or use defaults"""
    url = os.getenv("POSTGRES_DB_URL")
    if url:
        return url
    
    user = os.getenv('POSTGRES_USER', 'chatbot_user')
    password = os.getenv('POSTGRES_PASSWORD', 'chatbot_password_123')
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    db = os.getenv('POSTGRES_DB', 'chatbot_db')
    
    from urllib.parse import quote_plus
    password_encoded = quote_plus(password) if password else ''
    
    return f"postgresql://{user}:{password_encoded}@{host}:{port}/{db}"

Base = declarative_base()

# Skybanking Fee Master Model
class SkybankingFeeMaster(Base):
    __tablename__ = "skybanking_fee_master"
    
    fee_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    charge_type = Column(String(100), nullable=False)
    network = Column(String(50), nullable=True)  # VISA, etc.
    product = Column(String(50), nullable=False)  # Skybanking
    product_name = Column(String(200), nullable=False)  # Service name
    fee_amount = Column(DECIMAL(15, 4), nullable=True)  # Can be NULL for "Variable" or "Free"
    fee_unit = Column(String(20), nullable=False)  # BDT, PERCENTAGE
    fee_basis = Column(String(50), nullable=False)  # YEARLY, PER REQUEST, PER TRANSACTION
    is_conditional = Column(Boolean, nullable=False, default=False)
    condition_description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="ACTIVE")
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

def parse_date(date_str):
    """Parse date string to date object"""
    if pd.isna(date_str):
        return None
    try:
        # Try different date formats
        if isinstance(date_str, str):
            # Handle "27/11/2025" format
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        return date_str
    except:
        return None

def parse_fee_amount(amount_str):
    """Parse fee amount - can be number, "Variable", "Free", or 0"""
    if pd.isna(amount_str):
        return None
    
    amount_str = str(amount_str).strip()
    
    if amount_str.lower() in ['variable', 'free', 'n/a', '']:
        return None
    
    try:
        return Decimal(str(amount_str))
    except:
        return None

def parse_fee_unit(unit_str):
    """Parse fee unit"""
    if pd.isna(unit_str):
        return "BDT"
    
    unit_str = str(unit_str).strip().upper()
    
    # Map variations
    if unit_str in ['BDT', 'TAKA', 'TK']:
        return "BDT"
    elif unit_str in ['PERCENTAGE', 'PERCENT', '%', 'PERCENTAGE']:
        return "PERCENTAGE"
    else:
        return unit_str

def parse_fee_basis(basis_str):
    """Parse fee basis"""
    if pd.isna(basis_str):
        return "PER_REQUEST"
    
    basis_str = str(basis_str).strip().upper()
    
    # Map variations
    if 'YEARLY' in basis_str or 'YEAR' in basis_str:
        return "PER_YEAR"
    elif 'TRANSACTION' in basis_str:
        return "PER_TRANSACTION"
    elif 'REQUEST' in basis_str:
        return "PER_REQUEST"
    else:
        return basis_str

def import_skybanking_fees(excel_path: str):
    """Import Skybanking fees from Excel file"""
    
    # Read Excel file
    logger.info(f"Reading Excel file: {excel_path}")
    df = pd.read_excel(excel_path, sheet_name='Skybanking_Fees')
    
    logger.info(f"Found {len(df)} rows in Excel file")
    
    # Connect to database
    database_url = get_database_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    
    # Create table if not exists
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        imported = 0
        updated = 0
        skipped = 0
        
        for idx, row in df.iterrows():
            try:
                # Parse data
                effective_from = parse_date(row.get('EFFECTIVE FROM'))
                effective_to = parse_date(row.get('EFFECTIVE TO'))
                charge_type = str(row.get('CHARGE TYPE', '')).strip()
                network = str(row.get(' NETWORK', '')).strip() if not pd.isna(row.get(' NETWORK')) else None
                # Handle column name with leading space: ' PRODUCT' vs 'PRODUCT'
                product = str(row.get(' PRODUCT', row.get('PRODUCT', ''))).strip()
                product_name = str(row.get('PRODUCT NAME', '')).strip()
                fee_amount = parse_fee_amount(row.get('FEE AMOUNT'))
                fee_unit = parse_fee_unit(row.get('FEE UNIT'))
                fee_basis = parse_fee_basis(row.get('FEE BASIS'))
                status = str(row.get('STATUS', 'ACTIVE')).strip().upper()
                is_conditional = str(row.get('CONDITIONAL', 'NO')).strip().upper() == 'YES'
                condition_description = str(row.get('CONDITION DESCRIPTION', '')).strip() if not pd.isna(row.get('CONDITION DESCRIPTION')) else None
                
                # Skip if required fields are missing
                if not charge_type or not product or not product_name:
                    logger.warning(f"Row {idx + 1}: Skipping - missing required fields")
                    skipped += 1
                    continue
                
                # Check if record already exists (by charge_type, product, product_name, effective_from)
                existing = session.query(SkybankingFeeMaster).filter(
                    SkybankingFeeMaster.charge_type == charge_type,
                    SkybankingFeeMaster.product == product,
                    SkybankingFeeMaster.product_name == product_name,
                    SkybankingFeeMaster.effective_from == effective_from
                ).first()
                
                if existing:
                    # Update existing record
                    existing.effective_to = effective_to
                    existing.network = network
                    existing.fee_amount = fee_amount
                    existing.fee_unit = fee_unit
                    existing.fee_basis = fee_basis
                    existing.is_conditional = is_conditional
                    existing.condition_description = condition_description
                    existing.status = status
                    existing.updated_at = func.now()
                    updated += 1
                    logger.debug(f"Updated: {product_name} - {charge_type}")
                else:
                    # Create new record
                    new_fee = SkybankingFeeMaster(
                        effective_from=effective_from,
                        effective_to=effective_to,
                        charge_type=charge_type,
                        network=network,
                        product=product,
                        product_name=product_name,
                        fee_amount=fee_amount,
                        fee_unit=fee_unit,
                        fee_basis=fee_basis,
                        is_conditional=is_conditional,
                        condition_description=condition_description,
                        status=status
                    )
                    session.add(new_fee)
                    imported += 1
                    logger.debug(f"Imported: {product_name} - {charge_type}")
                
            except Exception as e:
                logger.error(f"Row {idx + 1}: Error processing - {e}")
                skipped += 1
                continue
        
        session.commit()
        logger.info(f"Import complete: {imported} imported, {updated} updated, {skipped} skipped")
        
        return {
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "total": len(df)
        }
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error importing data: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    # Excel file path
    excel_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "xls",
        "Fees and Charges against issuing Certificates through EBL Skybanking in Schedule of Charges (SOC) (Effective from 27th November 2025.).xlsx"
    )
    
    if not os.path.exists(excel_file):
        logger.error(f"Excel file not found: {excel_file}")
        sys.exit(1)
    
    print("=" * 70)
    print("Importing Skybanking Certificate Fees")
    print("=" * 70)
    print(f"File: {excel_file}")
    print()
    
    try:
        result = import_skybanking_fees(excel_file)
        print()
        print("=" * 70)
        print("Import Summary")
        print("=" * 70)
        print(f"Total rows in Excel: {result['total']}")
        print(f"Imported: {result['imported']}")
        print(f"Updated: {result['updated']}")
        print(f"Skipped: {result['skipped']}")
        print("=" * 70)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

