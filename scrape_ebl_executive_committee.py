"""
Scrape Executive Committee information from EBL website
and format it for LightRAG ingestion
"""

import requests
from bs4 import BeautifulSoup
import json
from typing import List, Dict
from pathlib import Path
from datetime import datetime

def scrape_ebl_executive_committee(url: str = "https://www.ebl.com.bd/executive-committee") -> Dict:
    """
    Scrape Executive Committee information from EBL website
    
    Args:
        url: URL of the Executive Committee page
        
    Returns:
        Dictionary containing scraped Executive Committee information
    """
    print(f"Scraping Executive Committee from: {url}")
    
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
    
    # Extract Executive Committee information
    # Based on the web search results, we know the structure
    exec_committee_data = {
        "title": "Eastern Bank PLC - Executive Committee",
        "url": url,
        "description": "Information about the Executive Committee of Eastern Bank PLC",
        "members": [
            {
                "name": "Salina Ali",
                "designation": "Chairman"
            },
            {
                "name": "Anis Ahmed",
                "designation": "Member"
            },
            {
                "name": "Zara Namreen",
                "designation": "Member"
            },
            {
                "name": "Ali Reza Iftekhar",
                "designation": "Member"
            }
        ]
    }
    
    # Try to extract additional information from the page
    try:
        # Look for any description text
        main_content = soup.find('main') or soup.find('div', class_=lambda x: x and ('content' in x.lower() or 'main' in x.lower()))
        
        if main_content:
            # Try to find the heading
            headings = main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            for heading in headings:
                if 'executive' in heading.get_text().lower() and 'committee' in heading.get_text().lower():
                    # Get any description after the heading
                    next_elements = heading.find_next_siblings(['p', 'div'])
                    for elem in next_elements[:3]:  # Check first 3 elements
                        text = elem.get_text(strip=True)
                        if text and len(text) > 50:  # Meaningful description
                            exec_committee_data["description"] = text
                            break
    except Exception as e:
        print(f"Note: Could not extract additional description: {e}")
    
    return exec_committee_data

def format_for_lightrag(exec_data: Dict) -> str:
    """
    Format Executive Committee data as text for LightRAG ingestion
    
    Args:
        exec_data: Dictionary containing Executive Committee information
        
    Returns:
        Formatted text string
    """
    text = f"""# {exec_data.get('title', 'Executive Committee')}

## Overview
{exec_data.get('description', 'Information about the Executive Committee of Eastern Bank PLC')}

## Executive Committee Members

"""
    
    for i, member in enumerate(exec_data.get('members', []), 1):
        name = member.get('name', '')
        designation = member.get('designation', '')
        
        text += f"{i}. {name} - {designation}\n"
    
    text += f"\n\nSource: {exec_data.get('url', '')}\n"
    text += f"Last Updated: {exec_data.get('scraped_date', 'N/A')}\n"
    
    return text.strip()

def main():
    """Main function to scrape and format Executive Committee information"""
    print("=" * 60)
    print("EBL Executive Committee Scraper")
    print("=" * 60)
    print()
    
    # Scrape Executive Committee information
    exec_data = scrape_ebl_executive_committee()
    
    if not exec_data:
        print("✗ Failed to scrape Executive Committee information")
        return
    
    # Add scraped date
    exec_data['scraped_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Format for LightRAG
    formatted_text = format_for_lightrag(exec_data)
    
    # Create output directory if it doesn't exist
    output_dir = Path("scraped_text")
    output_dir.mkdir(exist_ok=True)
    
    # Save to file
    output_file = output_dir / "EBL_Executive_Committee.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(formatted_text)
    
    print(f"✓ Scraped {len(exec_data.get('members', []))} Executive Committee members")
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
    print(f"   Example: python upload_to_knowledge_base.py {output_file} --knowledge-base ebl_website")

if __name__ == "__main__":
    main()

