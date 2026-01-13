# Fix Failed Documents in LightRAG

## Issue

All 5 documents (EBL Annual Report 2024, Parts 1-5) have **Failed** status in LightRAG. This is why queries are returning errors - there's no processed data to search.

## Diagnosis

### Check Document Status

```bash
python fix_failed_documents.py
```

This will show:
- Which documents failed
- Error messages (if available)
- Recommended actions

### Check LightRAG Logs

```bash
docker logs LightRAG_New --tail 100
```

Look for error messages related to document processing.

## Common Causes

### 1. Document Too Large
Large PDFs (like annual reports) may exceed LightRAG's processing limits.

**Solution:**
- Upload as single document (not split into parts)
- Or use smaller chunks (10-20 pages each)

### 2. PDF Format Issues
- Encrypted PDFs
- Image-based PDFs (no text layer)
- Corrupted PDFs

**Solution:**
- Ensure PDF is not encrypted
- Use PDFs with text layer (not scanned images)
- Re-download from EBL website

### 3. Text Extraction Failed
PyPDF2 might fail on complex PDFs.

**Solution:**
- Try different PDF library (pdfplumber, pymupdf)
- Pre-process PDF to extract text
- Use OCR if needed

### 4. Processing Timeout
Large documents may timeout during processing.

**Solution:**
- Increase timeout in LightRAG configuration
- Upload smaller chunks
- Process during off-peak hours

## Solutions

### Solution 1: Delete and Re-upload (Recommended)

**Step 1: Delete Failed Documents**

In LightRAG web interface:
1. Select all failed documents
2. Click "Delete" or use API

Or use script:
```python
from fix_failed_documents import delete_document

# Delete failed documents
doc_ids = ["doc-a9c5b6b5f73544eb6567c4d2aff3aae3", ...]
for doc_id in doc_ids:
    delete_document(doc_id)
```

**Step 2: Re-upload as Single Document**

```bash
# Upload entire annual report as one document (not split)
python download_and_upload_financial_reports.py --years 2024 --knowledge-base ebl_financial_reports
```

**Step 3: Trigger Scan**

In LightRAG web interface:
- Click "Scan" button

Or use API:
```python
from fix_failed_documents import trigger_scan
trigger_scan()
```

### Solution 2: Upload Smaller Chunks

If the full report is too large, split it:

```python
# Split PDF into smaller chunks (e.g., 20 pages each)
# Then upload each chunk separately
```

### Solution 3: Use Different PDF Library

Update `download_and_upload_financial_reports.py` to use a different PDF library:

```python
# Instead of PyPDF2, use pdfplumber or pymupdf
pip install pdfplumber  # or pymupdf

# Update extract_text_from_pdf() function
```

### Solution 4: Pre-process PDF

Extract text from PDF first, then upload text:

```bash
# Extract text from PDF
pdftotext EBL-ANNUAL-REPORT-2024.pdf output.txt

# Upload text file
python upload_to_knowledge_base.py output.txt --knowledge-base ebl_financial_reports
```

## Quick Fix Steps

1. **Delete failed documents** (via web UI or API)
2. **Re-upload annual report** as single document:
   ```bash
   python download_and_upload_financial_reports.py --years 2024
   ```
3. **Trigger scan** in LightRAG web UI
4. **Wait for processing** (check status)
5. **Test query**:
   ```
   "What was the bank's revenue in 2024?"
   ```

## Verification

After re-uploading:

1. Check document status in LightRAG web UI
2. Should show "Completed" or "Processing" (not "Failed")
3. "Chunks" column should show numbers (not empty)
4. Test query should work

## Alternative: Use Existing Knowledge Base

If financial reports keep failing, you can:

1. **Use default knowledge base** temporarily:
   ```python
   # In chatbot, route financial queries to default
   knowledge_base = "default"  # or "ebl_website"
   ```

2. **Upload to ebl_website** knowledge base:
   ```bash
   python download_and_upload_financial_reports.py --knowledge-base ebl_website
   ```

## Next Steps

1. ✅ Run diagnostic: `python fix_failed_documents.py`
2. ✅ Check LightRAG logs: `docker logs LightRAG_New`
3. ✅ Delete failed documents
4. ✅ Re-upload annual report (as single document)
5. ✅ Trigger scan and wait for processing
6. ✅ Test query again

## Summary

The documents failed processing, which is why queries return errors. The solution is to:
- Delete failed documents
- Re-upload the annual report (preferably as single document)
- Ensure proper processing
- Then queries will work

