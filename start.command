#!/bin/bash
# Mod-Guide launcher for macOS. Double-click this file to start the app.
# First run: creates the Python environment and installs the requirements
# (several minutes). Later runs start in a few seconds.
# Optional: put settings such as OPENAI_API_KEY=... in a file named config.env
# in this folder.

cd "$(dirname "$0")" || exit 1

pause() { echo; read -n 1 -r -p "Press any key to close this window..."; echo; }

# 1. Check for Python 3.10 or newer.
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "Mod-Guide needs Python 3.10 or newer."
  echo "Install it from https://www.python.org/downloads/ and double-click this file again."
  pause; exit 1
fi

# 2. Create the environment on the first run.
if [ ! -d .venv ]; then
  echo "First run: setting up Mod-Guide. This can take several minutes..."
  python3 -m venv .venv || { echo "Could not create the environment."; pause; exit 1; }
fi
source .venv/bin/activate

# 3. Install the requirements once.
if [ ! -f .venv/.installed ]; then
  pip install -r requirements.txt || { echo "Installing the requirements failed. Check your internet connection."; pause; exit 1; }
  touch .venv/.installed
fi

# 4. Load optional settings (for example OPENAI_API_KEY).
if [ -f config.env ]; then
  set -a; source config.env; set +a
fi

# 5. Open the browser shortly after the server starts, then run the server.
( sleep 5; open "http://127.0.0.1:8000" ) >/dev/null 2>&1 &
echo "Mod-Guide is running at http://127.0.0.1:8000"
echo "Close this window to stop it."
echo
uvicorn app:app --host 127.0.0.1 --port 8000
pause
