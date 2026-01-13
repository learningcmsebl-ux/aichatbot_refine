"""
Download and upload EBL financial reports to LightRAG knowledge base
Downloads reports from https://www.ebl.com.bd/financial-reports
"""

import requests
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
import logging
from connect_lightrag import LightRAGClient
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# EBL Financial Reports URLs
EBL_FINANCIAL_REPORTS_BASE = "https://www.ebl.com.bd"

# Annual Reports (2007-2024)
ANNUAL_REPORTS = {
    2024: "https://www.ebl.com.bd/./assets/reports/annual/EBL-ANNUAL-REPORT-2024.pdf",
    2023: "https://www.ebl.com.bd/./assets/reports/annual/EBL-ANNUAL-REPORT-2023.pdf",
    2022: "https://www.ebl.com.bd/./assets/reports/annual/EBL-ANNUAL-REPORT-2022.pdf",
    2021: "https://www.ebl.com.bd/./assets/reports/annual/EBL-Annual-Report-2021.pdf",
    2020: "https://www.ebl.com.bd/./assets/reports/annual/ANNUAL-REPORT-2020.pdf",
    2019: "https://www.ebl.com.bd/./assets/reports/annual/Annual-Report-2019.pdf",
    2018: "https://www.ebl.com.bd/./assets/reports/annual/EBL%5FAnnual%5FReport%5F2018.pdf",
    2017: "https://www.ebl.com.bd/./assets/reports/annual/EBL%5FAnnual%5FReport%5F2017.pdf",
    2016: "https://www.ebl.com.bd/./assets/reports/annual/EBL%5FAR%5F2016.pdf",
    2015: "https://www.ebl.com.bd/./assets/reports/annual/EBL AR 2015.pdf",
    2014: "https://www.ebl.com.bd/./assets/reports/annual/EBL Annual Report 2014.pdf",
    2013: "https://www.ebl.com.bd/./assets/reports/annual/EBL Annual Report 2013.pdf",
    2012: "https://www.ebl.com.bd/./assets/reports/annual/Annual%5FReport%5F2012.pdf",
    2011: "https://www.ebl.com.bd/./assets/reports/annual/Annual Report 2011.pdf",
    2010: "https://www.ebl.com.bd/./assets/reports/annual/Annual Report 2010.pdf",
    2009: "https://www.ebl.com.bd/./assets/reports/annual/Annual Report 2009.pdf",
    2008: "https://www.ebl.com.bd/./assets/reports/annual/Annual Report 2008.pdf",
    2007: "https://www.ebl.com.bd/./assets/reports/annual/EBL%5FAnnual%5FReport%5F2007.pdf",
}

# Quarterly Reports (you can add more as needed)
QUARTERLY_REPORTS = {
    # 2025
    "2025_Q3": "https://www.ebl.com.bd/./assets/reports/quarterly/EBL-Q3-Financial-Statement-2025.pdf",
    "2025_H1": "https://www.ebl.com.bd/./assets/reports/quarterly/Half-Yearly-Financial-Statements-2025.pdf",
    "2025_Q1": "https://www.ebl.com.bd/./assets/reports/quarterly/EBL-Q1-Financial-Statement-2025.pdf",
    # 2024
    "2024_Audited": "https://www.ebl.com.bd/./assets/reports/quarterly/Financial-Statements-2024.pdf",
    "2024_Q3": "https://www.ebl.com.bd/./assets/reports/quarterly/EBL-Q3-Financial-Statements-2024.pdf",
    "2024_H1": "https://www.ebl.com.bd/./assets/reports/quarterly/Half-Yearly-Financial-Statements-2024.pdf",
    "2024_Q1": "https://www.ebl.com.bd/./assets/reports/quarterly/EBL-Q1-Financial-Statements-2024.pdf",
}


