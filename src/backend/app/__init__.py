"""UNRISKOMEGA prototype backend.

``.env`` is loaded here, on first import of any ``app.*`` module, so every entry point sees the same
configuration: the uvicorn server, ``tools/drill.py``, a test run and an ad-hoc ``python -c`` script.
Loading it in ``main.py`` alone left scripts without the optional LLM key, which made the same code
behave differently depending on how it was started.
"""

from . import env

env.load()
