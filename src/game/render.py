"""Render hook registry — Python-side dispatcher for HUD subsystems.

Each subsystem registers a callback via register(). The manager calls
tick() at the appropriate cadence, which invokes all registered callbacks.
The PNACH-side dispatcher (16-render-dispatch.pnach) handles the actual
drawing by calling each renderer's cave entry point.
"""

import logging

log = logging.getLogger(__name__)

_hooks: list[tuple[str, callable]] = []


def register(name: str, fn: callable):
    """Register a render callback. fn(mem, loop_no) is called each tick."""
    _hooks.append((name, fn))


def tick(mem, loop_no):
    """Call all registered render hooks."""
    for name, fn in _hooks:
        try:
            fn(mem, loop_no)
        except Exception as e:
            log.error("Render hook %s error: %s", name, e)
