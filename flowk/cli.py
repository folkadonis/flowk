import sys
import subprocess
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: flowk [ui]")
        sys.exit(1)
        
    command = sys.argv[1]
    
    if command == "ui":
        # Launch streamlit dashboard
        try:
            import streamlit  # pyre-ignore
        except ImportError:
            print("Streamlit is not installed. Run 'pip install flowk[ui]' to enable the dashboard.")
            sys.exit(1)
            
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "dashboard.py")
        print("🌊 Starting Flowk Observability Dashboard...")
        subprocess.run(["streamlit", "run", ui_path])
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
