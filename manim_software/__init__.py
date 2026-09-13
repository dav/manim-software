"""
manim_software: mobjects and animations for explaining how software works,
as a plugin for Manim Community.

Diagrams of systems (components, containers, connectors), the messages that
travel between them (packets), what goes wrong with them (drops, timeouts,
retries, circuit breakers), many at once (fan-out, fan-in, queues), sequence
diagrams of the same interactions, annotations, and a few 3D set pieces::

    from manim import *
    from manim_software import *
"""
from manim_software.style import DiagramStyle
from manim_software.style import DEFAULT_STYLE
from manim_software.style import get_style
from manim_software.style import set_style
from manim_software.style import Z_CONTAINER
from manim_software.style import Z_NODE
from manim_software.style import Z_EDGE
from manim_software.style import Z_EDGE_LABEL
from manim_software.style import Z_PACKET
from manim_software.style import Z_ANNOTATION
from manim_software.style import Z_CAPTION

from manim_software.icons import Pictogram
from manim_software.icons import BrowserIcon
from manim_software.icons import ServerIcon
from manim_software.icons import DatabaseIcon
from manim_software.icons import CacheIcon
from manim_software.icons import QueueIcon
from manim_software.icons import UserIcon
from manim_software.icons import CloudIcon
from manim_software.icons import LockIcon
from manim_software.icons import Icon
from manim_software.icons import ICON_REGISTRY
from manim_software.icons import register_icon
from manim_software.icons import find_svg
from manim_software.icons import get_assets_dir

from manim_software.components import Component
from manim_software.components import Container
from manim_software.components import SystemDiagram
from manim_software.components import bounding_box_point

from manim_software.connectors import Route
from manim_software.connectors import Connector
from manim_software.connectors import length_alpha_to_curve_alpha

from manim_software.layout import assign_layers
from manim_software.layout import order_layers
from manim_software.layout import layered_layout
from manim_software.layout import force_layout
from manim_software.layout import label_candidates
from manim_software.layout import place_labels

from manim_software.packets import Packet
from manim_software.packets import Send
from manim_software.packets import Reply
from manim_software.packets import Pulse
from manim_software.packets import SendAlong
from manim_software.packets import FadeInAfter
from manim_software.packets import reply_hops

from manim_software.failures import Timer
from manim_software.failures import Countdown
from manim_software.failures import Timeout
from manim_software.failures import Drop
from manim_software.failures import Retry
from manim_software.failures import CircuitBreaker
from manim_software.failures import TripBreaker
from manim_software.failures import ResetBreaker

from manim_software.concurrency import FanOut
from manim_software.concurrency import FanIn
from manim_software.concurrency import MessageQueue
from manim_software.concurrency import Enqueue
from manim_software.concurrency import Dequeue

from manim_software.sequence import Message
from manim_software.sequence import SequenceDiagram
from manim_software.sequence import message_animation

from manim_software.annotate import Caption
from manim_software.annotate import Spotlight
from manim_software.annotate import Unspotlight
from manim_software.annotate import Callout

from manim_software.titles import TitleCard
from manim_software.titles import open_on

from manim_software.three_d import Database3D
from manim_software.three_d import Server3D
from manim_software.three_d import DiagramCamera
from manim_software.three_d import SoftwareThreeDScene
from manim_software.three_d import zoom_to
from manim_software.three_d import orbit
from manim_software.three_d import reset_camera

__version__ = "0.1.0"

__all__ = [
    "DiagramStyle", "DEFAULT_STYLE", "get_style", "set_style",
    "Z_CONTAINER", "Z_NODE", "Z_EDGE", "Z_EDGE_LABEL", "Z_PACKET", "Z_ANNOTATION", "Z_CAPTION",
    "Pictogram", "BrowserIcon", "ServerIcon", "DatabaseIcon", "CacheIcon", "QueueIcon",
    "UserIcon", "CloudIcon", "LockIcon", "Icon", "ICON_REGISTRY", "register_icon",
    "find_svg", "get_assets_dir",
    "Component", "Container", "SystemDiagram", "bounding_box_point",
    "Route", "Connector", "length_alpha_to_curve_alpha",
    "assign_layers", "order_layers", "layered_layout", "force_layout", "label_candidates", "place_labels",
    "Packet", "Send", "Reply", "Pulse", "SendAlong", "FadeInAfter", "reply_hops",
    "Timer", "Countdown", "Timeout", "Drop", "Retry", "CircuitBreaker", "TripBreaker", "ResetBreaker",
    "FanOut", "FanIn", "MessageQueue", "Enqueue", "Dequeue",
    "Message", "SequenceDiagram", "message_animation",
    "Caption", "Spotlight", "Unspotlight", "Callout",
    "TitleCard", "open_on",
    "Database3D", "Server3D", "DiagramCamera", "SoftwareThreeDScene", "zoom_to", "orbit", "reset_camera",
]
