"""
3D set pieces and the camera moves that show them off.

A flat diagram lies in the xy-plane. Tilting the camera turns that plane
into a floor, and these props stand up out of it along OUT: a database drum
and a server rack. ``zoom_to``, ``orbit`` and ``reset_camera`` are the
camera moves; they play themselves, like ``ThreeDScene.move_camera``.

Manim's Cairo renderer has no depth buffer. Its ``ThreeDCamera`` draws 3D
pieces sorted by distance and then every flat mobject on top of them, so a
diagram lying on the floor would cover a prop standing on it. A diagram is a
floor, so ``SoftwareThreeDScene`` uses ``DiagramCamera``, which draws flat
mobjects first, 3D pieces by depth, and fixed-in-frame captions last.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from manim import DEGREES
from manim import DOWN
from manim import GREEN
from manim import GREY_A
from manim import GREY_B
from manim import GREY_D
from manim import MED_SMALL_BUFF
from manim import ORIGIN
from manim import OUT
from manim import PI
from manim import RIGHT
from manim import Camera
from manim import Cylinder
from manim import Dot
from manim import Mobject
from manim import Prism
from manim import ThreeDCamera
from manim import ThreeDScene
from manim import VGroup
from manim import config

from manim_software.style import _make_text
from manim_software.style import _pick
from manim_software.style import _resolve_style

if TYPE_CHECKING:
    from typing import Any
    from typing import Iterable

    from manim import Animation
    from manim.typing import ManimColor

    from manim_software.style import DiagramStyle


DEFAULT_THETA = -90.0   # manim's default azimuth, in degrees: x to the right


class DiagramCamera(ThreeDCamera):
    """
    A ``ThreeDCamera`` for a flat diagram with props standing on it: flat
    mobjects are drawn first (in ``z_index`` order), 3D-shaded pieces by
    distance, and fixed-in-frame mobjects last.
    """
    def get_mobjects_to_display(self, *args: Any, **kwargs: Any) -> list[Mobject]:
        mobjects = Camera.get_mobjects_to_display(self, *args, **kwargs)
        rot_matrix = self.get_rotation_matrix()

        def key(mob: Mobject) -> float:
            if mob in self.fixed_in_frame_mobjects:
                return np.inf
            if getattr(mob, "shade_in_3d", False):
                return float(np.dot(mob.get_z_index_reference_point(), rot_matrix.T)[2])
            return -np.inf

        return sorted(mobjects, key=key)


class SoftwareThreeDScene(ThreeDScene):
    """A ``ThreeDScene`` whose camera draws a flat diagram under its 3D props."""
    def __init__(self, camera_class: type[Camera] = DiagramCamera, **kwargs: Any):
        super().__init__(camera_class=camera_class, **kwargs)


class Database3D(VGroup):
    """A drum standing on the floor, with rings and a label written in front of it."""
    def __init__(
        self,
        height: float = 1.6,
        radius: float = 0.6,
        label: str = "",
        color: ManimColor | None = None,
        n_rings: int = 2,
        resolution: tuple[int, int] = (1, 32),
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        style = _resolve_style(style)
        self.style = style
        color = _pick(color, style.prop_color)
        self.body = Cylinder(
            radius=radius, height=height, direction=OUT, resolution=resolution,
            fill_color=color, fill_opacity=1.0, checkerboard_colors=False,
            stroke_color=color, stroke_width=0.5,
        )
        self.rings = VGroup()
        for z in np.linspace(-0.5 * height, 0.5 * height, n_rings + 2)[1:-1]:
            ring = Cylinder(
                radius=radius * 1.01, height=0.03, direction=OUT, show_ends=False,
                resolution=resolution, fill_color=GREY_A, fill_opacity=1.0,
                checkerboard_colors=False, stroke_color=GREY_A, stroke_width=0.5,
            )
            ring.shift(z * OUT)
            self.rings.add(ring)
        self.add(self.body, self.rings)
        self.label = None
        if label:
            self.label = _make_text(label, style=style)
            self.label.next_to(self.body, DOWN, buff=MED_SMALL_BUFF)
            self.label.set_z(-0.5 * height)
            self.add(self.label)


class Server3D(VGroup):
    """A rack of units stacked up from the floor, LEDs on the front."""
    def __init__(
        self,
        width: float = 1.8,
        depth: float = 1.2,
        unit_height: float = 0.35,
        n_units: int = 3,
        label: str = "",
        color: ManimColor = GREY_D,
        edge_color: ManimColor = GREY_B,
        led_color: ManimColor = GREEN,
        style: DiagramStyle | None = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        style = _resolve_style(style)
        self.style = style
        self.units = VGroup()
        for i in range(n_units):
            unit = Prism(
                dimensions=[width, depth, unit_height],
                fill_color=color, fill_opacity=1.0,
                stroke_color=edge_color, stroke_width=1.0,
            )
            unit.shift((i + 0.5) * unit_height * OUT)
            led = Dot(radius=0.05, color=led_color)
            led.rotate(PI / 2, RIGHT)
            led.move_to(unit.get_center() + 0.5 * depth * DOWN + 0.35 * width * RIGHT)
            led.shift(0.01 * DOWN)
            led.shade_in_3d = True
            self.units.add(VGroup(unit, led))
        self.add(self.units)
        self.label = None
        if label:
            self.label = _make_text(label, style=style)
            self.label.next_to(self.units, DOWN, buff=MED_SMALL_BUFF)
            self.label.set_z(0)   # next_to matched the rack's mid-height; the label lies on the floor
            self.add(self.label)


def zoom_to(
    scene: ThreeDScene,
    mobject: Mobject,
    height: float | None = None,
    theta: float = -20,
    phi: float = 65,
    gamma: float = 0,
    added_anims: Iterable[Animation] = (),
    **play_kwargs
) -> None:
    """
    Swing the camera down onto ``mobject`` and play the move. Angles are in
    degrees; ``theta`` is relative to manim's default azimuth, so 0 keeps x
    pointing right. ``height`` is how tall the visible frame ends up.
    """
    height = _pick(height, 2.5 * mobject.height)
    scene.move_camera(
        phi=phi * DEGREES,
        theta=(DEFAULT_THETA + theta) * DEGREES,
        gamma=gamma * DEGREES,
        zoom=config.frame_height / height,
        frame_center=mobject.get_center(),
        added_anims=list(added_anims),
        **play_kwargs
    )


def orbit(scene: ThreeDScene, degrees: float, **play_kwargs) -> None:
    """Turn the camera ``degrees`` further around the vertical axis, and play it."""
    play_kwargs.setdefault("rate_func", lambda t: t)
    scene.move_camera(theta=scene.camera.get_theta() + degrees * DEGREES, **play_kwargs)


def reset_camera(scene: ThreeDScene, added_anims: Iterable[Animation] = (), **play_kwargs) -> None:
    """Back to the flat, centred default view, and play it."""
    scene.move_camera(
        phi=0, theta=DEFAULT_THETA * DEGREES, gamma=0, zoom=1,
        frame_center=ORIGIN, added_anims=list(added_anims), **play_kwargs
    )
