import os
import sys

# Define base paths
ROOT_DIR = os.getcwd()
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

# Ensure backend and backend/app are in sys.path
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Mock environment variables for config if needed
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
os.environ.setdefault("ENCRYPTION_KEY", "dev-encryption-key-change-in-production")
os.environ.setdefault("EMBEDDING_DIMENSION", "1536")

try:
    # Use the full path for the import as expected by the app structure
    from app.llm.graph.graph import get_compiled_graph
    
    # Get the compiled graph
    print("Building graph...")
    app = get_compiled_graph()

    # Generate the PNG image using the mermaid visualizer
    print("Generating visualization...")
    png_data = app.get_graph().draw_mermaid_png()
    
    # Save to file
    output_path = os.path.join(ROOT_DIR, "graph.png")
    with open(output_path, "wb") as f:
        f.write(png_data)
        
    print(f"Successfully saved graph visualization to {output_path}")

except Exception as e:
    import traceback
    print(f"Error generating graph: {e}")
    traceback.print_exc()
    print("\nTip: If you see 'ImportError', ensure you are running this from the project root.")
    print("If you see 'mermaid' related errors, you may need to install 'pyppeteer' or 'playwright'.")
