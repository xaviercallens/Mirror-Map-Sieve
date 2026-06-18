# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Geographic bounds validation for Earth-2 climate models.

Validates latitude, longitude, temperature, and pressure values
against physical Earth-science constraints.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

from typing import Any, Sequence

import structlog

logger = structlog.get_logger(__name__)

# Physical bounds
LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 360.0  # Allow both [-180,180] and [0,360]
TEMP_MIN_K, TEMP_MAX_K = 150.0, 340.0  # Kelvin
PRESSURE_MIN_PA, PRESSURE_MAX_PA = 30000.0, 110000.0  # Pascals


def validate_geographic_bounds(
    latitudes: Sequence[float] | None = None,
    longitudes: Sequence[float] | None = None,
    temperatures_k: Sequence[float] | None = None,
    pressures_pa: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Validate geographic and atmospheric values against physical bounds.

    Args:
        latitudes: Latitude values in degrees (expected: [-90, 90]).
        longitudes: Longitude values in degrees (expected: [-180, 360]).
        temperatures_k: Temperature values in Kelvin (expected: [150, 340]).
        pressures_pa: Pressure values in Pascals (expected: [30000, 110000]).

    Returns:
        Dict with ``valid`` (bool), ``checks`` (per-variable results),
        ``errors``, and ``warnings``.

    Example::

        result = validate_geographic_bounds(
            latitudes=[48.86, 45.76],
            longitudes=[2.35, 4.83],
            temperatures_k=[288.0, 292.0],
        )
        assert result["valid"]
    """
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, dict[str, Any]] = {}

    if latitudes is not None:
        lat_check = _validate_range(
            "latitude", latitudes, LAT_MIN, LAT_MAX, "°",
        )
        checks["latitude"] = lat_check
        if not lat_check["valid"]:
            errors.append(lat_check["message"])

    if longitudes is not None:
        lon_check = _validate_range(
            "longitude", longitudes, LON_MIN, LON_MAX, "°",
        )
        checks["longitude"] = lon_check
        if not lon_check["valid"]:
            errors.append(lon_check["message"])

    if temperatures_k is not None:
        temp_check = _validate_range(
            "temperature", temperatures_k, TEMP_MIN_K, TEMP_MAX_K, "K",
        )
        checks["temperature"] = temp_check
        if not temp_check["valid"]:
            errors.append(temp_check["message"])
        elif temp_check.get("near_boundary"):
            warnings.append(temp_check["message"])

    if pressures_pa is not None:
        pres_check = _validate_range(
            "pressure", pressures_pa, PRESSURE_MIN_PA, PRESSURE_MAX_PA, "Pa",
        )
        checks["pressure"] = pres_check
        if not pres_check["valid"]:
            errors.append(pres_check["message"])

    valid = len(errors) == 0

    logger.debug(
        "geographic_validation",
        valid=valid,
        num_checks=len(checks),
        num_errors=len(errors),
    )

    return {
        "valid": valid,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def _validate_range(
    name: str,
    values: Sequence[float],
    vmin: float,
    vmax: float,
    unit: str,
) -> dict[str, Any]:
    """Validate that all values fall within [vmin, vmax].

    Args:
        name: Variable name for reporting.
        values: Values to check.
        vmin: Minimum allowed value.
        vmax: Maximum allowed value.
        unit: Unit string for messages.

    Returns:
        Validation result dict.
    """
    if not values:
        return {"valid": True, "message": f"No {name} data to validate"}

    actual_min = min(values)
    actual_max = max(values)
    valid = vmin <= actual_min and actual_max <= vmax

    # Near-boundary warning (within 5% of range)
    range_size = vmax - vmin
    margin = range_size * 0.05
    near_boundary = (
        actual_min < vmin + margin or actual_max > vmax - margin
    )

    message = (
        f"{name}: [{actual_min:.2f}, {actual_max:.2f}]{unit} "
        f"{'✓' if valid else '✗'} "
        f"(bounds: [{vmin:.2f}, {vmax:.2f}]{unit})"
    )

    return {
        "valid": valid,
        "actual_min": actual_min,
        "actual_max": actual_max,
        "expected_min": vmin,
        "expected_max": vmax,
        "near_boundary": near_boundary,
        "message": message,
    }
