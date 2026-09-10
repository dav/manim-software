"""
Pictograms for the parts of a software system: a browser, a server, a
database and so on, each drawn from manim primitives so it can be recolored,
scaled and animated piece by piece.

``Icon(name)`` is the one entry point scenes and components use. It looks the
name up in ``ICON_REGISTRY`` first, then falls back to an SVG file found in the
package's ``assets`` directory or manim's configured ``assets_dir``, and
finally to a labelled placeholder so a typo never kills a render.

The package ``assets`` directory ships a few monochrome outlines that have no
pictogram (``phone``, ``mail``, ``file``); they are recoloured with the style's
``icon_color`` like the pictograms. SVGs from ``assets_dir`` keep their own
colours.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from manim import DOWN
from manim import LEFT
from manim import PI
from manim import RIGHT
from manim import UP
from manim import Arc
from manim import Circle
from manim import Dot
from manim import Ellipse
from manim import Line
from manim import Polygon
from manim import Rectangle
from manim import RoundedRectangle
from manim import Square
from manim import SVGMobject
from manim import Union
from manim import VGroup
from manim import VMobject
from manim import config
from manim import logger

from manim_software.style import _make_text
from manim_software.style import _pick
from manim_software.style import _resolve_style

if TYPE_CHECKING:
    from typing import Iterable

    from manim.typing import ManimColor

    from manim_software.style import DiagramStyle


SOFTWARE_ASSETS_DIR = Path(__file__).parent / "assets"
"""SVGs that ship with the package; see ``assets/README.md``."""

DEFAULT_ICON_HEIGHT = 0.6


class Pictogram(VGroup):
    """
    Base for icons drawn from primitives. Subclasses override ``build`` and draw
    at whatever scale is convenient (roughly one unit tall is a good habit);
    the base class then normalises the height, recolors every part and keeps
    each part's own fill opacity, so LEDs and bolts stay filled while outlines
    stay hollow.
    """
    default_height: float = DEFAULT_ICON_HEIGHT

    def __init__(
        self,
        height: float | None = None,
        color: ManimColor | None = None,
        stroke_width: float = 2.0,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.style = _resolve_style(style)
        self.icon_color = _pick(color, self.style.icon_color)
        self.line_width = stroke_width
        self.add(*self.build())
        self.set_color(self.icon_color)
        self.scale_to_fit_height(_pick(height, self.default_height))

    def build(self) -> Iterable[VMobject]:
        raise NotImplementedError

    # Small helpers so subclasses read as drawings rather than style plumbing
    def _outline(self, mob: VMobject) -> VMobject:
        return mob.set_stroke(width=self.line_width).set_fill(opacity=0)

    def _solid(self, mob: VMobject) -> VMobject:
        return mob.set_stroke(width=0).set_fill(opacity=1)


class BrowserIcon(Pictogram):
    def build(self):
        window = self._outline(RoundedRectangle(corner_radius=0.1, width=1.4, height=1.0))
        bar_y = window.get_top()[1] - 0.25
        bar = self._outline(Line(window.get_left(), window.get_right()))
        bar.set_y(bar_y)
        dots = VGroup(*(
            self._solid(Dot(radius=0.045))
            for _ in range(3)
        )).arrange(RIGHT, buff=0.05)
        dots.move_to([window.get_left()[0] + 0.25, (window.get_top()[1] + bar_y) / 2, 0])
        return [window, bar, dots]


class ServerIcon(Pictogram):
    def build(self):
        units = VGroup()
        for _ in range(3):
            unit = self._outline(RoundedRectangle(corner_radius=0.06, width=1.2, height=0.3))
            led = self._solid(Dot(radius=0.045))
            led.move_to(unit.get_right() + 0.15 * LEFT)
            units.add(VGroup(unit, led))
        units.arrange(DOWN, buff=0.05)
        return [units]


class DatabaseIcon(Pictogram):
    """The classic cylinder, drawn flat: an ellipse lid over a drum."""
    def build(self):
        width, lid_height, depth = 1.0, 0.36, 0.9
        lid = self._outline(Ellipse(width=width, height=lid_height))
        # An Ellipse starts at its right side and runs counterclockwise, so the
        # second half of it is the bottom curve.
        bottom = self._outline(Ellipse(width=width, height=lid_height).get_subcurve(0.5, 1.0))
        bottom.shift(depth * DOWN)
        ring = bottom.copy().shift(0.5 * depth * UP)
        left = self._outline(Line(lid.get_left(), lid.get_left() + depth * DOWN))
        right = self._outline(Line(lid.get_right(), lid.get_right() + depth * DOWN))
        return [lid, left, right, ring, bottom]


class CacheIcon(Pictogram):
    """A box with a lightning bolt: fast, volatile."""
    def build(self):
        box = self._outline(RoundedRectangle(corner_radius=0.1, width=1.0, height=1.0))
        bolt = self._solid(Polygon(
            [0.12, 0.42, 0], [-0.28, -0.02, 0], [-0.02, -0.02, 0],
            [-0.12, -0.42, 0], [0.28, 0.06, 0], [0.02, 0.06, 0],
        ))
        return [box, bolt]


class QueueIcon(Pictogram):
    """A row of slots with the direction things move through them."""
    def build(self):
        slots = VGroup(*(
            self._outline(Square(side_length=0.3))
            for _ in range(4)
        )).arrange(RIGHT, buff=0.06)
        arrow = self._outline(Line(0.6 * LEFT, 0.6 * RIGHT))
        arrow.add_tip(tip_length=0.14, tip_width=0.14)
        arrow.next_to(slots, DOWN, buff=0.12)
        return [slots, arrow]


class UserIcon(Pictogram):
    def build(self):
        head = self._outline(Circle(radius=0.27))
        head.move_to(0.45 * UP)
        shoulders = self._outline(Arc(radius=0.55, start_angle=0, angle=PI))
        shoulders.move_arc_center_to(0.45 * DOWN)
        base = self._outline(Line(shoulders.get_start(), shoulders.get_end()))
        return [head, shoulders, base]


class CloudIcon(Pictogram):
    def build(self):
        puffs = [
            Circle(radius=0.30).move_to([-0.35, -0.05, 0]),
            Circle(radius=0.40).move_to([0.0, 0.15, 0]),
            Circle(radius=0.30).move_to([0.40, -0.05, 0]),
            Rectangle(width=1.1, height=0.35).move_to([0.02, -0.2, 0]),
        ]
        return [self._outline(Union(*puffs))]


class LockIcon(Pictogram):
    def build(self):
        body = self._outline(RoundedRectangle(corner_radius=0.08, width=0.8, height=0.6))
        body.move_to(0.2 * DOWN)
        shackle = self._outline(Arc(radius=0.25, start_angle=0, angle=PI))
        shackle.move_arc_center_to(0.12 * UP)
        keyhole = self._solid(Dot(radius=0.06)).move_to(0.2 * DOWN)
        return [body, shackle, keyhole]


ICON_REGISTRY: dict[str, type[Pictogram]] = {
    "browser": BrowserIcon,
    "server": ServerIcon,
    "service": ServerIcon,
    "database": DatabaseIcon,
    "db": DatabaseIcon,
    "cache": CacheIcon,
    "queue": QueueIcon,
    "user": UserIcon,
    "person": UserIcon,
    "cloud": CloudIcon,
    "lock": LockIcon,
    "auth": LockIcon,
}


def register_icon(name: str, cls: type[Pictogram]) -> None:
    ICON_REGISTRY[name.lower()] = cls


def get_assets_dir() -> Path:
    """Manim's configured ``assets_dir``, where user SVGs live."""
    return Path(config.assets_dir)


