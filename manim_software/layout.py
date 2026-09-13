"""
Placement passes that keep labels off the things they label.

``place_labels`` walks a diagram's wire labels and moves each one to the
best of a few candidate spots: on the wire at its middle, beside it on either
side, or further along it. A spot is judged by the boxes it would cover
(components, container titles, labels already placed) and, as a tie-break,
by the wires and container frames it would cross. It is a search over
bounding boxes with no rendering, so it is cheap enough to run after every
layout change and can be unit tested.

Laying out the components themselves is the next step, and this module is
where it will live.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from manim import DOWN
from manim import LEFT
from manim import RIGHT
from manim import SMALL_BUFF
from manim import UP
from manim import Mobject
from manim.utils.space_ops import normalize

if TYPE_CHECKING:
    from typing import Iterable
    from typing import Sequence

    from manim.typing import Vector3D

    from manim_software.connectors import Connector


Rect = "tuple[float, float, float, float]"    # x0, y0, x1, y1

DEFAULT_PROPORTIONS = (0.5, 0.35, 0.65, 0.25, 0.75, 0.15, 0.85)
PATH_SAMPLES = 40


# Bounding-box arithmetic


def _rect(mob: Mobject, margin: float = 0.0) -> tuple[float, float, float, float]:
    x0, y0, _ = mob.get_corner(DOWN + LEFT)
    x1, y1, _ = mob.get_corner(UP + RIGHT)
    return (x0 - margin, y0 - margin, x1 + margin, y1 + margin)


def _piece_rects(mob: Mobject, margin: float = 0.0) -> list:
    """
    One rect per drawn leaf of ``mob`` rather than its whole bounding box, so
    a packet's halo and its label count separately and a label can tuck in
    beside one without being charged for the other.
    """
    leaves = [m for m in mob.get_family() if m.has_points() and not m.submobjects]
    if not leaves:
        return [_rect(mob, margin)]
    return [_rect(leaf, margin) for leaf in leaves]


def _overlap_area(a, b) -> float:
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, width) * max(0.0, height)


def _contains(outer, inner) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]


def _crosses_frame(rect, frame) -> bool:
    """Whether ``rect`` straddles the edge of ``frame`` (rather than sitting inside or outside it)."""
    return _overlap_area(rect, frame) > 0 and not _contains(frame, rect)


def _points_inside(points: np.ndarray, rect) -> int:
    inside = (
        (points[:, 0] >= rect[0]) & (points[:, 0] <= rect[2])
        & (points[:, 1] >= rect[1]) & (points[:, 1] <= rect[3])
    )
    return int(np.count_nonzero(inside))


def _samples(connector: Connector, n: int = PATH_SAMPLES) -> np.ndarray:
    path = connector.get_travel_path()
    return np.array([path.point_from_proportion(t) for t in np.linspace(0.0, 1.0, n)])


def _side(connector: Connector, proportion: float) -> np.ndarray:
    """The unit normal to the wire at ``proportion``, snapped to an axis when nearly aligned."""
    path = connector.get_travel_path()
    eps = 0.01
    before = path.point_from_proportion(max(0.0, proportion - eps))
    after = path.point_from_proportion(min(1.0, proportion + eps))
    tangent = normalize(after - before)
    normal = np.array([-tangent[1], tangent[0], 0.0])
    if abs(normal[0]) < 0.3:
        return UP if normal[1] >= 0 else DOWN
    if abs(normal[1]) < 0.3:
        return RIGHT if normal[0] >= 0 else LEFT
    return normal


# The search


def label_candidates(
    connector: Connector,
    proportions: Sequence[float] = DEFAULT_PROPORTIONS,
) -> list[tuple[float, Vector3D | None]]:
    """
    Where a wire label may go, best first: at each proportion along the
    wire, on the wire itself, then beside it on either side.
    """
    candidates = []
    for proportion in proportions:
        side = _side(connector, proportion)
        candidates.append((proportion, None))
        candidates.append((proportion, side))
        candidates.append((proportion, -side))
    return candidates


def place_labels(
    connectors: Iterable[Connector],
    obstacles: Iterable[Mobject] = (),
    frames: Iterable[Mobject] = (),
    margin: float = 0.05,
    buff: float = SMALL_BUFF,
    proportions: Sequence[float] = DEFAULT_PROPORTIONS,
) -> dict[Connector, tuple[float, Vector3D | None]]:
    """
    Move every labelled connector's label to the candidate that covers the
    least of ``obstacles`` (and of labels placed before it), breaking ties by
    how many other wires and ``frames`` (container boundaries) it crosses,
    then by candidate order. Labels are visited in the order given, so put
    the ones that matter most first. Returns each connector's chosen
    ``(proportion, direction)``; ``direction`` ``None`` means on the wire.
    """
    connectors = [c for c in connectors]
    labelled = [c for c in connectors if c.label is not None]
    hard = [rect for o in obstacles for rect in _piece_rects(o, margin)]
    frame_rects = [_rect(f) for f in frames]
    samples = {c: _samples(c) for c in connectors}
    chosen: dict[Connector, tuple[float, Vector3D | None]] = dict()
    for connector in labelled:
        best = None
        for index, (proportion, direction) in enumerate(label_candidates(connector, proportions)):
            connector.move_label(proportion, direction, buff=buff)
            rect = _rect(connector.label, margin)
            covered = sum(_overlap_area(rect, h) for h in hard)
            crossings = sum(_points_inside(samples[other], rect) for other in connectors if other is not connector)
            crossings += sum(_crosses_frame(rect, frame) for frame in frame_rects)
            key = (round(covered, 6), crossings, index)
            if best is None or key < best[0]:
                best = (key, proportion, direction)
        _, proportion, direction = best
        connector.move_label(proportion, direction, buff=buff)
        hard.extend(_piece_rects(connector.label, margin))
        chosen[connector] = (proportion, direction)
    return chosen
