# Bundled SVG icons

`Icon(name)` looks here, after `ICON_REGISTRY`, for `<name>.svg`. Files in
this directory ship in the wheel, so keep them small, monochrome and
stroke-only: `Icon` recolours them with the style's `icon_color`, the way it
draws the pictograms, so a filled or multicoloured file would be flattened.

The frame is a 24 by 24 viewBox with a 2 unit stroke, which comes out the same
weight as the pictograms once scaled to the default icon height.

Icons for one video belong in manim's `assets_dir` (the `assets/` folder next
to your scene file by default), which `Icon` searches after this directory and
leaves in their own colours.
