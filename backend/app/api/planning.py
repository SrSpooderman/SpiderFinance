"""Compatibility module alias for the planning HTTP adapter."""

import sys
from app.modules.planning import api as module

sys.modules[__name__] = module
