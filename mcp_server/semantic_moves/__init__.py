"""Semantic moves — musical intents that compile to deterministic tool sequences."""

# Import move families to auto-register them
from . import mix_moves  # noqa: F401
from . import transition_moves  # noqa: F401
from . import sound_design_moves  # noqa: F401
from . import performance_moves  # noqa: F401
from . import device_creation_moves  # noqa: F401
from . import routing_moves  # noqa: F401  (v1.20)
from ..sample_engine import moves as sample_moves  # noqa: F401

# Import compilers to auto-register them
from . import mix_compilers  # noqa: F401
from . import transition_compilers  # noqa: F401
from . import sound_design_compilers  # noqa: F401
from . import performance_compilers  # noqa: F401
from . import sample_compilers  # noqa: F401
from . import device_creation_compilers  # noqa: F401
from . import routing_compilers  # noqa: F401  (v1.20)
