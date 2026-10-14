#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/opt/ffmpeg-full/bin:/usr/local/opt/ffmpeg-full/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
for church_python in python3.12 python3.11 python3; do
    if command -v "$church_python" >/dev/null 2>&1 && "$church_python" -c 'import sys; sys.exit(sys.version_info[:2] not in ((3,11),(3,12)))'; then
        exec "$church_python" run_local.py "$@"
    fi
done
echo 'Python 3.11/3.12 is required. On Mac: brew install python@3.12 ffmpeg-full'
exit 1
