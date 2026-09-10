#!/usr/bin/env bash
# Re-render the GIFs and the still that the README embeds, into docs/media/.
#
#     uv run scripts/render_readme_media.sh
#
# Low-quality renders are 854x480 at 15 fps. The GIFs are scaled to 640 wide
# at 10 fps with a per-file palette, which keeps the long story a few MB.
set -euo pipefail
cd "$(dirname "$0")/.."
out=docs/media
mkdir -p "$out"

gif() {  # scene name, output name
    manim -ql examples/request_flow.py "$1"
    src=$(ls -t tmp/media/videos/request_flow/480p15/"$1"*.mp4 | head -1)
    ffmpeg -y -loglevel error -i "$src" \
        -vf "fps=10,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
        "$out/$2.gif"
}

gif RequestFlow request_flow
gif RequestSequence request_sequence
gif DatabaseZoom database_zoom
gif PacketTest packet_test

manim -s -qm examples/request_flow.py SoftwareSmokeScene
cp "$(ls -t tmp/media/images/request_flow/SoftwareSmokeScene*.png | head -1)" "$out/smoke.png"

ls -la "$out"
