"""Source connectors. Collectors only ever talk to a `Connector`."""

from __future__ import annotations

import os

from .base import Connector, PERMISSION_MAP
from .simulated import SimulatedConnector


def get_connector(seed: int = 2026) -> Connector:
    """Return the configured connector. Default: simulated tenant ($0, offline)."""
    mode = os.environ.get("DISP_CONNECTOR", "simulated")
    if mode == "graph":
        from .graph import GraphConnector

        return GraphConnector.from_env()
    return SimulatedConnector(seed)


__all__ = ["Connector", "SimulatedConnector", "get_connector", "PERMISSION_MAP"]
