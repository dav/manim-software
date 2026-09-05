"""
Shared look for the software-explainer layer.

Every mobject in manim_software takes an optional ``style`` argument. When it
is left out, the module-level default (see ``get_style``/``set_style``) is
used, so a whole scene can be re-themed by swapping one object. Individual
constructors still accept explicit overrides (``fill_color=...``) for one-offs.

Also home to the drawing-order constants: everything in a diagram is stacked
by ``z_index`` so that packets ride above wires, wires above nodes, and nodes
above the containers that group them.
"""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from typing import TYPE_CHECKING

from manim import BLUE
from manim import BLUE_D
from manim import GREEN
from manim import GREY_A
from manim import GREY_B
from manim import GREY_C
from manim import GREY_D
from manim import GREY_E
from manim import MED_SMALL_BUFF
from manim import RED
from manim import TEAL
from manim import WHITE
from manim import YELLOW
from manim import Text

if TYPE_CHECKING:
    from manim.typing import ManimColor


# Drawing order, applied through Mobject.z_index. Containers sit under
# everything; packets ride on top of wires; captions float above all.
Z_CONTAINER = -2
Z_NODE = 0
Z_EDGE = 1
Z_EDGE_LABEL = 2
Z_PACKET = 3
Z_ANNOTATION = 5
Z_CAPTION = 10

# A generic Pango family, so the look is similar everywhere; set a family
# name (``DiagramStyle(font="Helvetica")``) for a fixed one.
DEFAULT_DIAGRAM_FONT = "sans-serif"


@dataclass
class DiagramStyle:
    # Nodes / components
    node_fill: ManimColor = GREY_E
    node_fill_opacity: float = 1.0
    node_stroke: ManimColor = GREY_B
    node_stroke_width: float = 2.0
    node_corner_radius: float = 0.15
    node_padding: float = MED_SMALL_BUFF
    active_color: ManimColor = YELLOW
    error_color: ManimColor = RED
    done_color: ManimColor = GREEN

    # Containers (dashed group boxes)
    container_stroke: ManimColor = GREY_C
    container_stroke_width: float = 1.5
    container_dash_length: float = 0.12

    # Edges / connectors
    edge_color: ManimColor = GREY_B
    edge_stroke_width: float = 3.0
    edge_tip_length: float = 0.2
    edge_corner_radius: float = 0.2

    # Packets
    packet_color: ManimColor = BLUE
    reply_color: ManimColor = TEAL
    packet_radius: float = 0.12

    # Text
    font: str = DEFAULT_DIAGRAM_FONT
    text_color: ManimColor = WHITE
    # Secondary text: subtitles, attributions, anything that should read as
    # quieter than the thing it sits under.
    muted_color: ManimColor = GREY_B
    label_font_size: int = 28
    small_font_size: int = 20
    icon_color: ManimColor = GREY_A

    # Sequence diagrams
    lifeline_color: ManimColor = GREY_C
    activation_fill: ManimColor = GREY_D

    # 3D set pieces
    prop_color: ManimColor = BLUE_D

    def with_(self, **changes) -> DiagramStyle:
        """A copy of this style with some fields replaced."""
        return replace(self, **changes)


DEFAULT_STYLE = DiagramStyle()

_current_style: DiagramStyle = DEFAULT_STYLE


def get_style() -> DiagramStyle:
    return _current_style


def set_style(style: DiagramStyle) -> None:
    global _current_style
    _current_style = style


def _resolve_style(style: DiagramStyle | None) -> DiagramStyle:
    return style if style is not None else get_style()


def _pick(value, default):
    """The explicit override when one was given, otherwise the style's value."""
    return default if value is None else value


def _make_text(
    text: str,
    font_size: int | None = None,
    style: DiagramStyle | None = None,
    **kwargs
) -> Text:
    style = _resolve_style(style)
    return Text(
        text,
        font=kwargs.pop("font", style.font),
        font_size=_pick(font_size, style.label_font_size),
        color=kwargs.pop("color", style.text_color),
        **kwargs
    )


def _backstroke(text: Text, width: float = 4.0) -> Text:
    """A dark outline behind text that sits over a wire or a busy background."""
    return text.set_stroke(width=width, background=True)
