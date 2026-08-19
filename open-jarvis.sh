#!/usr/bin/env bash
# Launch the JARVIS UI as its own Chrome instance with a distinct window class
# (JarvisUI) so KWin keeps it on the center screen and only sends real browser
# windows to the Acer. GPU-pinned to the GTX 1650.
exec env __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia \
  google-chrome \
    --app=http://127.0.0.1:8340/ --start-fullscreen \
    --class=JarvisUI \
    --user-data-dir="$HOME/.jarvis-ui-profile" \
    >/dev/null 2>&1 &
