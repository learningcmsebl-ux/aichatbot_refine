"""
Scrape CODE of conduct.pdf and GAP Book.pdf from source_pdf directory
Extracts text in LightRAG-friendly format and saves to scraped_text directory
"""

import os
import sys
from pathlib import Path
import logging

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
                if page_text:
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


def extract_text_from_pdf(pdf_path: str) -> dict:
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
    
    # Clean up text - remove excessive whitespace but keep structure
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        cleaned_line = line.strip()
        if cleaned_line:  # Keep non-empty lines
            cleaned_lines.append(cleaned_line)
        elif cleaned_lines and cleaned_lines[-1]:  # Keep single blank line between paragraphs
            cleaned_lines.append("")
    
    text = '\n'.join(cleaned_lines).strip()
    
    logger.info(f"✓ Successfully extracted {len(text):,} characters using {method_used}")
    logger.info(f"  Text preview (first 300 chars): {text[:300]}...")
    
    return {
        "file": pdf_name,
        "success": True,
        "text": text,
        "method": method_used,
        "length": len(text)
    }


def scrape_specific_pdfs(
    pdf_names: list,
    source_dir: str = "source_pdf",
    output_dir: str = "scraped_text"
) -> list:
    """Scrape specific PDFs from source directory"""
    
    source_path = Path(source_dir)
    if not source_path.exists():
        logger.error(f"Source directory not found: {source_dir}")
        return []
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    logger.info(f"Output directory: {output_path.absolute()}")
    
    results = []
    
    for pdf_name in pdf_names:
        pdf_file = source_path / pdf_name
        
        if not pdf_file.exists():
            logger.warning(f"PDF file not found: {pdf_file}")
            results.append({
                "file": pdf_name,
                "success": False,
                "text": "",
                "method": "none",
                "length": 0,
                "error": "File not found"
            })
            continue
        
        logger.info(f"\nProcessing: {pdf_file.name}")
        
        # Extract text
        result = extract_text_from_pdf(str(pdf_file))
        results.append(result)
        
        if result["success"]:
            # Save to text file - use clean filename
            safe_name = pdf_file.stem.replace(" ", "_").replace(".", "_")
            output_file = output_path / f"{safe_name}.txt"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result["text"])
            
            logger.info(f"✓ Saved to: {output_file.absolute()}")
            logger.info(f"  File size: {output_file.stat().st_size:,} bytes")
        else:
            logger.error(f"✗ Failed to extract text from {pdf_file.name}")
    
    # Summary
    print("\n" + "="*70)
    print("SCRAPING SUMMARY")
    print("="*70)
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    print(f"\nTotal PDFs: {len(results)}")
    print(f"✓ Successful: {len(successful)}")
    print(f"✗ Failed: {len(failed)}")
    
    if successful:
        print("\nSuccessful Extractions:")
        for r in successful:
            print(f"  ✓ {r['file']}")
            print(f"    Method: {r['method']}")
            print(f"    Length: {r['length']:,} characters")
            safe_name = Path(r['file']).stem.replace(" ", "_").replace(".", "_")
            print(f"    Saved to: {output_dir}/{safe_name}.txt")
    
    if failed:
        print("\nFailed Extractions:")
        for r in failed:
            print(f"  ✗ {r['file']}")
            if 'error' in r:
                print(f"    Error: {r['error']}")
    
    print("\n" + "="*70)
    print("Files are ready for LightRAG ingestion!")
    print("="*70)
    
    return results


def main():
    """Main function"""
    # Target PDFs
    target_pdfs = [
        "CODE of conduct.pdf",
        "GAP Book.pdf"
    ]
    
    source_dir = r"E:\Chatbot_refine\source_pdf"
    output_dir = r"E:\Chatbot_refine\scraped_text"
    
    logger.info("Starting PDF scraping for LightRAG...")
    logger.info(f"Source directory: {source_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Target PDFs: {', '.join(target_pdfs)}")
    
    results = scrape_specific_pdfs(
        pdf_names=target_pdfs,
        source_dir=source_dir,
        output_dir=output_dir
    )
    
    return results


if __name__ == "__main__":
    main()

