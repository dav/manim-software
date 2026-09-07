"""
The boxes of a system diagram.

``Component`` is a labelled, optionally iconed box with named *ports* on its
edges for connectors to attach to, and a small set of visual states (idle,
active, error, done) that can be switched directly or through ``.animate``.
``Container`` draws a dashed boundary with a title around a group of them (a
browser, a VPC, a cluster). ``SystemDiagram`` is a name registry over both, so
a list of messages can drive a system view and a sequence view alike.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from manim import DOWN
from manim import LEFT
from manim import MED_LARGE_BUFF
from manim import MED_SMALL_BUFF
from manim import RIGHT
from manim import SMALL_BUFF
from manim import UL
from manim import UP
from manim import BackgroundRectangle
from manim import DashedVMobject
from manim import Mobject
from manim import RoundedRectangle
from manim import VGroup
from manim import VMobject

from manim_software.icons import Icon
from manim_software.style import Z_CONTAINER
from manim_software.style import Z_NODE
from manim_software.style import _make_text
from manim_software.style import _pick
from manim_software.style import _resolve_style

if TYPE_CHECKING:
    from typing import Iterable
    from typing import Self

    from manim.typing import ManimColor
    from manim.typing import Point3D
    from manim.typing import Vector3D

    from manim_software.connectors import Connector
    from manim_software.style import DiagramStyle


def _dominant_direction(vect: Vector3D) -> Vector3D:
    """The axis direction (LEFT/RIGHT/UP/DOWN) a vector mostly points along."""
    if abs(vect[0]) >= abs(vect[1]):
        return RIGHT if vect[0] >= 0 else LEFT
    return UP if vect[1] >= 0 else DOWN


def bounding_box_point(mob: Mobject, direction: Vector3D) -> Point3D:
    """
    Where a ray from the centre in ``direction`` leaves the bounding box:
    an edge midpoint for axis directions, a point on the box for diagonals.
    """
    direction = np.array(direction, dtype=float)
    center = mob.get_center()
    half = np.array([mob.width, mob.height, 0.0]) / 2
    scales = [half[i] / abs(direction[i]) for i in range(2) if abs(direction[i]) > 1e-9]
    if not scales:
        return center
    return center + min(scales) * direction


class Component(VGroup):
    """
    A labelled box, the basic node of a system diagram.

    Ports: ``get_port(direction, offset)`` gives a point on the box edge facing
    ``direction``; ``offset`` in [-1, 1] slides it along that edge so a request
    and its reply can run in parallel lanes.

    States: ``STATE_STYLES`` maps a name to style overrides for the box. Values
    naming a ``DiagramStyle`` field (``"active_color"``) are looked up on the
    component's style, so a theme swap recolors states too. ``set_state`` only
    mutates style, which is what lets ``component.animate.set_state("active")``
    blend smoothly.
    """
    STATE_STYLES: dict[str, dict] = {
        "idle": dict(),
        "active": dict(stroke_color="active_color", stroke_width=4.0),
        "error": dict(stroke_color="error_color", stroke_width=4.0),
        "done": dict(stroke_color="done_color", stroke_width=3.0),
    }

    def __init__(
        self,
        label: str | VMobject = "",
        icon: str | VMobject | None = None,
        icon_position: Vector3D = UP,
        icon_height: float = 0.6,
        width: float | None = None,
        height: float | None = None,
        min_width: float = 1.6,
        min_height: float = 0.9,
        padding: float | None = None,
        corner_radius: float | None = None,
        fill_color: ManimColor | None = None,
        fill_opacity: float | None = None,
        stroke_color: ManimColor | None = None,
        stroke_width: float | None = None,
        font_size: int | None = None,
        states: dict[str, dict] | None = None,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        style = _resolve_style(style)
        self.style = style
        self.states = dict(self.STATE_STYLES)
        if states:
            self.states.update(states)
        self.base_style = dict(
            fill_color=_pick(fill_color, style.node_fill),
            fill_opacity=_pick(fill_opacity, style.node_fill_opacity),
            stroke_color=_pick(stroke_color, style.node_stroke),
            stroke_width=_pick(stroke_width, style.node_stroke_width),
        )
        padding = _pick(padding, style.node_padding)

        # Content: label and optional icon, stacked away from icon_position
        if isinstance(label, VMobject):
            self.label = label
        else:
            self.label = _make_text(label, font_size=font_size, style=style)
        if isinstance(icon, str):
            self.icon = Icon(icon, height=icon_height, style=style)
        elif icon is not None:
            self.icon = icon.scale_to_fit_height(icon_height)
        else:
            self.icon = None
        parts = [p for p in (self.icon, self.label) if p is not None and p.family_members_with_points()]
        self.content = VGroup(*parts)
        if len(parts) > 1:
            self.content.arrange(-np.array(icon_position), buff=SMALL_BUFF)

        # Box, sized to content unless told otherwise
        box_width = _pick(width, max(min_width, self.content.width + 2 * padding))
        box_height = _pick(height, max(min_height, self.content.height + 2 * padding))
        self.box = RoundedRectangle(
            corner_radius=_pick(corner_radius, style.node_corner_radius),
            width=box_width,
            height=box_height,
        )
        self.content.move_to(self.box)

        self.add(self.box, self.content)
        self.state = "idle"
        self.set_state("idle")
        self.set_z_index(Z_NODE)

    # Ports
    def get_port(self, direction: Vector3D, offset: float = 0.0) -> Point3D:
        direction = np.array(direction, dtype=float)
        if abs(direction[0]) > 0 and abs(direction[1]) > 0:
            # Diagonal: the rounded corner region
            return bounding_box_point(self.box, direction)
        point = self.box.get_edge_center(direction)
        if abs(direction[0]) > abs(direction[1]):
            along, half = UP, self.box.height / 2
        else:
            along, half = RIGHT, self.box.width / 2
        return point + offset * half * along

    def get_port_toward(self, other: Mobject | Point3D, offset: float = 0.0) -> Point3D:
        target = other.get_center() if isinstance(other, Mobject) else np.array(other)
        return self.get_port(_dominant_direction(target - self.get_center()), offset)

    # States
    def _resolve_state_style(self, name: str) -> dict:
        overrides = self.states[name]
        resolved = dict(self.base_style)
        for key, value in overrides.items():
            if isinstance(value, str) and hasattr(self.style, value):
                value = getattr(self.style, value)
            resolved[key] = value
        return resolved

    def set_state(self, name: str) -> Self:
        if name not in self.states:
            raise KeyError(f"Unknown component state '{name}'")
        self.box.set_style(**self._resolve_state_style(name))
        self.state = name
        return self

    def highlight(self, color: ManimColor | None = None) -> Self:
        self.set_state("active")
        if color is not None:
            self.box.set_stroke(color)
        return self

    def reset(self) -> Self:
        return self.set_state("idle")

    def set_label(self, text: str) -> Self:
        new_label = _make_text(text, font_size=self.label.font_size, style=self.style)
        new_label.move_to(self.label)
        index = self.content.submobjects.index(self.label)
        self.content.submobjects[index] = new_label
        self.label = new_label
        return self


class Container(VGroup):
    """
    A dashed boundary with a title around some members: a browser, a cluster,
    a team. Members stay ordinary submobjects, so moving or arranging the
    container moves them; ``refit`` redraws the frame after they move.
    """
    def __init__(
        self,
        *members: Mobject,
        title: str = "",
        buff: float = MED_LARGE_BUFF,
        title_corner: Vector3D = UL,
        dashed: bool = True,
        corner_radius: float = 0.2,
        stroke_color: ManimColor | None = None,
        stroke_width: float | None = None,
        fill_color: ManimColor | None = None,
        fill_opacity: float = 0.0,
        font_size: int | None = None,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        style = _resolve_style(style)
        self.style = style
        self.buff = buff
        self.dashed = dashed
        self.corner_radius = corner_radius
        self.title_corner = np.array(title_corner, dtype=float)
        self.frame_style = dict(
            stroke_color=_pick(stroke_color, style.container_stroke),
            stroke_width=_pick(stroke_width, style.container_stroke_width),
            fill_color=_pick(fill_color, style.node_fill),
            fill_opacity=fill_opacity,
        )
        self.members = VGroup(*members)
        self.frame = self._build_frame()
        title_text = _make_text(title, font_size=_pick(font_size, style.small_font_size), style=style)
        self.title = VGroup(BackgroundRectangle(title_text, buff=SMALL_BUFF), title_text) if title else VGroup()
        self.title_text = title_text
        self._place_title()
        self.add(self.frame, self.title, self.members)
        self.frame.set_z_index(Z_CONTAINER)
        self.title.set_z_index(Z_CONTAINER)

    def _build_frame(self) -> VMobject:
        width = self.members.width + 2 * self.buff
        height = self.members.height + 2 * self.buff
        rect = RoundedRectangle(corner_radius=self.corner_radius, width=width, height=height)
        rect.set_style(**self.frame_style)
        rect.move_to(self.members)
        if not self.dashed:
            return rect
        perimeter = rect.get_arc_length()
        num_dashes = max(4, int(perimeter / (2 * self.style.container_dash_length)))
        frame = DashedVMobject(rect, num_dashes=num_dashes)
        frame.set_stroke(self.frame_style["stroke_color"], self.frame_style["stroke_width"])
        frame.set_fill(opacity=0)
        if self.frame_style["fill_opacity"] > 0:
            # Dashes cannot carry a fill, so a solid rectangle sits behind them
            fill = rect.copy().set_stroke(width=0)
            frame = VGroup(fill, frame)
        return frame

    def _place_title(self) -> None:
        if len(self.title) == 0:
            return
        corner = self.frame.get_corner(self.title_corner)
        self.title.move_to(corner)
        inward = -self.title_corner[0] * RIGHT
        self.title.shift(inward * (self.title.width / 2 + MED_SMALL_BUFF))

    def refit(self, buff: float | None = None) -> Self:
        if buff is not None:
            self.buff = buff
        new_frame = self._build_frame()
        self.frame.become(new_frame)
        self._place_title()
        return self

    def add_members(self, *mobs: Mobject) -> Self:
        self.members.add(*mobs)
        return self.refit()


class SystemDiagram(VGroup):
    """
    A named collection of components and the connectors between them. Lay
    the components out by hand with ordinary manim calls (``arrange``,
    ``next_to``, ``to_edge``) or let ``layout()`` do it; ``resolve_labels``
    then keeps the wire labels off the things they label.
    """
    def __init__(self, style: DiagramStyle | None = None, **kwargs):
        super().__init__(**kwargs)
        self.style = _resolve_style(style)
        self.components: dict[str, Component] = dict()
        self.connectors: dict[tuple[str, str], Connector] = dict()
        self.containers: list[Container] = []

    def add_component(self, name: str, component: Component) -> Component:
        self.components[name] = component
        self.add(component)
        return component

    def add_container(self, container: Container) -> Container:
        self.containers.append(container)
        # Members are already in the diagram; only the frame and title are new
        self.add(container.frame, container.title)
        return container

    def connect(self, src: str, dst: str, **connector_kwargs) -> Connector:
        from manim_software.connectors import Connector
        connector = Connector(self[src], self[dst], style=self.style, **connector_kwargs)
        self.connectors[(src, dst)] = connector
        self.add(connector)
        return connector

    def __getitem__(self, key):
        if isinstance(key, str):
            return self.components[key]
        return super().__getitem__(key)

    def get_connector(self, src: str, dst: str) -> tuple[Connector, bool]:
        """The connector joining two components, and whether it runs dst -> src."""
        if (src, dst) in self.connectors:
            return self.connectors[(src, dst)], False
        if (dst, src) in self.connectors:
            return self.connectors[(dst, src)], True
        raise KeyError(f"No connector between '{src}' and '{dst}'")

    def get_components(self) -> VGroup:
        return VGroup(*self.components.values())

    def get_connectors(self) -> VGroup:
        return VGroup(*self.connectors.values())

    def layout(
        self,
        kind: str = "layered",
        direction: Vector3D = RIGHT,
        layer_gap: float = 1.5,
        node_gap: float = 0.5,
        layers: dict[str, int] | None = None,
        fit_labels: bool = True,
        resolve_labels: bool = True,
        **kwargs
    ) -> Self:
        """
        Place the components automatically, then refit containers, reroute
        wires and (unless told not to) resolve labels. ``"layered"`` runs
        the flow along ``direction`` with wires going forward, members of a
        container kept together, and ``layers`` pinning components to a
        layer (``{"cache": 2, "db": 2}``); with ``fit_labels`` the layer gap
        grows until the widest wire label fits between layers. ``"force"``
        is a spring layout for graphs without a flow. Extra keyword arguments
        reach ``layout.layered_layout`` or ``layout.force_layout``.
        """
        from manim_software.layout import force_layout
        from manim_software.layout import layered_layout
        nodes = list(self.components)
        edges = list(self.connectors)
        sizes = {name: (comp.width, comp.height) for name, comp in self.components.items()}
        if kind == "layered":
            if fit_labels:
                widest = max([c.label.width for c in self.connectors.values() if c.label is not None] + [0.0])
                layer_gap = max(layer_gap, widest + 2 * SMALL_BUFF + 2 * self.style.edge_tip_length)
            groups = {}
            for index, container in enumerate(self.containers):
                for name, comp in self.components.items():
                    if comp in container.members.submobjects and name not in groups:
                        groups[name] = index
            group_gap = kwargs.pop("group_gap", 2 * max([c.buff for c in self.containers] + [0.0]))
            positions = layered_layout(
                nodes, edges, sizes, direction=direction, layer_gap=layer_gap, node_gap=node_gap,
                groups=groups, group_gap=group_gap, layers=layers, **kwargs
            )
        elif kind == "force":
            positions = force_layout(nodes, edges, sizes, **kwargs)
        else:
            raise ValueError("kind must be 'layered' or 'force'")
        for name, point in positions.items():
            self.components[name].move_to(point)
        for container in self.containers:
            container.refit()
        for connector in self.connectors.values():
            connector.reroute()
        if resolve_labels:
            self.resolve_labels()
        return self

    def resolve_labels(self, margin: float = 0.05, obstacles: Iterable[Mobject] = (), **kwargs) -> Self:
        """
        Move wire labels off components, container titles and each other,
        and where possible off other wires and container frames. Call after
        the components are in their final places (and again after moving
        them, or after parking a packet or a callout on the diagram, passed
        as extra ``obstacles``); see ``layout.place_labels`` for the search
        and its options.
        """
        from manim_software.layout import place_labels
        obstacles = (
            list(self.components.values())
            + [c.title for c in self.containers if len(c.title)]
            + list(obstacles)
        )
        place_labels(
            self.connectors.values(),
            obstacles=obstacles,
            frames=[c.frame for c in self.containers],
            margin=margin,
            **kwargs
        )
        return self
