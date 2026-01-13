"""
Update Retail & SME Banking Division Head information in LightRAG knowledge base
Adds information about M. Khorshed Anowar as the head of Retail & SME Banking Division
"""

import os
from pathlib import Path
from connect_lightrag import LightRAGClient

# Configuration
LIGHTRAG_URL = os.getenv("LIGHTRAG_URL", "http://localhost:9262")
LIGHTRAG_API_KEY = os.getenv("LIGHTRAG_API_KEY", "MyCustomLightRagKey456")
KNOWLEDGE_BASE = "ebl_website"  # Management info is stored in ebl_website knowledge base

def update_retail_sme_head_info():
    """Add/update Retail & SME Banking Division Head information"""
    
    # Information about the Retail & SME Banking Division Head
    retail_sme_head_info = """
EBL Management Information - Retail & SME Banking Division Head

The head of the Retail & SME Banking Division at Eastern Bank Limited (EBL) is M. Khorshed Anowar. He holds the position of Deputy Managing Director (DMD) and Head of Retail & SME Banking. He is responsible for overseeing the operations and services of this division, which are tailored to retail clients and small to medium enterprises.

Name: M. Khorshed Anowar
Position: Deputy Managing Director (DMD) and Head of Retail & SME Banking
Division: Retail & SME Banking Division

The Retail & SME Banking Division provides comprehensive banking services including:
- Retail banking services for individual customers
- Small and Medium Enterprise (SME) banking services
- Deposit products and services for retail and SME customers
- Loan products for retail and SME customers
- Digital financial services for retail and SME segments

For questions about Retail & SME Banking Division leadership, M. Khorshed Anowar is the Deputy Managing Director (DMD) and Head of Retail & SME Banking.
"""
    
    try:
        client = LightRAGClient(base_url=LIGHTRAG_URL, api_key=LIGHTRAG_API_KEY)
        
        # Check health
        health = client.health_check()
        if health.get("status") not in ["ok", "healthy"]:
            print(f"[X] LightRAG health check failed: {health}")
            return False
        
        print("=" * 60)
        print("Updating Retail & SME Banking Division Head Information")
        print("=" * 60)
        print(f"Knowledge Base: {KNOWLEDGE_BASE}")
        print(f"LightRAG URL: {LIGHTRAG_URL}")
        print()
        
        # Insert the information with knowledge base specified
        result = client.insert_text(
            text=retail_sme_head_info,
            file_source="EBL_Retail_SME_Division_Head_Update.txt",
            knowledge_base=KNOWLEDGE_BASE
        )
        
        print("[OK] Successfully added Retail & SME Banking Division Head information to LightRAG")
        print(f"Knowledge Base: {KNOWLEDGE_BASE}")
        print(f"Response: {result}")
        print()
        print("Next steps:")
        print("1. The information has been uploaded to the knowledge base")
        print("2. LightRAG will process and index this information")
        print("3. The chatbot can now answer questions about the Retail & SME Banking Division head")
        print()
        print("Example queries that will work:")
        print("- 'Who is the head of Retail & SME Banking Division?'")
        print("- 'Who is M. Khorshed Anowar?'")
        print("- 'Who leads the Retail & SME Banking Division at EBL?'")
        print("- 'Who is the DMD of Retail & SME Banking?'")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error adding information: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print()
    success = update_retail_sme_head_info()
    print()
    if success:
        print("[SUCCESS] Update completed successfully!")
    else:
        print("[FAILED] Update failed. Please check the error messages above.")
    print()

