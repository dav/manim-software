# manim-software

A [Manim Community](https://www.manim.community/) plugin for videos that
explain how software works: the boxes of a system diagram, the wires between
them, packets that travel those wires, sequence diagrams of the same
conversation, and a few 3D props for the camera to swoop down on.

```python
from manim import *
from manim_software import *


class Hello(Scene):
    def construct(self):
        system = SystemDiagram()
        browser = system.add_component("browser", Component("Browser", icon="browser"))
        api = system.add_component("api", Component("API", icon="server"))
        db = system.add_component("db", Component("Database", icon="database"))
        system.get_components().arrange(RIGHT, buff=1.5)
        system.add_container(Container(api, db, title="Backend"))
        system.connect("browser", "api", label="HTTPS")
        system.connect("api", "db", label="SQL")
        self.add(system)

        request = Packet("GET /orders")
        self.play(SendAlong(request, [system.connectors[("browser", "api")],
                                      system.connectors[("api", "db")]]))
        self.play(db.animate.set_state("active"))
```

## Install

```sh
pip install manim-software        # or: uv pip install manim-software
```

It depends on `manim>=0.19` (the Community edition), which needs a few
system libraries before `pip install` can build its Cairo and Pango bindings:

```sh
brew install cairo pango pkg-config ffmpeg            # macOS
sudo apt install libcairo2-dev libpango1.0-dev ffmpeg # Debian / Ubuntu
```

See manim's [installation page](https://docs.manim.community/en/stable/installation.html)
for Windows and the details.
Listing it under `plugins` in `manim.cfg` is optional; `from manim_software import *`
is what brings the names into a scene file.

## Try the examples

```sh
git clone https://github.com/dav/manim-software && cd manim-software
uv venv && uv pip install -e ".[dev]"
manim -pql examples/request_flow.py RequestFlow            # a 68 s story, low-res preview
manim -s -qm examples/request_flow.py SoftwareSmokeScene   # one still with everything in it
manim -qh examples/request_flow.py RequestFlow             # 1080p
```

The repo's `manim.cfg` sends media to `tmp/media`, which is git-ignored.

## What is in the box

- **`DiagramStyle`** — one dataclass of colours, stroke widths, fonts and sizes.
  Every constructor takes `style=`; `set_style` swaps the default for a whole
  scene. Constants `Z_CONTAINER` … `Z_CAPTION` are the drawing order (packets
  over wires over nodes over containers).
- **`Component`** — a labelled, optionally iconed rounded box.
  `get_port(direction, offset)` is where wires attach;
  `set_state("idle" | "active" | "error" | "done")` changes only style, so
  `component.animate.set_state(...)` blends.
- **`Container`** — a dashed, titled boundary around some members; `refit()`
  after moving them.
- **`SystemDiagram`** — a registry: `add_component(name, ...)`,
  `connect(src, dst, ...)`, `get_connector(src, dst)` (which also says whether
  it runs backwards).
- **Icons** — `BrowserIcon`, `ServerIcon`, `DatabaseIcon`, `CacheIcon`,
  `QueueIcon`, `UserIcon`, `CloudIcon`, `LockIcon`, all drawn from primitives.
  `Icon(name)` looks a name up in `ICON_REGISTRY`, then as an SVG in the
  package's `assets` directory, then in manim's configured `assets_dir`, and
  falls back to a labelled placeholder. `register_icon` adds your own.
- **`Connector`** — a wire between two mobjects' ports:
  `route="straight" | "arc" | "orthogonal" | "loop"`, tips at either end
  (`tip_shape` takes any manim `ArrowTip`), `dashed`, `offset` for parallel
  lanes, and a `label`. `attach()` makes it follow moving endpoints. Its
  `route` is a `Route`, the path packets travel.
- **`Packet`** — a dot or a labelled pill. `Send(packet, connector)` moves it
  with a trailing light and an arrival flash; `Reply` goes the other way;
  `SendAlong` chains hops and pulses each component on arrival; `reply_hops`
  reverses a list of connectors for the response.
- **`Message` and `SequenceDiagram`** — plain records and the diagram that
  draws them: `message(src, dst, label, kind)` adds one row, `activate` draws
  a bar. `message_animation(msg, system, sequence)` plays a message in either
  or both views at once, so one list of messages drives the whole video.
- **`Caption`, `Callout`, `Spotlight` / `Unspotlight`** — narration at a
  screen edge, a note with a leader line, and dimming everything but one thing.
  In a 3D scene, add a caption with `caption.pin(scene)` so it stays put while
  the camera moves.
- **`Database3D`, `Server3D`, `SoftwareThreeDScene`, `zoom_to`, `orbit`,
  `reset_camera`** — props that stand up out of the diagram's plane, and the
  camera moves that look at them. Manim's Cairo renderer draws flat mobjects
  over 3D ones; `SoftwareThreeDScene` uses a camera that draws the flat
  diagram first, so props stand on it instead of under it.

## Notes

- Persistent state changes (`set_state`) belong between `play` calls; two
  `.animate` builders on the same mobject inside one `Succession` undo each
  other, because each copies its target when it is built.
- Text uses the style's `font`, a generic `sans-serif` by default. Give
  `DiagramStyle(font="Helvetica")` (or any family `manimpango.list_fonts()`
  knows) for a fixed look across machines.
- Anything you keep on a mobject must survive `copy.deepcopy`: manim copies
  mobjects for every animation.

## Development

```sh
uv venv && uv pip install -e ".[dev]"
pytest                                  # geometry, layout and export tests, no rendering
manim -s -qm examples/request_flow.py SoftwareSmokeScene
```

The package started life as a subpackage of a ManimGL fork
([dav/manim](https://github.com/dav/manim/tree/software-explainers)) and was
ported to Manim Community so it can be installed as a plugin.

## License

MIT
