# powermatchui/utils/ev_load_trace_store.py
"""
File-based storage for EvLoadTrace (D12, half-hourly, 17,520 periods/year).

Implements the storage direction floated for supplyfactors-scale time
series (Parquet/NumPy referenced from a DB row, not expanded into it):
17,520 periods x 30 years x 3 scenarios as one row per half-hour would be
~1.6M rows before even counting the managed/unmanaged charging-mode axis.
Each trace is instead saved as a single .npy file under
settings.EV_TRACE_DIR, with the siren_web.models.EvLoadTrace row carrying
only the file path and summary metadata (n_intervals, annual_energy_mwh,
integral_check_pct).
"""
import hashlib
from pathlib import Path

import numpy as np
from django.conf import settings

from siren_web.models import EvLoadTrace


def _trace_path(csiro_scenario: str, year: int, charging_mode: str) -> Path:
    return Path(settings.EV_TRACE_DIR) / csiro_scenario / charging_mode / f"{year}.npy"


def save_trace(trace, csiro_scenario: str, year: int, charging_mode: str,
                annual_energy_mwh: float, integral_check_pct: float = None) -> EvLoadTrace:
    """
    Persist a half-hourly trace (any array-like) to EV_TRACE_DIR as .npy,
    and create/update the corresponding EvLoadTrace row. Idempotent:
    overwrites any previous file/row for the same (scenario, year, mode).
    """
    arr = np.asarray(trace, dtype=float)
    abs_path = _trace_path(csiro_scenario, year, charging_mode)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(abs_path, arr)

    rel_path = abs_path.relative_to(Path(settings.EV_TRACE_DIR)).as_posix()

    record, _ = EvLoadTrace.objects.update_or_create(
        csiro_scenario=csiro_scenario, year=year, charging_mode=charging_mode,
        defaults={
            'file_path': rel_path,
            'n_intervals': arr.size,
            'annual_energy_mwh': annual_energy_mwh,
            'integral_check_pct': integral_check_pct,
        },
    )
    return record


def load_trace(record: EvLoadTrace) -> np.ndarray:
    """Load the half-hourly NumPy array a given EvLoadTrace row points to."""
    abs_path = Path(settings.EV_TRACE_DIR) / record.file_path
    if not abs_path.exists():
        raise FileNotFoundError(
            f"EvLoadTrace id={record.idevloadtrace} references {abs_path}, which does not exist on disk."
        )
    return np.load(abs_path)


def checksum_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
