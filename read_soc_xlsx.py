import pandas as pd
import sys

# Set UTF-8 encoding for output
sys.stdout.reconfigure(encoding='utf-8')

# Read the Excel file
file_path = r'E:\Chatbot_refine\xls\soc.xlsx'
df = pd.read_excel(file_path)

print(f"File: soc.xlsx")
print(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns")
print(f"\nColumns ({len(df.columns)}):")
for i, col in enumerate(df.columns):
    print(f"  {i}: {repr(col)}")

print(f"\n\nFirst 30 rows:")
print("=" * 100)
print(df.head(30).to_string())

if len(df) > 30:
    print(f"\n... (showing first 30 of {len(df)} rows)")

print(f"\n\nData types:")
print(df.dtypes)

print(f"\n\nNon-null counts:")
print(df.count())
