"""Semantic moves — musical intents that compile to deterministic tool sequences."""

# Import move families to auto-register them
from . import mix_moves  # noqa: F401
from . import transition_moves  # noqa: F401
from . import sound_design_moves  # noqa: F401
from . import performance_moves  # noqa: F401

# Import compilers to auto-register them
from . import mix_compilers  # noqa: F401
from . import transition_compilers  # noqa: F401
from . import sound_design_compilers  # noqa: F401
from . import performance_compilers  # noqa: F401
