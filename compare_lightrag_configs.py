"""
Compare LightRAG container configurations
Extract key differences between LightRAG_30092025 and LightRAG_New
"""

import json

# Settings from LightRAG_30092025 (working container)
old_config = {
    "EMBEDDING_DIM": "1536",  # KEY: Explicitly set!
    "EMBEDDING_BINDING": "openai",
    "EMBEDDING_MODEL": "text-embedding-3-small",
    "EMBEDDING_BINDING_HOST": "https://api.openai.com/v1",
    "EMBEDDING_BINDING_API_KEY": "sk-proj-...",  # Has API key
    "LLM_BINDING": "openai",
    "LLM_MODEL": "gpt-4o-mini",
    "LLM_BINDING_HOST": "https://api.openai.com/v1",
    "LLM_BINDING_API_KEY": "sk-proj-...",  # Has API key
    "EMBEDDING_FUNC_MAX_ASYNC": "6",
    "EMBEDDING_BATCH_NUM": "64",
    "LIGHTRAG_API_KEY": "MyCustomLightRagKey456",
    "WORKING_DIR": "/app/data/rag_storage",
    "INPUT_DIR": "/app/data/inputs"
}

print("=" * 70)
print("LightRAG Configuration Comparison")
print("=" * 70)
print()
print("Key Settings from LightRAG_30092025 (Working):")
print("-" * 70)
for key, value in old_config.items():
    if "API_KEY" in key:
        print(f"  {key}: {'*' * 20} (hidden)")
    else:
        print(f"  {key}: {value}")

print()
print("=" * 70)
print("Critical Differences to Check in LightRAG_New:")
print("=" * 70)
print()
print("1. EMBEDDING_DIM=1536")
print("   - Old container: ✅ Explicitly set to 1536")
print("   - New container: ❓ May be missing (causes dimension mismatch)")
print()
print("2. EMBEDDING_BINDING_HOST")
print("   - Old container: ✅ https://api.openai.com/v1")
print("   - New container: ❓ May be missing")
print()
print("3. EMBEDDING_BINDING_API_KEY")
print("   - Old container: ✅ Has API key")
print("   - New container: ❓ May be missing (using OPENAI_API_KEY instead)")
print()
print("4. LLM_BINDING_HOST")
print("   - Old container: ✅ https://api.openai.com/v1")
print("   - New container: ❓ May be missing")
print()
print("5. LLM_BINDING_API_KEY")
print("   - Old container: ✅ Has API key")
print("   - New container: ❓ May be missing (using OPENAI_API_KEY instead)")
print()
print("=" * 70)
print("Solution: Update LightRAG_New with missing settings")
print("=" * 70)