def find_svg(name: str) -> Path | None:
    """
    The first existing file for ``name`` (with or without ``.svg``): an
    absolute path, then the package assets, then manim's ``assets_dir``.
    """
    candidates = []
    given = Path(name)
    if given.is_absolute():
        candidates.append(given)
    for directory in (SOFTWARE_ASSETS_DIR, get_assets_dir()):
        candidates.append(directory / name)
    for path in candidates:
        for full in (path, path.with_suffix(".svg") if path.suffix != ".svg" else path):
            if full.is_file():
                return full
    return None


def _is_bundled_svg(path: Path) -> bool:
    """Whether ``path`` is one of the SVGs that ship in the package assets directory."""
    return path.resolve().is_relative_to(SOFTWARE_ASSETS_DIR.resolve())


def _placeholder_icon(name: str, height: float, style: DiagramStyle) -> VGroup:
    box = RoundedRectangle(corner_radius=0.1, width=1.4, height=1.0)
    box.set_stroke(style.icon_color, 2.0).set_fill(opacity=0)
    label = _make_text(name, font_size=style.small_font_size, style=style)
    if label.width > 0.9 * box.width:
        label.scale_to_fit_width(0.9 * box.width)
    label.move_to(box)
    return VGroup(box, label).scale_to_fit_height(height)


def Icon(
    name: str,
    height: float = DEFAULT_ICON_HEIGHT,
    style: DiagramStyle | None = None,
    **kwargs
) -> VMobject:
    """
    An icon by name. Registered pictograms come first; otherwise ``name`` is
    treated as an SVG file looked up in the package assets directory, then
    manim's configured ``assets_dir`` (absolute paths also work). Unknown
    names give a labelled placeholder.

    Bundled SVGs are monochrome outlines and take the style's ``icon_color``
    unless ``color=`` is given; SVGs from elsewhere keep their own colours.
    """
    style = _resolve_style(style)
    cls = ICON_REGISTRY.get(name.lower())
    if cls is not None:
        return cls(height=height, style=style, **kwargs)
    path = find_svg(name)
    if path is None:
        logger.warning("No icon or SVG named '%s'; using a placeholder", name)
        return _placeholder_icon(name, height, style)
    svg = SVGMobject(str(path), height=height, **kwargs)
    if _is_bundled_svg(path) and "color" not in kwargs:
        svg.set_color(style.icon_color)
    return svg
