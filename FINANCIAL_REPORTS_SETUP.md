# EBL Financial Reports Setup Guide

## Overview

This guide shows you how to download and upload EBL financial reports from [https://www.ebl.com.bd/financial-reports](https://www.ebl.com.bd/financial-reports) to your LightRAG knowledge base so the chatbot can answer questions about financial data.

## Available Reports

According to the [EBL Financial Reports page](https://www.ebl.com.bd/financial-reports), the following reports are available:

### Annual Reports (2007-2024)
- Annual Report 2024
- Annual Report 2023
- Annual Report 2022
- ... and more going back to 2007

### Quarterly/Half-yearly Reports
- Q1, Q3, and Half-yearly reports for 2025, 2024, 2023, etc.

### Financial Highlights
- Summary financial data

### Disclosures
- Risk Based Capital (BASEL III) disclosures

## Setup Steps

### Step 1: Install Dependencies

```bash
pip install PyPDF2 requests
```

### Step 2: Download and Upload Reports

#### Option A: Upload All Annual Reports (Recommended)

```bash
# Download and upload all annual reports (2007-2024)
python download_and_upload_financial_reports.py --knowledge-base ebl_financial_reports
```

#### Option B: Upload Specific Years

```bash
# Upload only recent years (2024, 2023, 2022)
python download_and_upload_financial_reports.py --years 2024 2023 2022 --knowledge-base ebl_financial_reports
```

#### Option C: Download Only (No Upload)

```bash
# Download PDFs without uploading to LightRAG
python download_and_upload_financial_reports.py --no-upload --keep-files
```

### Step 3: Trigger Indexing in LightRAG

After uploading, you need to trigger indexing in LightRAG. Check your LightRAG API documentation for the indexing endpoint.

## How It Works

### 1. Download Process
- Downloads PDF files from EBL website
- Saves to `financial_reports/` directory (temporary)

### 2. Text Extraction
- Extracts text from PDF files using PyPDF2
- Processes all pages in each report

### 3. Upload to LightRAG
- Uploads extracted text to `ebl_financial_reports` knowledge base
- Each report is uploaded as a separate document

### 4. Smart Routing
- Chatbot automatically detects financial queries
- Routes to `ebl_financial_reports` knowledge base
- Answers questions using the uploaded reports

## Example Queries

Once the reports are uploaded, users can ask:

1. **"What was the bank's revenue in 2024?"**
   - Routes to: `ebl_financial_reports`
   - Searches: Annual Report 2024

2. **"Show me the quarterly results for 2024"**
   - Routes to: `ebl_financial_reports`
   - Searches: Q1, Q3, H1 reports for 2024

3. **"What was the profit in 2023?"**
   - Routes to: `ebl_financial_reports`
   - Searches: Annual Report 2023

4. **"Compare revenue between 2023 and 2024"**
   - Routes to: `ebl_financial_reports`
   - Searches: Both Annual Reports

## Script Options

```bash
python download_and_upload_financial_reports.py [OPTIONS]

Options:
  --years YEARS          Specific years to download (e.g., 2024 2023)
  --knowledge-base KB    Knowledge base name (default: ebl_financial_reports)
  --download-dir DIR     Download directory (default: financial_reports)
  --base-url URL         LightRAG API URL (default: http://localhost:9262)
  --api-key KEY          LightRAG API key (default: MyCustomLightRagKey456)
  --no-upload            Only download, don't upload
  --keep-files           Keep downloaded PDFs after upload
```

## Example Usage

### Upload Most Recent Reports

```bash
# Upload 2024, 2023, 2022 annual reports
python download_and_upload_financial_reports.py --years 2024 2023 2022
```

### Upload All Reports

```bash
# Upload all available annual reports (2007-2024)
python download_and_upload_financial_reports.py
```

### Test Download First

```bash
# Download without uploading to test
python download_and_upload_financial_reports.py --no-upload --keep-files
```

## Verification

After uploading, test with:

```python
from connect_lightrag import LightRAGClient

client = LightRAGClient()
result = client.query(
    query="What was the bank's revenue in 2024?",
    knowledge_base="ebl_financial_reports"
)
print(result)
```

## Troubleshooting

### 1. PyPDF2 Not Installed
```bash
pip install PyPDF2
```

### 2. Download Fails
- Check internet connection
- Verify URLs are accessible
- Some PDFs might have different URLs (check EBL website)

### 3. Text Extraction Fails
- PDF might be image-based (OCR needed)
- Try a different PDF library (pdfplumber, pymupdf)

### 4. Upload Fails
- Check LightRAG is running
- Verify API key is correct
- Check LightRAG API endpoint

## Notes

- **Large Files**: Annual reports can be large (10-50 MB PDFs)
- **Processing Time**: Text extraction takes time for large PDFs
- **Storage**: LightRAG stores extracted text, not PDFs
- **Updates**: Re-run script when new reports are published

## Next Steps

1. ✅ Run the download/upload script
2. ✅ Trigger indexing in LightRAG
3. ✅ Test queries about financial data
4. ✅ Verify chatbot routes to correct knowledge base

## Summary

✅ **Download script created** - Downloads reports from EBL website
✅ **Upload to LightRAG** - Uploads to `ebl_financial_reports` knowledge base
✅ **Smart routing** - Chatbot automatically routes financial queries
✅ **Ready to use** - After setup, chatbot can answer financial questions

Your chatbot will be able to answer questions like "What was the bank's revenue in 2024?" once the reports are uploaded!

