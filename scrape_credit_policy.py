"""
Scrape EBL Credit Policy Manual PDF and format it for LightRAG ingestion
"""

import os
from pathlib import Path
from typing import Dict
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_text_pypdf2(pdf_path: str) -> str:
    """Extract text using PyPDF2"""
    try:
        import PyPDF2
        text = ""
        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            total_pages = len(pdf_reader.pages)
            logger.info(f"Extracting text from {total_pages} pages using PyPDF2...")
            
            for i, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                text += f"\n--- Page {i+1} ---\n{page_text}\n"
                if (i + 1) % 10 == 0:
                    logger.info(f"  Processed {i + 1}/{total_pages} pages...")
        
        return text
    except ImportError:
        logger.warning("PyPDF2 not available, trying alternative...")
        return ""
    except Exception as e:
        logger.error(f"PyPDF2 extraction failed: {e}")
        return ""


def extract_text_pdfplumber(pdf_path: str) -> str:
    """Extract text using pdfplumber (better for complex PDFs)"""
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"Extracting text from {total_pages} pages using pdfplumber...")
            
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += f"\n--- Page {i+1} ---\n{page_text}\n"
                if (i + 1) % 10 == 0:
                    logger.info(f"  Processed {i + 1}/{total_pages} pages...")
        
        return text
    except ImportError:
        logger.warning("pdfplumber not available")
        return ""
    except Exception as e:
        logger.error(f"pdfplumber extraction failed: {e}")
        return ""


def extract_text_pymupdf(pdf_path: str) -> str:
    """Extract text using PyMuPDF (fitz) - fastest and most reliable"""
    try:
        import fitz  # PyMuPDF
        text = ""
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        logger.info(f"Extracting text from {total_pages} pages using PyMuPDF...")
        
        for i, page in enumerate(doc):
            page_text = page.get_text()
            if page_text:
                text += f"\n--- Page {i+1} ---\n{page_text}\n"
            if (i + 1) % 10 == 0:
                logger.info(f"  Processed {i + 1}/{total_pages} pages...")
        
        doc.close()
        return text
    except ImportError:
        logger.warning("PyMuPDF (fitz) not available")
        return ""
    except Exception as e:
        logger.error(f"PyMuPDF extraction failed: {e}")
        return ""


def extract_text_from_pdf(pdf_path: str) -> Dict[str, any]:
    """Extract text from PDF using best available method"""
    pdf_name = os.path.basename(pdf_path)
    logger.info(f"\n{'='*70}")
    logger.info(f"Processing: {pdf_name}")
    logger.info(f"{'='*70}")
    
    # Try multiple methods in order of preference
    text = ""
    method_used = ""
    
    # Try PyMuPDF first (most reliable)
    text = extract_text_pymupdf(pdf_path)
    if text.strip():
        method_used = "PyMuPDF"
    else:
        # Try pdfplumber
        text = extract_text_pdfplumber(pdf_path)
        if text.strip():
            method_used = "pdfplumber"
        else:
            # Try PyPDF2
            text = extract_text_pypdf2(pdf_path)
            if text.strip():
                method_used = "PyPDF2"
    
    if not text.strip():
        logger.error(f"Failed to extract text from {pdf_name} with any method")
        return {
            "file": pdf_name,
            "success": False,
            "text": "",
            "method": "none",
            "length": 0
        }
    
    # Clean up text
    text = text.strip()
    
    logger.info(f"✓ Successfully extracted {len(text):,} characters using {method_used}")
    logger.info(f"  Text preview (first 200 chars): {text[:200]}...")
    
    return {
        "file": pdf_name,
        "success": True,
        "text": text,
        "method": method_used,
        "length": len(text)
    }


def main():
    """Main function to scrape the Credit Policy Manual PDF"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Scrape EBL Credit Policy Manual PDF for LightRAG"
    )
    parser.add_argument(
        "--pdf-path",
        type=str,
        help="Path to the PDF file (if not provided, will search in source_pdf)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="scraped_text",
        help="Output directory for scraped text (default: scraped_text)"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("EBL Credit Policy Manual Scraper")
    print("=" * 70)
    print()
    
    # PDF filename
    pdf_filename = "4-Credit-Policy-Manual-Jan-2009.pdf"
    
    # Find the PDF file
    if args.pdf_path:
        pdf_path = args.pdf_path
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found at provided path: {pdf_path}")
            return
        logger.info(f"Using provided PDF path: {pdf_path}")
    else:
        # Check in source_pdf directory
        pdf_path = os.path.join("source_pdf", pdf_filename)
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            logger.info("\nPlease ensure the PDF file is in source_pdf/ directory")
            logger.info(f"Or provide the path using: --pdf-path <path_to_pdf>")
            return
        logger.info(f"Found PDF: {pdf_path}")
    
    # Extract text from PDF
    result = extract_text_from_pdf(pdf_path)
    
    if not result["success"]:
        logger.error(f"Failed to extract text from PDF")
        return
    
    # Create output folder
    output_dir = args.output_dir
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    logger.info(f"Created/verified output directory: {output_dir}")
    
    # Generate output filename
    output_filename = "4-Credit-Policy-Manual-Jan-2009.txt"
    output_file = output_path / output_filename
    
    # Save to text file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(result["text"])
    
    logger.info(f"✓ Saved to: {output_file}")
    
    # Show preview
    print("\n" + "="*70)
    print(f"PREVIEW: {result['file']}")
    print("="*70)
    preview = result["text"][:1000]
    print(preview)
    if len(result["text"]) > 1000:
        print(f"\n... ({len(result['text']) - 1000:,} more characters)")
    print("="*70 + "\n")
    
    # Summary
    print("\n" + "="*70)
    print("SCRAPING SUMMARY")
    print("="*70)
    print(f"✓ PDF File: {pdf_path}")
    print(f"✓ Extraction Method: {result['method']}")
    print(f"✓ Text Length: {result['length']:,} characters")
    print(f"✓ Output File: {output_file}")
    print("\n" + "="*70)
    print("Next Steps:")
    print("="*70)
    print(f"1. Review the extracted text file in '{output_dir}/' directory")
    print("2. Upload to LightRAG using:")
    print(f"   python upload_to_knowledge_base.py {output_file} --knowledge-base ebl_financial_reports")
    print("   (or use appropriate knowledge base like 'ebl_website' or 'ebl_user_documents')")
    print("="*70)


if __name__ == "__main__":
    main()








