"""
Everything public in the package is reachable from ``from manim_software import *``
through the explicit ``__all__``, and nothing shadows a manim name.
"""
import importlib
import inspect
import pkgutil

import manim

import manim_software


def _public_members(module):
    for name, obj in vars(module).items():
        if name.startswith("_"):
            continue
        if not (inspect.isclass(obj) or inspect.isfunction(obj)):
            continue
        if getattr(obj, "__module__", "") == module.__name__:
            yield name, obj


def _submodules():
    for info in pkgutil.iter_modules(manim_software.__path__):
        yield importlib.import_module(f"{manim_software.__name__}.{info.name}")


def test_all_public_classes_and_functions_are_exported():
    exported = set(manim_software.__all__)
    missing = [
        f"{module.__name__}.{name}"
        for module in _submodules()
        for name, _ in _public_members(module)
        if name not in exported
    ]
    assert not missing, f"Add to manim_software.__all__: {missing}"


def test_every_export_exists():
    for name in manim_software.__all__:
        assert hasattr(manim_software, name), name


def test_no_export_shadows_a_manim_name():
    clashes = [name for name in manim_software.__all__ if hasattr(manim, name)]
    assert not clashes, f"These names already exist in manim: {clashes}"


def test_plugin_entry_point_is_registered():
    from importlib.metadata import entry_points
    names = {ep.name for ep in entry_points(group="manim.plugins")}
    assert "manim_software" in names
