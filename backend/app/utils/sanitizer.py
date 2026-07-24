import datetime
import numpy as np
import pandas as pd
from typing import Any

def sanitize_for_json(obj: Any) -> Any:
    """
    Secara rekursif membersihkan dan mengonversi objek Python/pandas/numpy (seperti Timestamp, datetime.date,
    np.int64, np.float64, pd.NA, np.nan) menjadi objek murni Python yang 100% JSON serializable.
    """
    if obj is None:
        return None
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass

    if isinstance(obj, (datetime.datetime, datetime.date, pd.Timestamp)):
        return obj.isoformat()
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        val = float(obj)
        return None if np.isnan(val) or np.isinf(val) else val
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(i) for i in obj]
    return obj
