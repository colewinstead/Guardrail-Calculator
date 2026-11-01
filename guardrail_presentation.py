"""Display and filename formatting at application boundaries."""

import os
import re

def fmt_ft_in(x_ft: float) -> str:
    """Pretty format like 18.1458 -> 18'-1.75\" (approx)."""
    if x_ft is None:
        return ""
    sign = "-" if x_ft < 0 else ""
    x = abs(x_ft)
    ft = int(x)
    inches = (x - ft) * 12.0
    return f"{sign}{ft}'-{inches:.4f}\""


def _safe_filename(name: str) -> str:
    name = name.strip()
    if not name:
        return "guardrail_calc_sheet.pdf"
    # Remove invalid Windows filename characters
    name = re.sub(r'[<>:"/\\|?*]+', "_", name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def _join_path(folder: str, filename: str) -> str:
    folder = (folder or "").strip()
    if folder == "":
        return os.path.abspath(filename)
    return os.path.abspath(os.path.join(folder, filename))
