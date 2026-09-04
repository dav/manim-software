"""
Sequence diagrams: participants across the top, lifelines hanging down,
messages between them one row at a time.

``Message`` records are plain data, so the same list can drive a
``SystemDiagram`` (packets travelling wires) and a ``SequenceDiagram``
(arrows between lifelines); ``message_animation`` does both at once.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from manim import RIGHT
from manim import UP
from manim import AnimationGroup
from manim import ArrowTriangleTip
from manim import DashedLine
from manim import GrowFromPoint
from manim import Rectangle
from manim import VGroup

from manim_software.components import Component
from manim_software.components import SystemDiagram
from manim_software.connectors import Connector
from manim_software.packets import FadeInAfter
from manim_software.packets import Packet
from manim_software.packets import Send
from manim_software.style import Z_NODE
from manim_software.style import _pick
from manim_software.style import _resolve_style

if TYPE_CHECKING:
    from typing import Self
    from typing import Sequence

    from manim import Animation

    from manim_software.style import DiagramStyle


MESSAGE_KINDS = ("sync", "reply", "async")


def _label_text(component: Component) -> str:
    """A component's label as written (manim's ``Text.text`` drops the spaces)."""
    label = component.label
    return getattr(label, "original_text", getattr(label, "text", ""))


@dataclass
class Message:
    src: str
    dst: str
    label: str = ""
    kind: str = "sync"      # sync | reply | async
    packet_label: str | None = None

    def __post_init__(self):
        if self.kind not in MESSAGE_KINDS:
            raise ValueError(f"kind must be one of {MESSAGE_KINDS}")


class SequenceDiagram(VGroup):
    """
    Participants may be names, ``(key, display name)`` pairs, or Components
    (their label text becomes the key). ``message`` draws one arrow on the
    next free row and returns it as a ``Connector``, so the usual creation
    animations and ``Send`` apply; ``activate`` draws an activation bar.
    """
    def __init__(
        self,
        participants: Sequence[str | tuple[str, str] | Component],
        spacing: float = 2.5,
        n_rows: int = 8,
        row_height: float = 0.6,
        header_height: float = 0.8,
        header_width: float = 1.4,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        style = _resolve_style(style)
        self.style = style
        self.spacing = spacing
        self.row_height = row_height
        self.n_rows = n_rows
        self.row = 0

        self.keys: list[str] = []
        self.headers = VGroup()
        for i, participant in enumerate(participants):
            key, display = self._key_and_display(participant)
            header = Component(
                display,
                font_size=style.small_font_size,
                min_width=header_width,
                min_height=header_height,
                padding=0.12,
                style=style,
            )
            header.move_to(i * spacing * RIGHT)
            self.keys.append(key)
            self.headers.add(header)

        self.lifelines = VGroup(*(self._build_lifeline(i) for i in range(len(self.keys))))
        self.lifelines.set_z_index(Z_NODE - 1)
        self.messages = VGroup()
        self.activations = VGroup()
        self.records: list[tuple[int, Message, Connector]] = []
        self.add(self.lifelines, self.activations, self.headers, self.messages)
        self.center()

    @staticmethod
    def _key_and_display(participant) -> tuple[str, str]:
        if isinstance(participant, Component):
            text = _label_text(participant)
            return text, text
        if isinstance(participant, tuple):
            return participant
        return participant, participant

    # Geometry
    def _top_y(self) -> float:
        return self.headers.get_bottom()[1]

    def row_y(self, row: int) -> float:
        return self._top_y() - (row + 1) * self.row_height

    def _bottom_y(self, n_rows: int | None = None) -> float:
        return self.row_y(_pick(n_rows, self.n_rows) - 1) - 0.5 * self.row_height

    def _index(self, key: str | int | Component) -> int:
        if isinstance(key, int):
            return key
        if isinstance(key, Component):
            key = _label_text(key)
        return self.keys.index(key)

    def get_participant(self, key: str | int | Component) -> Component:
        return self.headers[self._index(key)]

    def get_lifeline_x(self, key: str | int | Component) -> float:
        return self.headers[self._index(key)].get_center()[0]

    def _build_lifeline(self, index: int) -> DashedLine:
        header = self.headers[index]
        x = header.get_center()[0]
        top = np.array([x, self._top_y(), 0])
        bottom = np.array([x, self._bottom_y(), 0])
        line = DashedLine(top, bottom, dash_length=self.style.container_dash_length)
        line.set_stroke(self.style.lifeline_color, self.style.container_stroke_width)
        return line

    def fit_rows(self, n_rows: int | None = None) -> Self:
        """Stretch the lifelines to cover every row used so far (or ``n_rows``)."""
        self.n_rows = _pick(n_rows, max(self.n_rows, self.row))
        for i, line in enumerate(self.lifelines):
            line.become(self._build_lifeline(i))
        return self

    # Content
    def message(
        self,
        src: str | int | Component,
        dst: str | int | Component,
        label: str = "",
        kind: str = "sync",
        row: int | None = None,
    ) -> Connector:
        if kind not in MESSAGE_KINDS:
            raise ValueError(f"kind must be one of {MESSAGE_KINDS}")
        if row is None:
            row = self.row
        self.row = max(self.row, row + 1)
        if self.row > self.n_rows:
            self.fit_rows(self.row)
        x0, x1 = self.get_lifeline_x(src), self.get_lifeline_x(dst)
        y = self.row_y(row)
        common = dict(
            dashed=(kind == "reply"),
            tip_shape=(ArrowTriangleTip if kind == "async" else None),
            buff=0.0,
            style=self.style,
        )
        if np.isclose(x0, x1):
            arrow = Connector(
                [x0, y + 0.2 * self.row_height, 0], [x0, y - 0.3 * self.row_height, 0],
                route="loop", start_dir=RIGHT, **common
            )
            if label:
                arrow.add_label(label, proportion=0.5, direction=RIGHT, buff=0.08)
        else:
            arrow = Connector([x0, y, 0], [x1, y, 0], route="straight", **common)
            if label:
                arrow.add_label(label, proportion=0.5, direction=UP, buff=0.05)
        self.messages.add(arrow)
        self.records.append((row, Message(str(src), str(dst), label, kind), arrow))
        return arrow

    def message_from(self, msg: Message) -> Connector:
        return self.message(msg.src, msg.dst, msg.label, msg.kind)

    def activate(self, key: str | int | Component, from_row: int, to_row: int, width: float = 0.18) -> Rectangle:
        top = self.row_y(from_row) + 0.35 * self.row_height
        bottom = self.row_y(to_row) - 0.35 * self.row_height
        bar = Rectangle(width=width, height=top - bottom)
        bar.set_fill(self.style.activation_fill, opacity=1.0)
        bar.set_stroke(self.style.lifeline_color, 1.0)
        bar.move_to([self.get_lifeline_x(key), (top + bottom) / 2, 0])
        bar.set_z_index(Z_NODE)
        self.activations.add(bar)
        return bar

    def get_messages(self) -> VGroup:
        return self.messages


def message_animation(
    msg: Message,
    system: SystemDiagram | None = None,
    sequence: SequenceDiagram | None = None,
    packet: Packet | None = None,
    run_time: float = 1.0,
    **send_kwargs
) -> Animation:
    """
    One message, played in whichever views are given: a packet along the
    system's connector, and/or a new arrow growing in the sequence diagram.
    """
    if system is None and sequence is None:
        raise ValueError("message_animation needs a system, a sequence diagram, or both")
    anims = []
    if system is not None:
        connector, reverse = system.get_connector(msg.src, msg.dst)
        if packet is None:
            style = system.style
            color = style.reply_color if msg.kind == "reply" else style.packet_color
            packet = Packet(_pick(msg.packet_label, msg.label), color=color, style=style)
        send_kwargs.setdefault("fade_out", True)
        anims.append(Send(packet, connector, reverse=reverse, run_time=run_time, **send_kwargs))
    if sequence is not None:
        arrow = sequence.message_from(msg)
        anims.append(GrowFromPoint(arrow.route, arrow.route.get_start(), run_time=run_time))
        if arrow.label is not None:
            anims.append(FadeInAfter(arrow.label, delay=0.5, run_time=run_time))
    return AnimationGroup(*anims, run_time=run_time)
