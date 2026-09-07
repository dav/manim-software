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

gif() {  # example module, scene name, output name
    manim -ql "examples/$1.py" "$2"
    src=$(ls -t "tmp/media/videos/$1/480p15/$2"*.mp4 | head -1)
    ffmpeg -y -loglevel error -i "$src" \
        -vf "fps=10,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
        "$out/$3.gif"
}

gif request_flow RequestFlow request_flow
gif request_flow RequestSequence request_sequence
gif request_flow DatabaseZoom database_zoom
gif request_flow PacketTest packet_test
gif failure_modes RetryWithBackoff retry_with_backoff
gif failure_modes TimeoutAndBreaker timeout_and_breaker
gif failure_modes FanOutFanIn fan_out_fan_in
gif failure_modes QueueUnderLoad queue_under_load

manim -s -qm examples/request_flow.py SoftwareSmokeScene
cp "$(ls -t tmp/media/images/request_flow/SoftwareSmokeScene*.png | head -1)" "$out/smoke.png"
manim -s -qm examples/request_flow.py AutoLayoutScene
cp "$(ls -t tmp/media/images/request_flow/AutoLayoutScene*.png | head -1)" "$out/auto_layout.png"

ls -la "$out"
