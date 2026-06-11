#!/bin/bash
# Build a standalone Verify binary using PyInstaller
# Prerequisites: pip install pyinstaller
# Output: dist/verify — a single self-contained executable

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Clean
rm -rf build dist *.spec

# Ensure pyinstaller is available
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Error: PyInstaller not found. Install with: pip install pyinstaller"
    exit 1
fi

# Build
python -m PyInstaller \
    --onefile \
    --name verify \
    --add-data "examples:examples" \
    --hidden-import verify.requirements.models \
    --hidden-import verify.definitions.models \
    --hidden-import verify.campaigns.models \
    --hidden-import verify.evidence.models \
    --collect-all rich \
    --collect-all textual \
    verify/cli/main.py

echo ""
echo "Binary built: dist/verify"
echo ""
echo "To install shell completions:"
echo "  eval \"\$(dist/verify completion bash)\"   # bash"
echo "  eval \"\$(dist/verify completion zsh)\"    # zsh"
echo "  dist/verify completion fish | source       # fish"
