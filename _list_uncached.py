import json
from pathlib import Path

# Load uncached files list
with open('.graphify_uncached.txt', 'r') as f:
    uncached = [line.strip() for line in f if line.strip()]

# Write chunks
print(f"Total uncached files: {len(uncached)}")
print("Files to process:")
for i, f in enumerate(uncached):
    print(f"  {i+1}: {f}")