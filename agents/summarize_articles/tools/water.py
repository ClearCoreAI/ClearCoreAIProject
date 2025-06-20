"""
Module: water
Component: Waterdrop Metering for ClearCoreAI

Description:
This module provides reusable utilities for tracking and persisting AIWaterdrop consumption
within ClearCoreAI components. It ensures that waterdrop usage is consistently metered,
persisted across sessions, and safely shared within any agent or orchestrator.

- Supports lazy loading and in-memory cache for performance
- Ensures persistence via aiwaterdrops.json file
- Thread-safe for single-process usage (not multiprocess safe)
- To be imported by any module needing water metering

Usage:
    from tools.water import increment_aiwaterdrops, get_aiwaterdrops, save_aiwaterdrops

License: MIT
Version: 1.0.0
Validated by: Olivier Hays
Last Updated: 2025-06-20
"""

# ----------- Imports ----------- #
import json
from pathlib import Path

# ----------- Constants ----------- #
ROOT = Path(__file__).parent.parent
AIWATERDROPS_FILE = ROOT / "memory" / "short_term" / "aiwaterdrops.json"

# ----------- Internal State ----------- #
_aiwaterdrops_consumed = None  # Lazy-loaded on first access

# ----------- Functions ----------- #
def load_aiwaterdrops() -> float:
    """
    Loads current AI waterdrop usage from persistent storage.

    Returns:
        float: The number of waterdrops consumed so far.

    Initial State:
        - File may or may not exist on disk.

    Final State:
        - Value is loaded from file or defaults to 0.0.

    Water Cost:
        - 0
    """
    global _aiwaterdrops_consumed
    try:
        with AIWATERDROPS_FILE.open("r", encoding="utf-8") as f:
            _aiwaterdrops_consumed = json.load(f).get("aiwaterdrops_consumed", 0.0)
    except FileNotFoundError:
        _aiwaterdrops_consumed = 0.0
    return _aiwaterdrops_consumed

def save_aiwaterdrops(value: float) -> None:
    """
    Saves the provided waterdrop value to persistent storage.

    Parameters:
        value (float): The new total to persist.

    Returns:
        None

    Initial State:
        - File path must be writable.

    Final State:
        - aiwaterdrops.json is updated with the new value.

    Water Cost:
        - 0
    """
    with AIWATERDROPS_FILE.open("w", encoding="utf-8") as f:
        json.dump({"aiwaterdrops_consumed": value}, f)

def increment_aiwaterdrops(amount: float) -> None:
    """
    Increments the waterdrop consumption by a given amount.

    Parameters:
        amount (float): Number of waterdrops to add.

    Returns:
        None

    Initial State:
        - In-memory cache is initialized via lazy loading if needed.

    Final State:
        - Cache and file are updated with new total.

    Raises:
        None

    Water Cost:
        - 0
    """
    global _aiwaterdrops_consumed
    if _aiwaterdrops_consumed is None:
        load_aiwaterdrops()
    _aiwaterdrops_consumed += amount
    save_aiwaterdrops(_aiwaterdrops_consumed)

def get_aiwaterdrops() -> float:
    """
    Returns the current number of waterdrops consumed.

    Returns:
        float: Cached or loaded value.

    Initial State:
        - May not yet be loaded.

    Final State:
        - Value is returned.

    Water Cost:
        - 0
    """
    global _aiwaterdrops_consumed
    if _aiwaterdrops_consumed is None:
        load_aiwaterdrops()
    return _aiwaterdrops_consumed