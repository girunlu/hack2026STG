"""External inputs — X1 (market news) and X2 (house/CIO view).

Both modules are designed to degrade gracefully: network failures never raise,
and unresolvable instruments are reported as unavailable rather than fabricated.
"""

from . import news, house_view

__all__ = ["news", "house_view"]
