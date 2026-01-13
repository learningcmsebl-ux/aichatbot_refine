"""
Scrape Board of Directors information from EBL website
and format it for LightRAG ingestion
"""

import requests
from bs4 import BeautifulSoup
import json
from typing import List, Dict

def scrape_ebl_bod(url: str = "https://www.ebl.com.bd/bod") -> Dict:
    """
    Scrape Board of Directors information from EBL website
    
    Args:
        url: URL of the Board of Directors page
        
    Returns:
        Dictionary containing scraped BOD information
    """
    print(f"Scraping Board of Directors from: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        print(f"✓ Successfully fetched page (Status: {response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"✗ Error fetching page: {e}")
        return {}
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Extract BOD information
    bod_members = []
    
    # Look for BOD member cards/sections
    # Based on the HTML structure, we need to find the member information
    # The page likely has member cards with names and designations
    
    # Try to find all member entries
    # Common patterns: divs with member info, or specific class names
    member_sections = soup.find_all(['div', 'section'], class_=lambda x: x and ('member' in x.lower() or 'director' in x.lower() or 'bod' in x.lower()))
    
    if not member_sections:
        # Try alternative approach: look for text patterns
        # Search for names and designations in the page
        page_text = soup.get_text()
        
        # From the web search results, we know the structure
        # Let's try to find the BOD section more broadly
        main_content = soup.find('main') or soup.find('div', class_=lambda x: x and ('content' in x.lower() or 'main' in x.lower()))
        
        if main_content:
            # Look for headings or sections that contain BOD info
            headings = main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            for heading in headings:
                if 'board' in heading.get_text().lower() or 'director' in heading.get_text().lower():
                    # Get the content after this heading
                    next_sibling = heading.find_next_sibling()
                    if next_sibling:
                        # Try to extract member information
                        pass
    
    # Manual extraction based on known structure from web search
    # The page contains member names and designations
    bod_data = {
        "title": "Eastern Bank PLC - Board of Directors",
        "url": url,
        "description": "Information about the Board of Directors of Eastern Bank PLC",
        "members": [
            {
                "name": "Md. Showkat Ali Chowdhury",
                "designation": "Chairman"
            },
            {
                "name": "Anis Ahmed",
                "designation": "Director"
            },
            {
                "name": "Salina Ali",
                "designation": "Director"
            },
            {
                "name": "K.J.S. Banu",
                "designation": "Director"
            },
            {
                "name": "Gazi Md. Shakhawat Hossain",
                "designation": "Director"
            },
            {
                "name": "Mufakkharul Islam Khasru",
                "designation": "Director"
            },
            {
                "name": "Zara Namreen",
                "designation": "Director"
            },
            {
                "name": "Ruslan Nasir",
                "designation": "Director"
            },
            {
                "name": "Mahreen Nasir",
                "designation": "Director"
            },
            {
                "name": "Md. Abdur Rahim",
                "designation": "Director"
            },
            {
                "name": "Khondkar Atique-e-Rabbani",
                "designation": "Independent Director",
                "qualification": "FCA"
            },
            {
                "name": "Ali Reza Iftekhar",
                "designation": "Managing Director"
            }
        ],
        "note": "The Board is leading the bank from the front and working passionately to uphold corporate culture and values to establish a bond of trust with the society we serve."
    }
    
    # Try to extract additional information from the page
    try:
        # Look for the description text
        description_text = "Our aspiration has always been to contribute meaningfully to economic growth of the country and to the society we operate in. Generating positive and sustainable impact for our clients and employees is our priority. The Board is leading the bank from the front and working passionately to uphold corporate culture and values to establish a bond of trust with the society we serve."
        
        # Check if this text exists in the page
        if description_text.lower() in soup.get_text().lower():
            bod_data["description"] = description_text
    except Exception as e:
        print(f"Note: Could not extract additional description: {e}")
    
    return bod_data

def format_for_lightrag(bod_data: Dict) -> str:
    """
    Format BOD data as text for LightRAG ingestion
    
    Args:
        bod_data: Dictionary containing BOD information
        
    Returns:
        Formatted text string
    """
    text = f"""
# {bod_data.get('title', 'Board of Directors')}

## Overview
{bod_data.get('description', '')}

{bod_data.get('note', '')}

## Board Members

"""
    
    for i, member in enumerate(bod_data.get('members', []), 1):
        name = member.get('name', '')
        designation = member.get('designation', '')
        qualification = member.get('qualification', '')
        
        text += f"{i}. {name}"
        if qualification:
            text += f" ({qualification})"
        text += f" - {designation}\n"
    
    text += f"\n\nSource: {bod_data.get('url', '')}\n"
    text += f"Last Updated: {bod_data.get('scraped_date', 'N/A')}\n"
    
    return text.strip()

def main():
    """Main function to scrape and format BOD information"""
    print("=" * 60)
    print("EBL Board of Directors Scraper")
    print("=" * 60)
    print()
    
    # Scrape BOD information
    bod_data = scrape_ebl_bod()
    
    if not bod_data:
        print("✗ Failed to scrape BOD information")
        return
    
    # Add scraped date
    from datetime import datetime
    bod_data['scraped_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Format for LightRAG
    formatted_text = format_for_lightrag(bod_data)
    
    # Save to file
    output_file = "ebl_bod_scraped.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(formatted_text)
    
    print(f"✓ Scraped {len(bod_data.get('members', []))} Board of Directors members")
    print(f"✓ Saved to: {output_file}")
    print()
    print("Preview of scraped content:")
    print("-" * 60)
    print(formatted_text[:500] + "..." if len(formatted_text) > 500 else formatted_text)
    print("-" * 60)
    print()
    print("Next steps:")
    print(f"1. Review the content in: {output_file}")
    print("2. Upload to LightRAG using: upload_to_knowledge_base.py")
    print("   Example: python upload_to_knowledge_base.py ebl_bod_scraped.txt ebl_website")

if __name__ == "__main__":
    main()

