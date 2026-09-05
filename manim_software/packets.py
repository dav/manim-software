"""
Things that travel along wires, and the animations that move them.

``Packet`` is a dot or a labelled pill. ``Send`` moves one along a connector
with a light trailing it and a flash where it lands; ``Reply`` is the same
back the other way; ``SendAlong`` chains hops through several connectors,
pulsing each component as the packet arrives.

Manim adds every mobject of a queued animation to the scene before the first
one starts, so the helpers here keep their trails, flashes and fading packets
invisible until their own ``begin`` and hide them again in ``finish``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from manim import SMALL_BUFF
from manim import TAU
from manim import RIGHT
from manim import UP
from manim import Animation
from manim import AnimationGroup
from manim import Circle
from manim import Dot
from manim import Line
from manim import Mobject
from manim import RoundedRectangle
from manim import Succession
from manim import Transform
from manim import VGroup
from manim import VMobject
from manim import smooth
from manim import there_and_back

from manim_software.connectors import Connector
from manim_software.connectors import Route
from manim_software.connectors import length_alpha_to_curve_alpha
from manim_software.style import Z_EDGE
from manim_software.style import Z_PACKET
from manim_software.style import _backstroke
from manim_software.style import _make_text
from manim_software.style import _pick
from manim_software.style import _resolve_style

if TYPE_CHECKING:
    from typing import Callable, Sequence

    from manim.typing import ManimColor
    from manim.typing import Point3D
    from manim.typing import Vector3D

    from manim_software.components import Component
    from manim_software.style import DiagramStyle


class Packet(VGroup):
    """
    A message in flight: a glowing dot, or a pill carrying a short label like
    ``GET /orders``. A dot's label rides beside it, above by default
    (``label_direction``); pick the side away from whatever the wire passes.
    """
    def __init__(
        self,
        label: str = "",
        shape: str = "dot",
        color: ManimColor | None = None,
        radius: float | None = None,
        font_size: int | None = None,
        halo: bool = True,
        label_direction: Vector3D = UP,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        style = _resolve_style(style)
        self.style = style
        self.packet_color = _pick(color, style.packet_color)
        radius = _pick(radius, style.packet_radius)
        font_size = _pick(font_size, style.small_font_size)
        self.label = _make_text(label, font_size=font_size, style=style) if label else None

        if shape == "pill" and self.label is not None:
            self.body = RoundedRectangle(
                corner_radius=0.5 * (self.label.height + 2 * SMALL_BUFF),
                width=self.label.width + 2 * SMALL_BUFF,
                height=self.label.height + 2 * SMALL_BUFF,
            )
            self.body.set_fill(self.packet_color, opacity=1).set_stroke(width=0)
            self.label.move_to(self.body)
        else:
            self.body = Dot(radius=radius, color=self.packet_color)
            if self.label is not None:
                _backstroke(self.label)
                self.label.next_to(self.body, label_direction, buff=0.5 * SMALL_BUFF)
        self.halo = None
        if halo:
            halo_radius = 2.0 * radius if shape != "pill" else 0.5 * self.body.height + 0.6 * radius
            self.halo = Circle(radius=halo_radius, stroke_width=0)
            self.halo.set_fill(self.packet_color, opacity=0.25).move_to(self.body)
            if shape == "pill":
                self.halo.stretch_to_fit_width(self.body.width + 1.2 * radius)
            self.add(self.halo)
        self.add(self.body)
        if self.label is not None:
            self.add(self.label)
        self.set_z_index(Z_PACKET)

    def get_packet_color(self) -> ManimColor:
        return self.packet_color


# Opacity bookkeeping for things that fade while manim already shows them


def _family_opacities(mobject: Mobject) -> list[tuple[float, float, float]]:
    """
    The opacities a mobject has when fully shown. Remembered on the mobject
    the first time they are read, because a later hop of the same packet is
    built while an earlier one has already hidden it.
    """
    cached = getattr(mobject, "_full_opacities", None)
    if cached is not None:
        return cached
    opacities = [
        (sm.get_fill_opacity(), sm.get_stroke_opacity(), sm.get_stroke_opacity(background=True))
        for sm in mobject.get_family()
        if isinstance(sm, VMobject)
    ]
    mobject._full_opacities = opacities
    return opacities


def _set_family_opacity(mobject: Mobject, factor: float, full_opacities) -> None:
    vmobs = [sm for sm in mobject.get_family() if isinstance(sm, VMobject)]
    for sm, (fill, stroke, back) in zip(vmobs, full_opacities):
        sm.set_fill(opacity=factor * fill, family=False)
        sm.set_stroke(opacity=factor * stroke, family=False)
        sm.set_stroke(opacity=factor * back, background=True, family=False)


def _flash_bounds(alpha: float, time_width: float) -> tuple[float, float]:
    """The visible stretch of a passing flash, as in ``ShowPassingFlash``."""
    upper = alpha * (1 + time_width)
    lower = upper - time_width
    return max(lower, 0.0), min(upper, 1.0)


class _WireFlash(Animation):
    """
    A light sweeping along a wire copy, invisible before it begins and after
    it ends. Bounds are by arc length, so it does not lurch over corners.
    """
    def __init__(self, vmobject: VMobject, time_width: float = 0.35, **kwargs):
        self.time_width = time_width
        self.full_path = vmobject.copy()
        self.full_width = vmobject.get_stroke_width()
        vmobject.set_stroke(width=0)
        super().__init__(vmobject, remover=True, **kwargs)

    def begin(self) -> None:
        self.mobject.set_stroke(width=self.full_width)
        super().begin()

    def interpolate_mobject(self, alpha: float) -> None:
        lower, upper = _flash_bounds(self.rate_func(alpha), self.time_width)
        self.mobject.pointwise_become_partial(
            self.full_path,
            length_alpha_to_curve_alpha(self.full_path, lower),
            length_alpha_to_curve_alpha(self.full_path, upper),
        )

    def finish(self) -> None:
        super().finish()
        self.mobject.set_stroke(width=0)


class _ArrivalFlash(Animation):
    """
    Rays bursting out of a point during the last part of the animation
    (``delay`` is the fraction of the run time to wait first). Invisible
    before it begins and after it ends.
    """
    def __init__(
        self,
        point: Point3D,
        color: ManimColor,
        delay: float = 0.7,
        line_length: float = 0.12,
        num_lines: int = 12,
        flash_radius: float = 0.25,
        line_stroke_width: float = 2.5,
        **kwargs
    ):
        self.delay = delay
        self.point = np.array(point, dtype=float)
        self.line_stroke_width = line_stroke_width
        self.lines = VGroup()
        for angle in np.arange(0, TAU, TAU / num_lines):
            line = Line(self.point, self.point + line_length * RIGHT)
            line.shift(flash_radius * RIGHT)
            line.rotate(angle, about_point=self.point)
            self.lines.add(line)
        self.lines.set_stroke(color, width=0)
        self.full_lines = self.lines.copy()
        super().__init__(self.lines, remover=True, **kwargs)

    def begin(self) -> None:
        self.lines.set_stroke(width=self.line_stroke_width)
        super().begin()

    def interpolate_mobject(self, alpha: float) -> None:
        t = 0.0 if alpha <= self.delay else (alpha - self.delay) / (1 - self.delay)
        lower, upper = _flash_bounds(smooth(t), 1.0)
        for line, full in zip(self.lines, self.full_lines):
            line.pointwise_become_partial(full, lower, upper)

    def finish(self) -> None:
        super().finish()
        self.lines.set_stroke(width=0)


class _MoveAlongRoute(Animation):
    """
    Slides a mobject along a path by arc length, fading it in and out at the
    ends when asked. A packet meant to fade in is hidden until it begins.
    """
    def __init__(
        self,
        mobject: Mobject,
        path: VMobject,
        fade_in: bool = False,
        fade_out: bool = False,
        fade_fraction: float = 0.15,
        **kwargs
    ):
        self.path = path
        self.fade_in = fade_in
        self.fade_out = fade_out
        self.fade_fraction = fade_fraction
        self.full_opacities = _family_opacities(mobject)
        if fade_in:
            _set_family_opacity(mobject, 0.0, self.full_opacities)
        super().__init__(mobject, **kwargs)

    def _fade_factor(self, alpha: float) -> float:
        f = self.fade_fraction
        factor = 1.0
        if self.fade_in and alpha < f:
            factor = min(factor, alpha / f)
        if self.fade_out and alpha > 1 - f:
            factor = min(factor, (1 - alpha) / f)
        return factor

    def interpolate_mobject(self, alpha: float) -> None:
        point = self.path.point_from_proportion(self.rate_func(alpha))
        self.mobject.move_to(point)
        if self.fade_in or self.fade_out:
            _set_family_opacity(self.mobject, self._fade_factor(alpha), self.full_opacities)


class _MoveTo(Animation):
    """Moves a mobject from wherever it is when the animation begins to a fixed point."""
    def __init__(self, mobject: Mobject, point: Point3D, **kwargs):
        self.point = np.array(point, dtype=float)
        super().__init__(mobject, **kwargs)

    def begin(self) -> None:
        self.origin = self.mobject.get_center()
        super().begin()

    def interpolate_mobject(self, alpha: float) -> None:
        alpha = self.rate_func(alpha)
        self.mobject.move_to(self.origin + alpha * (self.point - self.origin))


class FadeInAfter(Animation):
    """
    Fade a mobject in during the last part of the run time, after ``delay``
    (a fraction of it) has passed. The mobject is hidden until then, which
    manim's own ``FadeIn`` cannot promise once it is queued.
    """
    def __init__(self, mobject: Mobject, delay: float = 0.5, **kwargs):
        self.delay = delay
        self.full_opacities = _family_opacities(mobject)
        _set_family_opacity(mobject, 0.0, self.full_opacities)
        super().__init__(mobject, **kwargs)

    def interpolate_mobject(self, alpha: float) -> None:
        t = 0.0 if alpha <= self.delay else (alpha - self.delay) / (1 - self.delay)
        _set_family_opacity(self.mobject, self.rate_func(t), self.full_opacities)


def _travel_path(connector: Connector | Route | VMobject, reverse: bool) -> VMobject:
    if isinstance(connector, Connector):
        return connector.get_travel_path(reverse=reverse)
    if isinstance(connector, Route):
        path = connector.get_travel_path()
    else:
        path = connector.copy()
    if reverse:
        path.reverse_points()
    return path


def _packet_color(packet: Mobject) -> ManimColor:
    if hasattr(packet, "get_packet_color"):
        return packet.get_packet_color()
    return packet.get_color()


class Send(AnimationGroup):
    """
    Move a packet along a connector: the packet slides by arc length, a light
    of its colour sweeps the wire under it, and a flash marks the arrival.
    ``reverse`` runs the same wire the other way (see ``Reply``).
    """
    def __init__(
        self,
        packet: Packet,
        connector: Connector | Route | VMobject,
        reverse: bool = False,
        run_time: float = 1.0,
        rate_func: Callable[[float], float] = smooth,
        trail: bool = True,
        trail_time_width: float = 0.35,
        flash: bool = True,
        fade_in: bool = True,
        fade_out: bool = False,
        **kwargs
    ):
        self.packet = packet
        self.path = _travel_path(connector, reverse)
        color = _packet_color(packet)
        anims = [
            _MoveAlongRoute(
                packet, self.path,
                fade_in=fade_in, fade_out=fade_out,
                run_time=run_time, rate_func=rate_func,
                remover=fade_out,
            )
        ]
        if trail:
            trail_mob = self.path.copy()
            width = self.path.get_stroke_width() or 3.0
            trail_mob.set_stroke(color, width=2.0 * width, opacity=1.0)
            trail_mob.set_z_index(Z_EDGE)
            anims.append(_WireFlash(
                trail_mob, time_width=trail_time_width,
                run_time=run_time, rate_func=rate_func,
            ))
        if flash:
            arrival = _ArrivalFlash(self.path.get_end(), color=color, run_time=run_time)
            arrival.lines.set_z_index(Z_PACKET)
            anims.append(arrival)
        super().__init__(*anims, run_time=run_time, **kwargs)


class Reply(Send):
    """A ``Send`` back along the wire, in the reply colour unless the packet has its own."""
    def __init__(self, packet: Packet, connector, **kwargs):
        kwargs.setdefault("reverse", True)
        super().__init__(packet, connector, **kwargs)


class Pulse(Transform):
    """A quick swell and glow of a component's box, for 'this one is handling it'."""
    def __init__(
        self,
        component: Component | VMobject,
        scale_factor: float = 1.06,
        color: ManimColor | None = None,
        rate_func: Callable[[float], float] = there_and_back,
        run_time: float = 0.6,
        **kwargs
    ):
        style = _resolve_style(getattr(component, "style", None))
        self.scale_factor = scale_factor
        self.pulse_color = _pick(color, style.active_color)
        super().__init__(component, rate_func=rate_func, run_time=run_time, **kwargs)

    def create_target(self) -> Mobject:
        target = self.mobject.copy()
        box = target.box if hasattr(target, "box") else target
        box.scale(self.scale_factor)
        box.set_stroke(self.pulse_color)
        return target


