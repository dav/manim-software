"""
Where things go: laying out a diagram's components, and keeping labels off
the things they label.

``layered_layout`` places named boxes in layers along a direction, the way a
request flows left to right: layers by longest path from the sources, order
within a layer by the barycenter heuristic with members of one container kept
together, and spacing from the boxes' real sizes. ``force_layout`` is the
spring alternative for graphs without a flow. ``SystemDiagram.layout`` wraps
them, then refits containers, reroutes wires and runs ``place_labels``.

``place_labels`` walks a diagram's wire labels and moves each one to the
best of a few candidate spots: on the wire at its middle, beside it on either
side, or further along it. A spot is judged by the boxes it would cover
(components, container titles, labels already placed) and, as a tie-break,
by the wires and container frames it would cross.

Everything here is arithmetic over names, sizes and bounding boxes, with no
rendering, so it is cheap enough to run after every change and can be unit
tested. networkx comes with manim.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx
import numpy as np

from manim import DOWN
from manim import LEFT
from manim import RIGHT
from manim import SMALL_BUFF
from manim import UP
from manim import Mobject
from manim.utils.space_ops import normalize

if TYPE_CHECKING:
    from typing import Hashable
    from typing import Iterable
    from typing import Mapping
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


# Component layout


def _break_cycles(graph: nx.DiGraph) -> nx.DiGraph:
    """A copy of ``graph`` with one edge per cycle dropped, so layers can be assigned."""
    dag = graph.copy()
    while not nx.is_directed_acyclic_graph(dag):
        cycle = nx.find_cycle(dag)
        src, dst = cycle[-1][:2]
        dag.remove_edge(src, dst)
    return dag


def assign_layers(
    nodes: Sequence[str],
    edges: Sequence[tuple[str, str]],
    fixed: Mapping[str, int] | None = None,
) -> dict[str, int]:
    """
    Each node's layer: the length of the longest path reaching it from a
    source, so every wire runs forward at least one layer. ``fixed`` pins
    nodes to layers of the caller's choosing; nodes downstream of a pinned
    node still land after it. Cycles are cut at one edge each.
    """
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from((s, d) for s, d in edges if s != d)
    dag = _break_cycles(graph)
    fixed = dict(fixed or {})
    layers = {node: 0 for node in nodes}
    for node in nx.topological_sort(dag):
        if node in fixed:
            layers[node] = fixed[node]
            continue
        preds = list(dag.predecessors(node))
        if preds:
            layers[node] = max(layers[p] + 1 for p in preds)
    return layers


def order_layers(
    nodes: Sequence[str],
    edges: Sequence[tuple[str, str]],
    layers: Mapping[str, int],
    groups: Mapping[str, Hashable] | None = None,
    sweeps: int = 4,
) -> dict[int, list[str]]:
    """
    Nodes of each layer in top-to-bottom order, by the barycenter heuristic:
    a few sweeps forward and back, each sorting a layer by the mean position
    of its neighbours in the previous one. Nodes sharing a ``groups`` value
    (a container) stay adjacent, ordered by their group's mean position.
    """
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from((s, d) for s, d in edges if s != d)
    groups = dict(groups or {})
    by_layer: dict[int, list[str]] = {}
    for node in nodes:
        by_layer.setdefault(layers[node], []).append(node)
    index = {node: i for layer in by_layer.values() for i, node in enumerate(layer)}

    def barycenter(node: str, neighbours: Iterable[str]) -> float:
        positions = [index[n] for n in neighbours if n in index]
        return float(np.mean(positions)) if positions else float(index[node])

    def resort(layer_nodes: list[str], bary: dict[str, float]) -> list[str]:
        grouped: dict[Hashable, list[float]] = {}
        first_seen: dict[Hashable, int] = {}
        for i, node in enumerate(layer_nodes):
            key = groups.get(node)
            if key is not None:
                grouped.setdefault(key, []).append(bary[node])
                first_seen.setdefault(key, i)
        means = {key: float(np.mean(values)) for key, values in grouped.items()}

        def sort_key(node: str):
            key = groups.get(node)
            if key is None:
                return (bary[node], -1, bary[node], layer_nodes.index(node))
            # Same mean as another group: the group seen first stays first, whole
            return (means[key], first_seen[key], bary[node], layer_nodes.index(node))
        return sorted(layer_nodes, key=sort_key)

    ordered = sorted(by_layer)
    for sweep in range(sweeps):
        forward = sweep % 2 == 0
        sequence = ordered[1:] if forward else list(reversed(ordered[:-1]))
        for depth in sequence:
            neighbours_of = graph.predecessors if forward else graph.successors
            bary = {node: barycenter(node, neighbours_of(node)) for node in by_layer[depth]}
            by_layer[depth] = resort(by_layer[depth], bary)
            for i, node in enumerate(by_layer[depth]):
                index[node] = i
    return {depth: by_layer[depth] for depth in ordered}


def _axes(direction: Vector3D) -> tuple[np.ndarray, np.ndarray]:
    """Unit vectors along the layers and across them (across runs top-to-bottom, or left-to-right)."""
    along = normalize(np.array(direction, dtype=float))
    if abs(along[0]) >= abs(along[1]):
        return along, DOWN
    return along, RIGHT


def layered_layout(
    nodes: Sequence[str],
    edges: Sequence[tuple[str, str]],
    sizes: Mapping[str, tuple[float, float]],
    direction: Vector3D = RIGHT,
    layer_gap: float = 1.5,
    node_gap: float = 0.5,
    groups: Mapping[str, Hashable] | None = None,
    group_gap: float = 0.0,
    layers: Mapping[str, int] | None = None,
    sweeps: int = 4,
) -> dict[str, np.ndarray]:
    """
    Centre points for boxes laid out in layers along ``direction``.

    ``sizes`` are each box's (width, height). Layers sit ``layer_gap``
    apart edge to edge; within a layer boxes sit ``node_gap`` apart, with
    ``group_gap`` more between boxes of different ``groups`` (room for
    container frames). ``layers`` pins nodes to layers. The result is
    centred on the origin.
    """
    nodes = list(nodes)
    depth = assign_layers(nodes, edges, layers)
    order = order_layers(nodes, edges, depth, groups, sweeps)
    along, across = _axes(direction)
    horizontal = abs(along[0]) >= abs(along[1])
    groups = dict(groups or {})

    def extent(node: str) -> tuple[float, float]:
        width, height = sizes[node]
        return (width, height) if horizontal else (height, width)   # (along, across)

    positions: dict[str, np.ndarray] = {}
    offset = 0.0
    for depth_index, layer_nodes in order.items():
        thickness = max(extent(n)[0] for n in layer_nodes)
        centre_along = offset + 0.5 * thickness
        # Stack across, then centre the stack
        cursor = 0.0
        centres = []
        previous = None
        for node in layer_nodes:
            if previous is not None:
                cursor += node_gap
                if groups.get(previous) != groups.get(node) and (groups.get(previous) is not None or groups.get(node) is not None):
                    cursor += group_gap
            size_across = extent(node)[1]
            centres.append(cursor + 0.5 * size_across)
            cursor += size_across
            previous = node
        middle = 0.5 * cursor
        for node, centre_across in zip(layer_nodes, centres):
            positions[node] = centre_along * along + (centre_across - middle) * across
        offset += thickness + layer_gap

    if positions:
        centroid = 0.5 * (np.min(list(positions.values()), axis=0) + np.max(list(positions.values()), axis=0))
        for node in positions:
            positions[node] = positions[node] - centroid
    return positions


def force_layout(
    nodes: Sequence[str],
    edges: Sequence[tuple[str, str]],
    sizes: Mapping[str, tuple[float, float]],
    width: float = 10.0,
    height: float = 5.0,
    seed: int = 0,
    **spring_kwargs
) -> dict[str, np.ndarray]:
    """
    Centre points from networkx's spring layout, scaled to fill ``width`` by
    ``height``. For graphs with no obvious flow; unlike ``layered_layout``
    it does not promise boxes will not touch.
    """
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from((s, d) for s, d in edges if s != d)
    raw = nx.spring_layout(graph, seed=seed, **spring_kwargs)
    points = np.array([raw[n] for n in nodes]) if nodes else np.zeros((0, 2))
    if len(points) > 1:
        span = np.ptp(points, axis=0)
        span[span == 0] = 1.0
        points = (points - points.mean(axis=0)) / span * np.array([width, height])
    return {node: np.array([p[0], p[1], 0.0]) for node, p in zip(nodes, points)}
