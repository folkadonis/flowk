import sys
import subprocess
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: flowk [ui]")
        sys.exit(1)
        
    command = sys.argv[1]
    
    if command == "dev" or command == "ui":
        # Launch production-grade v2 dashboard
        try:
            from fastapi import FastAPI
            import uvicorn
            import webbrowser
            import threading
            import time
        except ImportError:
            print("FastAPI and Uvicorn are required for the v2 dashboard. Run 'pip install flowk[api]'")
            sys.exit(1)
            
        from flowk import Graph
        from flowk.server import create_app
        
        # Create a dummy graph to host the dashboard if none is provided
        # It will still serve the /ui/sessions etc. from the global memory store
        dummy_graph = Graph() # Automatically uses .flowk/flowk.db
        app = create_app(dummy_graph)
        
        url = "http://127.0.0.1:8502"
        
        def open_browser():
            time.sleep(1.5) # Wait for uvicorn to start
            print(f"🌍 Opening dashboard at {url}")
            webbrowser.open(url)

        if command == "dev":
            print("🚀 Starting Flowk Development Mode...")
            threading.Thread(target=open_browser, daemon=True).start()
            # In dev mode we would ideally watch the current directory
            # For now, we launch the standard dashboard server
            uvicorn.run(app, host="127.0.0.1", port=8502)
        else:
            print("🔥 Starting Flowk Production Dashboard (v2)...")
            threading.Thread(target=open_browser, daemon=True).start()
            uvicorn.run(app, host="127.0.0.1", port=8502)
    elif command == "serve":
        if len(sys.argv) < 3:
            print("Usage: flowk serve <file_path>:<graph_instance>")
            sys.exit(1)
        # TODO: Implement dynamic loading for 'flowk serve'
        print("🛠️ 'flowk serve' is coming soon in Phase 1.")
    elif command == "runs":
        if len(sys.argv) < 3:
            print("Usage: flowk runs <list|inspect> [run_id]")
            sys.exit(1)
        subcommand = sys.argv[2]
        
        from flowk.storage import StorageRegistry
        StorageRegistry.configure() # Will pick up .flowk/flowk.db
        
        if subcommand == "list":
            runs = StorageRegistry.list_runs()
            if not runs:
                print("No runs found in the registry.")
                sys.exit(0)
            print(f"📋 Found {len(runs)} runs (showing last 20):")
            for r in runs[-20:]:
                events = StorageRegistry.get_events(r)
                if events:
                    status = "finished" if any(e["type"] in ["run_end", "run_error", "run_interrupt"] for e in events) else "running"
                    print(f"  - [{status.upper()}] {r}")
                else:
                    print(f"  - [ARCHIVED] {r}")
        elif subcommand == "inspect":
            if len(sys.argv) < 4:
                print("Usage: flowk runs inspect <run_id>")
                sys.exit(1)
            run_id = sys.argv[3]
            events = StorageRegistry.get_events(run_id)
            if not events:
                try:
                    trace = StorageRegistry.get_trace(run_id)
                    print(f"🔍 Trace for {run_id}: {len(trace)} steps recorded.")
                except Exception:
                    print(f"❌ No data found for run ID: {run_id}")
                    sys.exit(1)
            else:
                print(f"🔍 Event Log for {run_id}:")
                for e in events:
                    import datetime
                    ts = datetime.datetime.fromtimestamp(e["timestamp"]).strftime('%H:%M:%S')
                    node = e.get("node") or "system"
                    print(f"  [{ts}] {e['type'].upper()} @ {node}")
        else:
            print(f"Unknown runs subcommand: {subcommand}")
            print("Available: list, inspect")
    else:
        print(f"Unknown command: {command}")
        print("Available commands: dev, ui, serve, runs")

if __name__ == "__main__":
    main()
