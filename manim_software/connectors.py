"""
Wires between components.

``Route`` is the path itself: a straight line, an arc, or an orthogonal run
of rounded corners, optionally with arrow tips. ``Connector`` wraps a route
between two mobjects' ports, with an optional label, and knows how to build
its own reverse for replies. Packets travel along ``connector.route``.

Routing is a few pure functions over numpy points (``_orthogonal_waypoints``,
``_round_open_corners``) so it can be unit tested without rendering.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from manim import DOWN
from manim import LEFT
from manim import RIGHT
from manim import SMALL_BUFF
from manim import UP
from manim import ArcBetweenPoints
from manim import ArrowTriangleFilledTip
from manim import BackgroundRectangle
from manim import DashedVMobject
from manim import Mobject
from manim import TipableVMobject
from manim import VGroup
from manim import VMobject
from manim.utils.space_ops import angle_between_vectors
from manim.utils.space_ops import cross2d
from manim.utils.space_ops import normalize

from manim_software.components import bounding_box_point
from manim_software.style import Z_EDGE
from manim_software.style import Z_EDGE_LABEL
from manim_software.style import _backstroke
from manim_software.style import _make_text
from manim_software.style import _pick
from manim_software.style import _resolve_style

if TYPE_CHECKING:
    from typing import Self
    from typing import Sequence

    from manim import ArrowTip
    from manim.typing import ManimColor
    from manim.typing import Point3D
    from manim.typing import Vector3D

    from manim_software.style import DiagramStyle


ROUTE_KINDS = ("auto", "straight", "arc", "orthogonal", "loop")
TIP_PLACEMENTS = (None, "none", "end", "start", "both")


# Pure geometry


def _norm(v) -> float:
    return float(np.linalg.norm(v))


def _is_horizontal(direction: Vector3D) -> bool:
    return abs(direction[0]) > abs(direction[1])


def _dominant_direction(vect: Vector3D) -> Vector3D:
    if abs(vect[0]) >= abs(vect[1]):
        return RIGHT if vect[0] >= 0 else LEFT
    return UP if vect[1] >= 0 else DOWN


def _port(mob: Mobject | Point3D, direction: Vector3D | None, offset: float = 0.0) -> Point3D:
    """
    Where a wire meets a mobject: its ``get_port`` when it has one (Component),
    else the bounding-box edge in ``direction``, else the raw point.
    """
    if not isinstance(mob, Mobject):
        return np.array(mob, dtype=float)
    if direction is None:
        return mob.get_center()
    if hasattr(mob, "get_port"):
        return mob.get_port(direction, offset)
    return bounding_box_point(mob, np.array(direction, dtype=float))


def _dedupe_points(points: Sequence[Point3D], atol: float = 1e-6) -> list[np.ndarray]:
    """Drops repeated points and any point lying on the segment through its neighbours."""
    result: list[np.ndarray] = []
    for p in points:
        p = np.array(p, dtype=float)
        if result and _norm(p - result[-1]) < atol:
            continue
        result.append(p)
    i = 1
    while i < len(result) - 1:
        a, b, c = result[i - 1], result[i], result[i + 1]
        if abs(cross2d(b - a, c - b)) < atol and np.dot(b - a, c - b) > 0:
            result.pop(i)
        else:
            i += 1
    return result


def _orthogonal_waypoints(
    start: Point3D,
    start_dir: Vector3D,
    end: Point3D,
    end_dir: Vector3D,
    stub: float = 0.4,
) -> list[np.ndarray]:
    """
    Corners of an axis-aligned run from ``start`` leaving in ``start_dir`` to
    ``end`` arriving against ``end_dir`` (both directions point *out* of their
    mobject). Facing horizontal ports meet at a vertical midline (a Z), facing
    vertical ports at a horizontal one, and mixed ports turn one corner (an L).
    """
    start = np.array(start, dtype=float)
    end = np.array(end, dtype=float)
    d0 = np.array(start_dir, dtype=float)
    d1 = np.array(end_dir, dtype=float)
    a = start + stub * d0
    b = end + stub * d1
    h0, h1 = _is_horizontal(d0), _is_horizontal(d1)
    if h0 and h1:
        if np.dot(d0, d1) < 0:
            mid_x = (a[0] + b[0]) / 2
            corners = [start, [mid_x, a[1], 0], [mid_x, b[1], 0], end]
        else:
            far_x = max(a[0], b[0]) if d0[0] > 0 else min(a[0], b[0])
            corners = [start, [far_x, a[1], 0], [far_x, b[1], 0], end]
    elif not h0 and not h1:
        if np.dot(d0, d1) < 0:
            mid_y = (a[1] + b[1]) / 2
            corners = [start, [a[0], mid_y, 0], [b[0], mid_y, 0], end]
        else:
            far_y = max(a[1], b[1]) if d0[1] > 0 else min(a[1], b[1])
            corners = [start, [a[0], far_y, 0], [b[0], far_y, 0], end]
    elif h0:
        corners = [start, [b[0], a[1], 0], end]
    else:
        corners = [start, [a[0], b[1], 0], end]
    return _dedupe_points(corners)


def _loop_waypoints(start: Point3D, end: Point3D, direction: Vector3D, reach: float = 0.6) -> list[np.ndarray]:
    """A three-sided detour out in ``direction`` and back, for self messages."""
    start = np.array(start, dtype=float)
    end = np.array(end, dtype=float)
    out = reach * np.array(direction, dtype=float)
    return _dedupe_points([start, start + out, end + out, end])


def _round_open_corners(points: Sequence[Point3D], radius: float) -> VMobject:
    """
    A path through ``points`` with every interior corner replaced by an arc,
    the open-path counterpart of ``Polygram.round_corners``. The radius is
    clamped so neighbouring arcs never overlap.
    """
    pts = [np.array(p, dtype=float) for p in points]
    path = VMobject()
    path.start_new_path(pts[0])
    if len(pts) < 3 or radius <= 0:
        for p in pts[1:]:
            path.add_line_to(p)
        return path
    for v1, v2, v3 in zip(pts, pts[1:], pts[2:]):
        vect1 = normalize(v2 - v1)
        vect2 = normalize(v3 - v2)
        angle = angle_between_vectors(vect1, vect2)
        if angle < 1e-6:
            continue
        # Never cut more than half of either neighbouring segment
        max_cut = 0.5 * min(_norm(v2 - v1), _norm(v3 - v2))
        cut = min(radius * np.tan(angle / 2), max_cut)
        sign = float(np.sign(cross2d(vect1, vect2)))
        arc = ArcBetweenPoints(v2 - vect1 * cut, v2 + vect2 * cut, angle=sign * angle, num_components=3)
        path.add_line_to(arc.get_start())
        path.append_points(arc.points)
    path.add_line_to(pts[-1])
    return path


def length_alpha_to_curve_alpha(vmobject: VMobject, alpha: float) -> float:
    """
    Convert a proportion of arc length into the proportion of curve count
    that ``pointwise_become_partial`` expects, so trims and partial draws
    land at the same spot along wires whose curves differ in length.
    """
    num_curves = vmobject.get_num_curves()
    if num_curves == 0 or alpha <= 0:
        return 0.0
    if alpha >= 1:
        return 1.0
    lengths = [vmobject.get_nth_curve_length(n) for n in range(num_curves)]
    target = alpha * sum(lengths)
    accumulated = 0.0
    for i, length in enumerate(lengths):
        if accumulated + length >= target:
            residue = (target - accumulated) / length if length > 0 else 0.0
            return (i + residue) / num_curves
        accumulated += length
    return 1.0


# Mobjects


class Route(TipableVMobject):
    """
    The drawn path of a connector. Two points give a line (or an arc when
    ``path_arc`` is non-zero); more give a polyline with rounded corners.
    """
    def __init__(
        self,
        points: Sequence[Point3D],
        path_arc: float = 0.0,
        corner_radius: float = 0.2,
        tip_length: float = 0.2,
        **kwargs
    ):
        super().__init__(tip_length=tip_length, **kwargs)
        self.route_points = [np.array(p, dtype=float) for p in points]
        self.path_arc = path_arc
        self.corner_radius = corner_radius
        self.set_points_by_route()

    def set_points_by_route(self) -> Self:
        pts = self.route_points
        self.clear_points()
        if len(pts) == 2:
            if self.path_arc:
                arc = ArcBetweenPoints(pts[0], pts[1], angle=self.path_arc)
                self.set_points(arc.points)
            else:
                self.start_new_path(pts[0])
                self.add_line_to(pts[1])
        else:
            self.set_points(_round_open_corners(pts, self.corner_radius).points)
        return self

    def get_unpositioned_tip(self, tip_shape=None, tip_length=None, tip_width=None) -> ArrowTip:
        return super().get_unpositioned_tip(
            tip_shape=tip_shape,
            tip_length=_pick(tip_length, self.tip_length),
            tip_width=_pick(tip_width, self.tip_length),
        )

    def reset_endpoints_based_on_tip(self, tip: ArrowTip, at_start: bool) -> Self:
        """
        Trim the path back to the tip's base by arc length. The base class
        stretches the whole path between two points instead, which is only
        right for a single straight segment.
        """
        arc_len = self.get_arc_length()
        if arc_len == 0:
            return self
        trim = min(tip.length / arc_len, 0.45)
        if at_start:
            self.pointwise_become_partial(self, length_alpha_to_curve_alpha(self, trim), 1.0)
        else:
            self.pointwise_become_partial(self, 0.0, length_alpha_to_curve_alpha(self, 1 - trim))
        return self

    def get_travel_path(self) -> VMobject:
        """A tip-less copy of the path, for things that move along it."""
        path = VMobject()
        path.set_points(self.points.copy())
        path.set_stroke(
            self.get_stroke_color(), width=self.get_stroke_width(),
            opacity=self.get_stroke_opacity(),
        )
        path.set_fill(opacity=0)
        return path

    def reversed(self) -> Route:
        route = Route(
            self.route_points[::-1],
            path_arc=-self.path_arc,
            corner_radius=self.corner_radius,
            tip_length=self.tip_length,
        )
        route.set_stroke(self.get_stroke_color(), width=self.get_stroke_width())
        return route


class Connector(VGroup):
    """
    A wire from ``start`` to ``end`` (mobjects or points), routed between their
    ports and optionally tipped, dashed and labelled.

    ``route``: ``"straight"``, ``"arc"`` (bent by ``path_arc``), ``"orthogonal"``
    (axis-aligned with rounded corners), ``"loop"`` (out and back, for self
    messages), or ``"auto"`` (straight unless ``path_arc`` is set).

    ``start_dir``/``end_dir`` pick which side of each mobject the wire leaves
    from and arrives at; by default the side facing the other end. ``offset``
    slides both ports along their edges so parallel lanes stay apart.

    ``tip_shape`` is any manim ``ArrowTip`` class (filled triangle by default;
    ``ArrowTriangleTip`` gives the open head of an asynchronous message).

    Rerouting when the endpoints move is opt-in: call ``attach()``.
    """
    def __init__(
        self,
        start: Mobject | Point3D,
        end: Mobject | Point3D,
        route: str = "auto",
        path_arc: float = 0.0,
        start_dir: Vector3D | None = None,
        end_dir: Vector3D | None = None,
        offset: float = 0.0,
        buff: float = SMALL_BUFF,
        tip: str | None = "end",
        tip_length: float | None = None,
        tip_shape: type[ArrowTip] | None = None,
        dashed: bool = False,
        corner_radius: float | None = None,
        label: str | VMobject | None = None,
        label_kwargs: dict | None = None,
        color: ManimColor | None = None,
        stroke_width: float | None = None,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        if route not in ROUTE_KINDS:
            raise ValueError(f"route must be one of {ROUTE_KINDS}")
        if tip not in TIP_PLACEMENTS:
            raise ValueError(f"tip must be one of {TIP_PLACEMENTS}")
        style = _resolve_style(style)
        self.style = style
        self.start_mob = start
        self.end_mob = end
        self.route_kind = route
        self.path_arc = path_arc
        self.start_dir = None if start_dir is None else np.array(start_dir, dtype=float)
        self.end_dir = None if end_dir is None else np.array(end_dir, dtype=float)
        self.offset = offset
        self.buff = buff
        self.tip_placement = tip if tip != "none" else None
        self.tip_length = _pick(tip_length, style.edge_tip_length)
        self.tip_shape = _pick(tip_shape, ArrowTriangleFilledTip)
        self.dashed = dashed
        self.corner_radius = _pick(corner_radius, style.edge_corner_radius)
        self.color = _pick(color, style.edge_color)
        self.stroke_width = _pick(stroke_width, style.edge_stroke_width)

        self.route = self._build_route()
        self.dashes = self._build_dashes()
        self.label = None
        self.label_proportion = 0.5
        self.label_direction = None
        self.label_buff = SMALL_BUFF
        self.add(self.route)
        if self.dashes is not None:
            self.add(self.dashes)
        self.set_z_index(Z_EDGE)
        if label is not None:
            self.add_label(label, **(label_kwargs or dict()))

    # Geometry
    def _endpoints(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Start point, its outward direction, end point, its outward direction."""
        c0 = _port(self.start_mob, None)
        c1 = _port(self.end_mob, None)
        d0 = self.start_dir if self.start_dir is not None else _dominant_direction(c1 - c0)
        d1 = self.end_dir if self.end_dir is not None else _dominant_direction(c0 - c1)
        if self.route_kind == "loop":
            d1 = d0
        p0 = _port(self.start_mob, d0, self.offset)
        p1 = _port(self.end_mob, d1, -self.offset if self.route_kind == "loop" else self.offset)
        return p0, d0, p1, d1

    def _route_points(self) -> list[np.ndarray]:
        p0, d0, p1, d1 = self._endpoints()
        kind = self.route_kind
        if kind == "auto":
            kind = "arc" if self.path_arc else "straight"
        if kind in ("straight", "arc"):
            along = normalize(p1 - p0) if _norm(p1 - p0) > 0 else d0
            return [p0 + self.buff * along, p1 - self.buff * along]
        if kind == "loop":
            return _loop_waypoints(p0 + self.buff * d0, p1 + self.buff * d1, d0)
        stub = self.corner_radius + 0.2
        return _orthogonal_waypoints(p0 + self.buff * d0, d0, p1 + self.buff * d1, d1, stub=stub)

    def _build_route(self) -> Route:
        route = Route(
            self._route_points(),
            path_arc=self.path_arc,
            corner_radius=self.corner_radius,
            tip_length=self.tip_length,
            stroke_color=self.color,
            stroke_width=self.stroke_width,
            fill_opacity=0.0,
        )
        if self.tip_placement in ("end", "both"):
            route.add_tip(tip_shape=self.tip_shape)
        if self.tip_placement in ("start", "both"):
            route.add_tip(tip_shape=self.tip_shape, at_start=True)
        for tip in route.get_tips():
            tip.set_color(self.color)
        if self.dashed:
            # The solid path stays as the thing packets travel along, unseen
            route.set_stroke(opacity=0, family=False)
        return route

    def _build_dashes(self) -> VMobject | None:
        if not self.dashed:
            return None
        path = self.route.get_travel_path().set_stroke(opacity=1)
        length = path.get_arc_length()
        num_dashes = max(2, int(length / (2 * self.style.container_dash_length)))
        dashes = DashedVMobject(path, num_dashes=num_dashes)
        dashes.set_stroke(self.color, width=self.stroke_width)
        dashes.set_fill(opacity=0)
        return dashes

    def reroute(self) -> Self:
        self.route.become(self._build_route())
        if self.dashes is not None:
            self.dashes.become(self._build_dashes())
        if self.label is not None:
            self._place_label()
        return self

    def attach(self) -> Self:
        self.add_updater(lambda c: c.reroute())
        return self

    def detach(self) -> Self:
        self.clear_updaters()
        return self

    # Points along the wire
    def get_point(self, proportion: float) -> Point3D:
        return self.route.get_travel_path().point_from_proportion(proportion)

    def get_start(self) -> Point3D:
        return self.route.get_start()

    def get_end(self) -> Point3D:
        return self.route.get_end()

    def get_reverse_route(self) -> Route:
        return self.route.reversed()

    def get_travel_path(self, reverse: bool = False) -> VMobject:
        path = self.route.get_travel_path()
        if reverse:
            path.reverse_points()
        return path

    # Labels
    def add_label(
        self,
        text: str | VMobject,
        proportion: float = 0.5,
        direction: Vector3D | None = None,
        buff: float = SMALL_BUFF,
        font_size: int | None = None,
    ) -> VGroup:
        """
        A label on the wire. With no ``direction`` it sits on the wire inside
        a background patch that hides the stroke behind it; with one, it sits
        beside the wire with a dark backstroke instead.
        """
        if isinstance(text, VMobject):
            text_mob = text
        else:
            text_mob = _make_text(text, font_size=_pick(font_size, self.style.small_font_size), style=self.style)
        if direction is None:
            text_mob.set_stroke(width=0, background=True)
            label = VGroup(BackgroundRectangle(text_mob, buff=0.6 * SMALL_BUFF), text_mob)
        else:
            _backstroke(text_mob)
            label = VGroup(text_mob)
        if self.label is not None:
            self.remove(self.label)
        self.label = label
        self.label_text = text_mob
        self.label_proportion = proportion
        self.label_direction = None if direction is None else np.array(direction, dtype=float)
        self.label_buff = buff
        self._place_label()
        label.set_z_index(Z_EDGE_LABEL)
        self.add(label)
        return label

    def move_label(
        self,
        proportion: float = 0.5,
        direction: Vector3D | None = None,
        buff: float = SMALL_BUFF,
    ) -> VGroup:
        """
        Put the existing label somewhere else on or beside the wire, with the
        same meaning of ``direction`` as ``add_label``. ``place_labels`` in
        ``layout`` calls this while searching for a clear spot.
        """
        if self.label is None:
            raise ValueError("This connector has no label to move")
        return self.add_label(self.label_text, proportion=proportion, direction=direction, buff=buff)

    def _place_label(self) -> None:
        point = self.get_point(self.label_proportion)
        if self.label_direction is None:
            self.label.move_to(point)
        else:
            self.label.next_to(point, self.label_direction, buff=self.label_buff)
