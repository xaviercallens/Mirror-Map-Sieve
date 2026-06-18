# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Earth-2 weather prediction integrations."""

from nvidia.earth2.weather_prediction import predict_weather
from nvidia.earth2.climate_validator import validate_geographic_bounds

__all__ = ["predict_weather", "validate_geographic_bounds"]