def download_pdf(url: str, output_path: str) -> bool:
    """Download a PDF file from URL"""
    try:
        logger.info(f"Downloading: {url}")
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save file
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        logger.info(f"✓ Downloaded: {os.path.basename(output_path)} ({file_size:.2f} MB)")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to download {url}: {e}")
        return False


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF file"""
    try:
        import PyPDF2
        text = ""
        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            total_pages = len(pdf_reader.pages)
            logger.info(f"Extracting text from {total_pages} pages...")
            
            for i, page in enumerate(pdf_reader.pages):
                text += page.extract_text() + "\n"
                if (i + 1) % 10 == 0:
                    logger.info(f"  Processed {i + 1}/{total_pages} pages...")
        
        logger.info(f"✓ Extracted {len(text)} characters from PDF")
        return text
    except ImportError:
        logger.error("PyPDF2 not installed. Install with: pip install PyPDF2")
        return ""
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return ""


def upload_to_lightrag(text: str, file_name: str, knowledge_base: str, client: LightRAGClient) -> bool:
    """Upload text to LightRAG knowledge base"""
    try:
        # Note: LightRAG API might need knowledge_base parameter
        # Check your LightRAG API documentation for exact parameter name
        result = client.insert_text(
            text=text,
            file_source=file_name
        )
        logger.info(f"✓ Uploaded to LightRAG: {file_name}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to upload {file_name}: {e}")
        return False


def process_financial_reports(
    years: Optional[List[int]] = None,
    download_dir: str = "financial_reports",
    knowledge_base: str = "ebl_financial_reports",
    base_url: str = "cdhttp://localhost:9262",
    api_key: str = "MyCustomLightRagKey456",
    upload: bool = True,
    keep_files: bool = False
):
    """
    Download and upload EBL financial reports to LightRAG
    
    Args:
        years: List of years to download (default: all available)
        download_dir: Directory to save downloaded PDFs
        knowledge_base: LightRAG knowledge base name
        base_url: LightRAG API base URL
        api_key: LightRAG API key
        upload: Whether to upload to LightRAG (default: True)
        keep_files: Whether to keep downloaded PDFs (default: False)
    """
    # Initialize LightRAG client
    if upload:
        client = LightRAGClient(base_url=base_url, api_key=api_key)
        health = client.health_check()
        if health.get("status") != "ok":
            logger.error(f"LightRAG health check failed: {health}")
            return
    
    # Determine which years to process
    if years is None:
        years = sorted(ANNUAL_REPORTS.keys(), reverse=True)  # Most recent first
    
    logger.info(f"Processing financial reports for years: {years}")
    logger.info(f"Knowledge base: {knowledge_base}")
    logger.info(f"Download directory: {download_dir}")
    logger.info("-" * 70)
    
    download_dir_path = Path(download_dir)
    download_dir_path.mkdir(exist_ok=True)
    
    success_count = 0
    failed_count = 0
    
    # Process annual reports
    for year in years:
        if year not in ANNUAL_REPORTS:
            logger.warning(f"Annual report not available for year {year}")
            continue
        
        url = ANNUAL_REPORTS[year]
        file_name = f"EBL_Annual_Report_{year}.pdf"
        pdf_path = download_dir_path / file_name
        
        # Download PDF
        if not download_pdf(url, str(pdf_path)):
            failed_count += 1
            continue
        
        # Extract text from PDF
        text = extract_text_from_pdf(str(pdf_path))
        if not text.strip():
            logger.warning(f"Empty text extracted from {file_name}")
            failed_count += 1
            if not keep_files:
                pdf_path.unlink()
            continue
        
        # Upload to LightRAG
        if upload:
            if upload_to_lightrag(text, file_name, knowledge_base, client):
                success_count += 1
            else:
                failed_count += 1
        else:
            logger.info(f"Upload skipped for {file_name}")
            success_count += 1
        
        # Clean up downloaded file if not keeping
        if not keep_files:
            pdf_path.unlink()
        
        # Small delay to avoid overwhelming the server
        time.sleep(1)
    
    logger.info("-" * 70)
    logger.info(f"Processing complete:")
    logger.info(f"  ✓ Successfully processed: {success_count} reports")
    logger.info(f"  ✗ Failed: {failed_count} reports")
    logger.info(f"  Knowledge base: {knowledge_base}")
    
    if upload:
        logger.info("\nNext step: Trigger indexing in LightRAG for the knowledge base")
        logger.info(f"Knowledge base '{knowledge_base}' is ready to use!")


def main():
    """Command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download and upload EBL financial reports to LightRAG"
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        help="Specific years to download (e.g., --years 2024 2023). Default: all available"
    )
    parser.add_argument(
        "--knowledge-base",
        "-kb",
        default="ebl_financial_reports",
        help="LightRAG knowledge base name (default: ebl_financial_reports)"
    )
    parser.add_argument(
        "--download-dir",
        default="financial_reports",
        help="Directory to save downloaded PDFs (default: financial_reports)"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:9262",
        help="LightRAG API base URL (default: http://localhost:9262)"
    )
    parser.add_argument(
        "--api-key",
        default="MyCustomLightRagKey456",
        help="LightRAG API key"
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Only download, don't upload to LightRAG"
    )
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Keep downloaded PDF files (default: delete after upload)"
    )
    
    args = parser.parse_args()
    
    process_financial_reports(
        years=args.years,
        download_dir=args.download_dir,
        knowledge_base=args.knowledge_base,
        base_url=args.base_url,
        api_key=args.api_key,
        upload=not args.no_upload,
        keep_files=args.keep_files
    )


if __name__ == "__main__":
    main()