class SendAlong(Succession):
    """
    One packet hopping through several connectors in turn. Each hop is a
    ``Send``; between hops the packet crosses the component it arrived at;
    and each arrival can pulse that component and run an ``on_arrive``
    animation of the caller's choosing.

    ``hops``: connectors, or ``(connector, reverse)`` pairs.
    """
    def __init__(
        self,
        packet: Packet,
        hops: Sequence[Connector | tuple[Connector, bool]],
        hop_time: float = 0.8,
        transit_time: float = 0.25,
        pulse: bool = True,
        fade_out: bool = True,
        on_arrive: Callable[[int, Connector], Animation | None] | None = None,
        **send_kwargs
    ):
        anims: list[Animation] = []
        normalized = [
            hop if isinstance(hop, tuple) else (hop, False)
            for hop in hops
        ]
        last = len(normalized) - 1
        for i, (connector, reverse) in enumerate(normalized):
            if i > 0:
                start = connector.get_travel_path(reverse=reverse).get_start()
                anims.append(_MoveTo(packet, start, run_time=transit_time))
            anims.append(Send(
                packet, connector, reverse=reverse,
                run_time=hop_time,
                fade_in=(i == 0) and send_kwargs.get("fade_in", True),
                fade_out=(i == last) and fade_out,
                **{k: v for k, v in send_kwargs.items() if k not in ("fade_in", "fade_out")}
            ))
            arrival = connector.start_mob if reverse else connector.end_mob
            extras = []
            if pulse and hasattr(arrival, "box"):
                extras.append(Pulse(arrival))
            if on_arrive is not None:
                extra = on_arrive(i, connector)
                if extra is not None:
                    extras.append(extra)
            if extras:
                anims.append(AnimationGroup(*extras))
        super().__init__(*anims)


def reply_hops(connectors: Sequence[Connector]) -> list[tuple[Connector, bool]]:
    """The hops of a reply: the given connectors, last first, each reversed."""
    return [(connector, True) for connector in reversed(list(connectors))]
