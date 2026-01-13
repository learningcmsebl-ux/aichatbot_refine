"""
Script to read and analyze Skybanking Certificate Fees Excel file
"""
import pandas as pd
import sys
import os

# File path
excel_file = r"xls\Fees and Charges against issuing Certificates through EBL Skybanking in Schedule of Charges (SOC) (Effective from 27th November 2025.).xlsx"

try:
    # Read the Excel file
    print("=" * 70)
    print("Reading Skybanking Certificate Fees Excel File")
    print("=" * 70)
    print(f"File: {excel_file}")
    print()
    
    # Read all sheets
    excel_data = pd.ExcelFile(excel_file)
    print(f"Sheet names: {excel_data.sheet_names}")
    print()
    
    # Read each sheet
    for sheet_name in excel_data.sheet_names:
        print(f"\n{'='*70}")
        print(f"Sheet: {sheet_name}")
        print(f"{'='*70}")
        
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        
        print(f"Shape: {df.shape} (rows x columns)")
        print(f"Columns: {list(df.columns)}")
        print()
        print("First few rows:")
        print(df.head(10).to_string())
        print()
        print("Data types:")
        print(df.dtypes)
        print()
        
        # Check for null values
        print("Null values per column:")
        print(df.isnull().sum())
        print()
        
except FileNotFoundError:
    print(f"Error: File not found: {excel_file}")
    sys.exit(1)
except Exception as e:
    print(f"Error reading Excel file: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)








