#!/usr/bin/env bash
# One-click JARVIS — always launches the CURRENT build:
#   1) load settings from .env (PIPER_MODEL voice, etc.)
#   2) rebuild the frontend if its source changed since the last build
#   3) start the backend if it isn't already serving
#   4) open the UI window (JarvisUI class -> center screen; GPU-pinned to GTX 1650)
DIR="/home/utsav/jarvis"
PORT=8340

# 1) load env (voice model + settings). ANTHROPIC_API_KEY stays empty -> free subscription brain.
set -a; [ -f "$DIR/.env" ] && . "$DIR/.env"; set +a

# 2) rebuild the frontend if any source file is newer than the built bundle (or no build yet)
if command -v npm >/dev/null 2>&1; then
  if [ ! -f "$DIR/frontend/dist/index.html" ] || \
     [ -n "$(find "$DIR/frontend/src" -type f -newer "$DIR/frontend/dist/index.html" 2>/dev/null | head -1)" ]; then
    ( cd "$DIR/frontend" && npm run build ) >/tmp/jarvis-build.log 2>&1
  fi
fi

# 3) start backend if not already serving
if ! curl -s -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null; then
  nohup "$DIR/.venv/bin/python" "$DIR/server.py" --host 127.0.0.1 --port "$PORT" \
    >/tmp/jarvis-server.log 2>&1 &
  for _ in $(seq 1 40); do
    curl -s -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null && break
    sleep 0.5
  done
fi

# 4) open the main UI window on the center screen
exec env __NV_PRIME_RENDER_OFFLOAD=1 \
         __GLX_VENDOR_LIBRARY_NAME=nvidia \
         __VK_LAYER_NV_optimus=NVIDIA_only \
  google-chrome \
    --app="http://127.0.0.1:$PORT/?v=$(date +%s)" --start-fullscreen \
    --class=JarvisUI \
    --ozone-platform=x11 \
    --use-fake-ui-for-media-stream \
    --ignore-gpu-blocklist --enable-gpu-rasterization --enable-zero-copy \
    --user-data-dir="$HOME/.jarvis-ui-profile"
