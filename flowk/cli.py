import sys
import subprocess
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: flowk [ui]")
        sys.exit(1)
        
    command = sys.argv[1]
    
    if command == "ui":
        # Launch production-grade v2 dashboard
        try:
            from fastapi import FastAPI
            import uvicorn
        except ImportError:
            print("FastAPI and Uvicorn are required for the v2 dashboard. Run 'pip install flowk[api]'")
            sys.exit(1)
            
        from flowk import Graph
        from flowk.server import create_app
        
        # Create a dummy graph to host the dashboard if none is provided
        # It will still serve the /ui/sessions etc. from the global memory store
        dummy_graph = Graph(checkpoint_db="flowk_memory.db")
        app = create_app(dummy_graph)
        
        print("🔥 Starting Flowk Production Dashboard (v2)...")
        uvicorn.run(app, host="127.0.0.1", port=8502)
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
