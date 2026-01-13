"""
Scrape EBL Management page and prepare for LightRAG upload
Scrapes https://www.ebl.com.bd/management
"""

import requests
from bs4 import BeautifulSoup
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def scrape_management_page(url: str = "https://www.ebl.com.bd/management") -> dict:
    """Scrape EBL Management page"""
    
    logger.info(f"Scraping: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract main content
        content = {
            "url": url,
            "title": "EBL Management Committee",
            "description": "Management Committee (MANCOM) is the highest decision and policy making executive body",
            "management_committee": []
        }
        
        # Find management committee members
        # Based on the HTML structure, look for management members
        main_content = soup.find('div', class_='main-content') or soup.find('main') or soup.find('body')
        
        if main_content:
            # Extract text content
            text_content = main_content.get_text(separator='\n', strip=True)
            
            # Try to find structured management information
            # Look for headings and member names
            headings = main_content.find_all(['h1', 'h2', 'h3', 'h4', 'strong'])
            
            members = []
            current_section = None
            
            # Extract management members from the page
            # The page shows names and their designations
            paragraphs = main_content.find_all(['p', 'div'])
            
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 10:  # Filter out empty/short texts
                    # Check if it looks like a name and designation
                    if any(keyword in text.lower() for keyword in ['managing director', 'deputy managing director', 'chief', 'head', 'unit head']):
                        members.append(text)
            
            content["management_committee"] = members
            content["full_text"] = text_content
        
        # Also extract structured data if available
        # Look for specific management member sections
        member_sections = soup.find_all(['div', 'section'], class_=lambda x: x and ('member' in x.lower() or 'management' in x.lower()))
        
        structured_members = []
        for section in member_sections:
            name_elem = section.find(['h3', 'h4', 'strong', 'span'])
            designation_elem = section.find(['p', 'div', 'span'], class_=lambda x: x and ('designation' in x.lower() or 'title' in x.lower()))
            
            if name_elem:
                name = name_elem.get_text(strip=True)
                designation = designation_elem.get_text(strip=True) if designation_elem else ""
                
                if name:
                    structured_members.append({
                        "name": name,
                        "designation": designation
                    })
        
        if structured_members:
            content["structured_members"] = structured_members
        
        logger.info(f"✓ Scraped {len(members)} management members")
        
        return content
        
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return {"error": str(e)}


def format_for_lightrag(content: dict) -> str:
    """Format scraped content for LightRAG upload"""
    
    text = f"""EBL Management Committee Information
Source: {content.get('url', 'Unknown')}

{content.get('description', '')}

MANAGEMENT COMMITTEE MEMBERS:

"""
    
    # Add structured members if available
    if "structured_members" in content and content["structured_members"]:
        for member in content["structured_members"]:
            text += f"Name: {member.get('name', 'N/A')}\n"
            text += f"Designation: {member.get('designation', 'N/A')}\n"
            text += "\n"
    
    # Add full text content
    if "full_text" in content:
        text += "\n" + "="*70 + "\n"
        text += "FULL PAGE CONTENT:\n"
        text += "="*70 + "\n\n"
        text += content["full_text"]
    
    return text


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape EBL Management page")
    parser.add_argument(
        "--url",
        default="https://www.ebl.com.bd/management",
        help="URL to scrape (default: https://www.ebl.com.bd/management)"
    )
    parser.add_argument(
        "--output-dir",
        default="scraped_text",
        help="Output directory (default: scraped_text)"
    )
    parser.add_argument(
        "--show-preview",
        action="store_true",
        help="Show preview of scraped content"
    )
    
    args = parser.parse_args()
    
    # Scrape the page
    content = scrape_management_page(args.url)
    
    if "error" in content:
        logger.error(f"Failed to scrape: {content['error']}")
        return
    
    # Format for LightRAG
    formatted_text = format_for_lightrag(content)
    
    # Save to file
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "EBL_Management_Committee.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(formatted_text)
    
    logger.info(f"✓ Saved to: {output_file}")
    logger.info(f"  File size: {len(formatted_text):,} characters")
    
    # Show preview
    if args.show_preview:
        print("\n" + "="*70)
        print("SCRAPED CONTENT PREVIEW")
        print("="*70)
        print(formatted_text[:2000])
        if len(formatted_text) > 2000:
            print(f"\n... ({len(formatted_text) - 2000:,} more characters)")
        print("="*70)
    
    # Show summary
    print("\n" + "="*70)
    print("SCRAPING SUMMARY")
    print("="*70)
    print(f"URL: {args.url}")
    print(f"Management Members Found: {len(content.get('management_committee', []))}")
    print(f"Structured Members: {len(content.get('structured_members', []))}")
    print(f"Output File: {output_file}")
    print(f"File Size: {len(formatted_text):,} characters")
    
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("1. Review the scraped content:")
    print(f"   {output_file}")
    print("\n2. Upload to LightRAG:")
    print(f"   python upload_to_knowledge_base.py {output_file} --knowledge-base ebl_website")
    print("\n3. Or upload to a dedicated management knowledge base:")
    print(f"   python upload_to_knowledge_base.py {output_file} --knowledge-base ebl_management")
    
    return content


if __name__ == "__main__":
    main()

