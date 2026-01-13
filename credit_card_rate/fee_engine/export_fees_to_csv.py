"""Export card_fee_master table data to CSV"""
import csv
from datetime import datetime
from pathlib import Path
from fee_engine_service import SessionLocal, CardFeeMaster

def export_fees_to_csv():
    """Export all fee records to CSV"""
    db = SessionLocal()
    
    try:
        # Query all records
        records = db.query(CardFeeMaster).order_by(
            CardFeeMaster.charge_type,
            CardFeeMaster.card_category,
            CardFeeMaster.card_network,
            CardFeeMaster.card_product
        ).all()
        
        # Define CSV columns
        fieldnames = [
            'fee_id',
            'effective_from',
            'effective_to',
            'charge_type',
            'card_category',
            'card_network',
            'card_product',
            'full_card_name',
            'fee_value',
            'fee_unit',
            'fee_basis',
            'min_fee_value',
            'min_fee_unit',
            'max_fee_value',
            'free_entitlement_count',
            'condition_type',
            'note_reference',
            'priority',
            'status',
            'product_line',
            'remarks',
            'created_at',
            'updated_at'
        ]
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"card_fee_master_export_{timestamp}.csv"
        csv_path = Path(__file__).parent / csv_filename
        
        # Write to CSV
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for record in records:
                row = {
                    'fee_id': str(record.fee_id),
                    'effective_from': record.effective_from.isoformat() if record.effective_from else '',
                    'effective_to': record.effective_to.isoformat() if record.effective_to else '',
                    'charge_type': record.charge_type or '',
                    'card_category': record.card_category or '',
                    'card_network': record.card_network or '',
                    'card_product': record.card_product or '',
                    'full_card_name': record.full_card_name or '',
                    'fee_value': str(record.fee_value) if record.fee_value is not None else '',
                    'fee_unit': record.fee_unit or '',
                    'fee_basis': record.fee_basis or '',
                    'min_fee_value': str(record.min_fee_value) if record.min_fee_value is not None else '',
                    'min_fee_unit': record.min_fee_unit or '',
                    'max_fee_value': str(record.max_fee_value) if record.max_fee_value is not None else '',
                    'free_entitlement_count': str(record.free_entitlement_count) if record.free_entitlement_count is not None else '',
                    'condition_type': record.condition_type or '',
                    'note_reference': record.note_reference or '',
                    'priority': record.priority or '',
                    'status': record.status or '',
                    'product_line': record.product_line or '',
                    'remarks': record.remarks or '',
                    'created_at': record.created_at.isoformat() if record.created_at else '',
                    'updated_at': record.updated_at.isoformat() if record.updated_at else ''
                }
                writer.writerow(row)
        
        print(f"Exported {len(records)} records to {csv_path}")
        print(f"CSV file location: {csv_path.absolute()}")
        return csv_path
        
    except Exception as e:
        print(f"Error exporting data: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    export_fees_to_csv()










