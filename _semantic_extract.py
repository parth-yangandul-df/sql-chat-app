# Combined semantic extraction using graphify's semantic module
import json
import io
from pathlib import Path
from graphify.extract_semantic import extract_semantic_files

# Load uncached files
with open('.graphify_uncached.txt', 'r') as f:
    uncached = [line.strip() for line in f if line.strip()]

print(f"Extracting semantic from {len(uncached)} files...")

# Run semantic extraction
try:
    result = extract_semantic_files(uncached)
    with io.open('.graphify_semantic_new.json', 'w', encoding='utf-8') as out:
        json.dump(result, out, indent=2, default=str)
    print(f"Semantics: {len(result.get('nodes', []))} nodes, {len(result.get('edges', []))} edges")
except Exception as e:
    print(f"Error: {e}")
    # Fall back to empty
    with io.open('.graphify_semantic_new.json', 'w', encoding='utf-8') as out:
        json.dump({'nodes': [], 'edges': [], 'hyperedges': []}, out, indent=2)
    print("Using empty semantics")