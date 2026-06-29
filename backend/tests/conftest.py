"""Test-suite configuration.

Force the local sandbox backend so the deterministic pipeline tests behave the
same everywhere — on a dev machine and on CI runners (which have Docker, and
would otherwise auto-select the Docker backend). Must run before app settings
are first read, so it lives at import time in conftest.
"""

import os

os.environ.setdefault("SANDBOX_BACKEND", "local")
