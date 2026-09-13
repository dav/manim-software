"""
Layered layout without rendering: layers follow the flow, pins and cycles
are handled, container members stay together, boxes never touch, every
direction works, and SystemDiagram.layout leaves containers and wires
consistent with where the components ended up.
"""
import numpy as np
import pytest
from manim import DOWN
from manim import LEFT
from manim import RIGHT
from manim import UP

from manim_software import Component
from manim_software import Container
from manim_software import SystemDiagram
from manim_software import assign_layers
from manim_software import force_layout
from manim_software import layered_layout
from manim_software import order_layers
from manim_software.layout import _overlap_area
from manim_software.layout import _rect


NODES = ["user", "browser", "gateway", "service", "cache", "db"]
EDGES = [("user", "browser"), ("browser", "gateway"), ("gateway", "service"), ("service", "cache"), ("service", "db")]
SIZES = {n: (1.8, 1.0) for n in NODES}


def _boxes(positions, sizes):
    return {
        n: (p[0] - sizes[n][0] / 2, p[1] - sizes[n][1] / 2, p[0] + sizes[n][0] / 2, p[1] + sizes[n][1] / 2)
        for n, p in positions.items()
    }


def _no_overlap(boxes):
    names = list(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert _overlap_area(boxes[a], boxes[b]) == 0, (a, b)


def test_layers_follow_the_longest_path():
    layers = assign_layers(NODES, EDGES)
    assert layers == {"user": 0, "browser": 1, "gateway": 2, "service": 3, "cache": 4, "db": 4}


def test_pinned_layers_win_and_push_downstream_nodes():
    layers = assign_layers(NODES, EDGES, fixed={"gateway": 4})
    assert layers["gateway"] == 4
    assert layers["service"] == 5 and layers["cache"] == 6
    assert layers["browser"] == 1


def test_cycles_and_self_loops_do_not_break_layering():
    layers = assign_layers(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a"), ("b", "b")])
    assert layers["a"] == 0
    assert sorted(layers.values()) == [0, 1, 2]


def test_isolated_nodes_sit_in_the_first_layer():
    layers = assign_layers(["a", "b", "loner"], [("a", "b")])
    assert layers["loner"] == 0


def test_ordering_keeps_container_members_together():
    nodes = ["hub", "x1", "y1", "x2", "y2"]
    edges = [("hub", n) for n in nodes[1:]]
    layers = assign_layers(nodes, edges)
    order = order_layers(nodes, edges, layers, groups={"x1": "X", "x2": "X", "y1": "Y", "y2": "Y"})
    second = order[1]
    groups = ["X" if n.startswith("x") else "Y" for n in second]
    assert groups in (["X", "X", "Y", "Y"], ["Y", "Y", "X", "X"])


def test_ordering_reduces_crossings():
    nodes = ["a", "b", "c", "d"]
    edges = [("a", "d"), ("b", "c")]       # given in a crossing order
    layers = assign_layers(nodes, edges)
    order = order_layers(nodes, edges, layers)
    top = order[0]
    bottom = order[1]
    assert top.index("a") < top.index("b")
    assert bottom.index("d") < bottom.index("c")


def test_layered_positions_do_not_touch_and_run_in_direction():
    positions = layered_layout(NODES, EDGES, SIZES, direction=RIGHT, layer_gap=1.0, node_gap=0.4)
    _no_overlap(_boxes(positions, SIZES))
    xs = {n: positions[n][0] for n in NODES}
    assert xs["user"] < xs["browser"] < xs["gateway"] < xs["service"] < xs["cache"]
    assert np.isclose(xs["cache"], xs["db"])
    assert np.isclose(positions["cache"][1] - positions["db"][1], 1.0 + 0.4) or np.isclose(positions["db"][1] - positions["cache"][1], 1.0 + 0.4)
    assert np.isclose(xs["browser"] - xs["user"], 1.8 + 1.0)
    centre = 0.5 * (np.min(list(positions.values()), axis=0) + np.max(list(positions.values()), axis=0))
    assert np.allclose(centre, 0)


@pytest.mark.parametrize("direction, axis, sign", [(RIGHT, 0, 1), (LEFT, 0, -1), (DOWN, 1, -1), (UP, 1, 1)])
def test_every_direction_lays_layers_along_it(direction, axis, sign):
    positions = layered_layout(NODES, EDGES, SIZES, direction=direction)
    _no_overlap(_boxes(positions, SIZES))
    assert sign * (positions["service"][axis] - positions["user"][axis]) > 0


def test_group_gap_separates_containers_within_a_layer():
    nodes = ["hub", "x", "y"]
    edges = [("hub", "x"), ("hub", "y")]
    sizes = {n: (1.0, 1.0) for n in nodes}
    plain = layered_layout(nodes, edges, sizes, node_gap=0.5)
    spaced = layered_layout(nodes, edges, sizes, node_gap=0.5, groups={"x": "X", "y": "Y"}, group_gap=1.0)
    assert np.isclose(abs(plain["x"][1] - plain["y"][1]), 1.5)
    assert np.isclose(abs(spaced["x"][1] - spaced["y"][1]), 2.5)


def test_force_layout_fills_the_requested_extent():
    positions = force_layout(NODES, EDGES, SIZES, width=8.0, height=4.0, seed=1)
    points = np.array(list(positions.values()))
    assert np.isclose(np.ptp(points[:, 0]), 8.0)
    assert np.isclose(np.ptp(points[:, 1]), 4.0)
    assert len(positions) == len(NODES)


def _system():
    system = SystemDiagram()
    for name in NODES:
        system.add_component(name, Component(name.title(), width=1.8, height=1.0))
    system.add_container(Container(system["user"], system["browser"], title="Client"))
    system.add_container(Container(system["service"], system["cache"], system["db"], title="Backend"))
    for src, dst in EDGES:
        system.connect(src, dst, label=f"{src}-{dst}")
    return system


def test_system_layout_moves_everything_consistently():
    system = _system()
    assert system.layout() is system
    boxes = {name: _rect(comp.box) for name, comp in system.components.items()}
    _no_overlap(boxes)
    for container in system.containers:
        frame = _rect(container.frame)
        for member in container.members:
            assert _overlap_area(frame, _rect(member)) > 0
    client, backend = (_rect(c.frame) for c in system.containers)
    assert _overlap_area(client, backend) == 0
    for (src, dst), conn in system.connectors.items():
        assert np.allclose(conn.get_start(), system[src].get_port_toward(system[dst]) + 0.0, atol=0.3)
        assert conn.label is not None
        for name, box in boxes.items():
            assert _overlap_area(_rect(conn.label), box) == 0, (src, dst, name)


def test_system_layout_accepts_pins_and_force():
    system = _system()
    system.layout(layers={"cache": 3})
    assert np.isclose(system["cache"].get_center()[0], system["service"].get_center()[0])
    forced = _system().layout(kind="force", width=9.0, height=4.0)
    assert forced is not None
    with pytest.raises(ValueError):
        _system().layout(kind="circular")
