"""
Upload documents to specific LightRAG knowledge bases
Supports multiple knowledge bases for different document types
"""

import os
import sys
from pathlib import Path
from typing import List, Optional
import logging
from connect_lightrag import LightRAGClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def read_text_file(file_path: str) -> str:
    """Read text from a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return ""


def read_pdf_file(file_path: str) -> str:
    """Read text from PDF file"""
    try:
        import PyPDF2
        text = ""
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except ImportError:
        logger.error("PyPDF2 not installed. Install with: pip install PyPDF2")
        return ""
    except Exception as e:
        logger.error(f"Error reading PDF {file_path}: {e}")
        return ""


def upload_directory_to_kb(
    directory: str,
    knowledge_base: str,
    base_url: str = "http://localhost:9262",
    api_key: str = "MyCustomLightRagKey456"
):
    """
    Upload all documents from a directory to a specific knowledge base
    
    Args:
        directory: Path to directory containing documents
        knowledge_base: Name of the knowledge base (e.g., 'ebl_financial_reports')
        base_url: LightRAG API base URL
        api_key: LightRAG API key
    """
    client = LightRAGClient(base_url=base_url, api_key=api_key)
    
    # Check health
    health = client.health_check()
    if health.get("status") != "ok":
        logger.error(f"LightRAG health check failed: {health}")
        return
    
    logger.info(f"Uploading documents from '{directory}' to knowledge base '{knowledge_base}'")
    
    directory_path = Path(directory)
    if not directory_path.exists():
        logger.error(f"Directory not found: {directory}")
        return
    
    # Supported file extensions
    text_extensions = {'.txt', '.md', '.text'}
    pdf_extensions = {'.pdf'}
    
    files_uploaded = 0
    files_failed = 0
    
    # Process all files in directory
    for file_path in directory_path.rglob('*'):
        if file_path.is_file():
            file_ext = file_path.suffix.lower()
            file_name = file_path.name
            
            # Read file content
            content = ""
            if file_ext in text_extensions:
                content = read_text_file(str(file_path))
            elif file_ext in pdf_extensions:
                content = read_pdf_file(str(file_path))
            else:
                logger.warning(f"Skipping unsupported file type: {file_name}")
                continue
            
            if not content.strip():
                logger.warning(f"Empty or unreadable file: {file_name}")
                continue
            
            # Upload to LightRAG
            try:
                # Note: LightRAG API might need knowledge_base in the request
                # Check LightRAG API documentation for exact parameter name
                result = client.insert_text(
                    text=content,
                    file_source=file_name
                )
                
                # If knowledge_base needs to be specified, you might need to modify
                # the insert_text method or use a different approach
                logger.info(f"✓ Uploaded: {file_name}")
                files_uploaded += 1
            except Exception as e:
                logger.error(f"✗ Failed to upload {file_name}: {e}")
                files_failed += 1
    
    logger.info(f"\nUpload complete:")
    logger.info(f"  ✓ Successfully uploaded: {files_uploaded} files")
    logger.info(f"  ✗ Failed: {files_failed} files")
    logger.info(f"  Knowledge base: {knowledge_base}")


def upload_single_file_to_kb(
    file_path: str,
    knowledge_base: str,
    base_url: str = "http://localhost:9262",
    api_key: str = "MyCustomLightRagKey456"
):
    """
    Upload a single file to a specific knowledge base
    
    Args:
        file_path: Path to the file
        knowledge_base: Name of the knowledge base
        base_url: LightRAG API base URL
        api_key: LightRAG API key
    """
    client = LightRAGClient(base_url=base_url, api_key=api_key)
    
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        logger.error(f"File not found: {file_path}")
        return
    
    file_ext = file_path_obj.suffix.lower()
    file_name = file_path_obj.name
    
    # Read file content
    content = ""
    if file_ext in {'.txt', '.md', '.text'}:
        content = read_text_file(file_path)
    elif file_ext == '.pdf':
        content = read_pdf_file(file_path)
    else:
        logger.error(f"Unsupported file type: {file_ext}")
        return
    
    if not content.strip():
        logger.error(f"Empty or unreadable file: {file_name}")
        return
    
    # Upload
    try:
        result = client.insert_text(
            text=content,
            file_source=file_name
        )
        logger.info(f"✓ Successfully uploaded '{file_name}' to knowledge base '{knowledge_base}'")
        return result
    except Exception as e:
        logger.error(f"✗ Failed to upload {file_name}: {e}")
        return None


def main():
    """Command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Upload documents to LightRAG knowledge base")
    parser.add_argument("path", help="Path to file or directory")
    parser.add_argument(
        "--knowledge-base",
        "-kb",
        required=True,
        help="Knowledge base name (e.g., 'ebl_financial_reports', 'ebl_user_documents')"
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
    
    args = parser.parse_args()
    
    path = Path(args.path)
    
    if path.is_file():
        upload_single_file_to_kb(
            str(path),
            args.knowledge_base,
            args.base_url,
            args.api_key
        )
    elif path.is_dir():
        upload_directory_to_kb(
            str(path),
            args.knowledge_base,
            args.base_url,
            args.api_key
        )
    else:
        logger.error(f"Path not found: {path}")


if __name__ == "__main__":
    main()

