# Quick Start: Import 4 Product Lines

## Prerequisites

1. PostgreSQL database is running and accessible
2. Database connection configured in environment variables or `.env` file
3. Excel files are in `E:\Chatbot_refine\xls\` directory

## Step 1: Set Up Environment Variables

Make sure your database connection is configured. The script uses the same environment variables as the fee engine service:

```bash
# Option 1: Use individual variables (in .env or environment)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=your_database_name
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password

# Option 2: Use connection URL
FEE_ENGINE_DB_URL=postgresql://user:password@localhost:5432/dbname
```

## Step 2: Run the Master Import Script

```bash
cd E:\Chatbot_refine\credit_card_rate\fee_engine
python import_all_product_lines.py
```

This script will:
1. ✅ Apply schema extension (adds `product_line` column if not exists)
2. ✅ Delete ALL existing data from `card_fee_master` table
3. ✅ Import all 4 product lines:
   - Credit Cards
   - Skybanking
   - Priority Banking
   - Retail Assets/Loans
4. ✅ Generate summary report

## Step 3: Verify Import

Check the summary report at the end of the import. You should see:
- Number of records imported per product line
- Total records count
- Status breakdown

## Step 4: Test in Chatbot

After successful import, you can test queries like:

**Credit Cards:**
- "VISA Platinum annual fee"
- "Mastercard Titanium ATM withdrawal fee"

**Skybanking:**
- "Skybanking annual service fee"
- "RTGS fund transfer fee"

**Priority Banking:**
- "Priority banking account maintenance fee"

**Retail Assets:**
- "Fast Cash processing fee"
- "Personal loan processing fee"

## Troubleshooting

### Error: Column 'product_line' does not exist
- The schema extension should run automatically
- If it fails, manually run: `psql -U user -d database -f schema_extension.sql`

### Error: Excel file not found
- Verify Excel files are in `E:\Chatbot_refine\xls\` directory
- Check file names match exactly (case-sensitive)

### Error: Database connection failed
- Verify PostgreSQL is running
- Check environment variables are set correctly
- Test connection: `psql -U user -d database -c "SELECT 1"`











