"""Compatibility module alias for the forecast HTTP adapter."""

import sys
from app.modules.forecasting import api as module

sys.modules[__name__] = module
