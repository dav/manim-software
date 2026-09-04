"""
The icon registry and the ``Icon`` lookup order: registered pictograms first,
then an SVG in the package assets directory, then manim's assets_dir, and a
placeholder rather than an exception.
"""
from manim import RED
from manim import WHITE
from manim import Circle
from manim import SVGMobject

from manim_software import DiagramStyle
from manim_software import ICON_REGISTRY
from manim_software import Icon
from manim_software import Pictogram
from manim_software import register_icon
from manim_software import icons


SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
<rect x="1" y="1" width="8" height="8" fill="none" stroke="white"/></svg>"""


def test_every_registered_icon_builds_at_requested_height():
    for name, cls in ICON_REGISTRY.items():
        icon = Icon(name, height=0.8)
        assert isinstance(icon, cls), name
        assert icon.family_members_with_points(), name
        assert abs(icon.height - 0.8) < 1e-3, name


def test_unknown_icon_gives_placeholder_not_error():
    icon = Icon("definitely-not-an-icon", height=0.5)
    assert icon.family_members_with_points()
    assert abs(icon.height - 0.5) < 1e-3


def test_register_icon_adds_to_registry():
    class Blob(Pictogram):
        def build(self):
            return [self._outline(Circle())]

    register_icon("blob", Blob)
    try:
        assert isinstance(Icon("Blob"), Blob)
    finally:
        del ICON_REGISTRY["blob"]


def test_svg_lookup_prefers_package_assets_over_assets_dir(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    user_dir = tmp_path / "user_assets"
    assets.mkdir()
    user_dir.mkdir()
    (assets / "widget.svg").write_text(SVG)
    (user_dir / "widget.svg").write_text(SVG.replace('width="8"', 'width="4"'))
    monkeypatch.setattr(icons, "SOFTWARE_ASSETS_DIR", assets)
    monkeypatch.setattr(icons, "get_assets_dir", lambda: user_dir)

    icon = Icon("widget", height=1.0)
    assert isinstance(icon, SVGMobject)
    # The package copy is square; the user copy is half as wide
    assert abs(icon.width - icon.height) < 1e-3

    (assets / "widget.svg").unlink()
    icon = Icon("widget", height=1.0)
    assert isinstance(icon, SVGMobject)
    assert icon.width < 0.75 * icon.height
    # A user's SVG keeps its own colours rather than the style's icon colour
    assert all(m.get_stroke_color() == WHITE for m in icon.family_members_with_points())


def test_bundled_svgs_ship_and_take_the_icon_colour():
    assert icons.SOFTWARE_ASSETS_DIR.is_dir()
    bundled = sorted(p.stem for p in icons.SOFTWARE_ASSETS_DIR.glob("*.svg"))
    assert bundled == ["file", "mail", "phone"]
    for name in bundled:
        assert icons.find_svg(name) == icons.SOFTWARE_ASSETS_DIR / f"{name}.svg"
        icon = Icon(name, height=0.6, style=DiagramStyle(icon_color=RED))
        assert isinstance(icon, SVGMobject), name
        assert icon.family_members_with_points(), name
        assert abs(icon.height - 0.6) < 1e-3, name
        assert all(m.get_stroke_color() == RED for m in icon.family_members_with_points()), name
    assert Icon("phone", color=WHITE).get_stroke_color() == WHITE
