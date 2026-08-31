"""
Project Vulpix 2.0 - One-Click Application Launcher
Starts the local API & analytics server and launches your default web browser.
"""

import sys
import time
import webbrowser
import threading
from server import run_server, PORT

def open_browser():
    time.sleep(1.2)
    url = f"http://localhost:{PORT}"
    print(f"🚀 Opening Vulpix AI Analytics Dashboard: {url}")
    webbrowser.open(url)

def main():
    threading.Thread(target=open_browser, daemon=True).start()
    try:
        run_server(PORT)
    except KeyboardInterrupt:
        print("\n⚡ Vulpix AI Dashboard Stopped.")
        sys.exit(0)

if __name__ == '__main__':
    main()
