"""
Scrape PDFs from source_pdf directory in LightRAG-friendly format
Extracts text and prepares it for upload to LightRAG
"""

import os
from pathlib import Path
from typing import List, Dict
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


def scrape_pdfs_from_directory(
    source_dir: str = "source_pdf",
    output_dir: str = "scraped_text",
    show_preview: bool = True,
    max_preview_length: int = 1000
) -> List[Dict]:
    """Scrape all PDFs from source directory"""
    
    source_path = Path(source_dir)
    if not source_path.exists():
        logger.error(f"Source directory not found: {source_dir}")
        return []
    
    # Find all PDFs
    pdf_files = list(source_path.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files found in {source_dir}")
        return []
    
    logger.info(f"Found {len(pdf_files)} PDF file(s) in {source_dir}")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    results = []
    
    for pdf_file in pdf_files:
        logger.info(f"\nProcessing: {pdf_file.name}")
        
        # Extract text
        result = extract_text_from_pdf(str(pdf_file))
        results.append(result)
        
        if result["success"]:
            # Save to text file
            output_file = output_path / f"{pdf_file.stem}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result["text"])
            logger.info(f"✓ Saved to: {output_file}")
            
            # Show preview
            if show_preview:
                print("\n" + "="*70)
                print(f"PREVIEW: {result['file']}")
                print("="*70)
                preview = result["text"][:max_preview_length]
                print(preview)
                if len(result["text"]) > max_preview_length:
                    print(f"\n... ({len(result['text']) - max_preview_length:,} more characters)")
                print("="*70 + "\n")
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
            print(f"    Saved to: {output_dir}/{Path(r['file']).stem}.txt")
    
    if failed:
        print("\nFailed Extractions:")
        for r in failed:
            print(f"  ✗ {r['file']}")
    
    print("\n" + "="*70)
    print("Next Steps:")
    print("="*70)
    print("1. Review the extracted text files in 'scraped_text/' directory")
    print("2. Upload to LightRAG using:")
    print("   python upload_to_knowledge_base.py scraped_text/ --knowledge-base ebl_financial_reports")
    print("3. Or upload individual files:")
    for r in successful:
        print(f"   python upload_to_knowledge_base.py scraped_text/{Path(r['file']).stem}.txt --knowledge-base ebl_financial_reports")
    
    return results


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape PDFs for LightRAG")
    parser.add_argument(
        "--source-dir",
        default="source_pdf",
        help="Source directory containing PDFs (default: source_pdf)"
    )
    parser.add_argument(
        "--output-dir",
        default="scraped_text",
        help="Output directory for extracted text (default: scraped_text)"
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Don't show text preview"
    )
    parser.add_argument(
        "--preview-length",
        type=int,
        default=1000,
        help="Preview length in characters (default: 1000)"
    )
    
    args = parser.parse_args()
    
    scrape_pdfs_from_directory(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        show_preview=not args.no_preview,
        max_preview_length=args.preview_length
    )


if __name__ == "__main__":
    main()

