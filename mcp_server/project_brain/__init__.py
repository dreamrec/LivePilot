"""Project Brain v1 — shared state substrate for LivePilot.

Provides one coherent, inspectable, updateable representation of the
current project state.  All engines read from this instead of each
rebuilding partial state from scratch.
"""
