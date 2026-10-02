"""Desktop entry point and compatibility API for the original V8.5 module."""

import guardrail_dxf
import guardrail_landxml
import guardrail_pdf_files
from guardrail_design import (APP_VERSION, DEFAULT_L1_FT, DEFAULT_TERMINAL_SECTION_FT,
    DEFAULT_GATING_FT, INCR_GUARDRAIL_FT, TABLE_9_6_A, TABLE_9_2_A)
from guardrail_engine import (adt_bucket_index, get_lr, speed_group_clearzone,
    adt_group_clearzone, resolve_clear_zone, round_up_to_increment, compute_x_min,
    compute_guardrail_outputs)
from guardrail_parsing import parse_number as _first_number
from guardrail_validation import require_finite as _require_finite
from guardrail_resources import resource_path
from guardrail_presentation import fmt_ft_in, _safe_filename, _join_path
from guardrail_report import build_pdf_data, validate_pdf_numbers
from guardrail_pdf import generate_pdf_calc_sheet
from guardrail_pdf_files import merge_with_appendices, appendix_manifest
from guardrail_cli import main
from guardrail_ui import ui_main


def write_calc_pdf(out_path, pdf_data, auto_open=False, include_appendix=True):
    """Compatibility adapter; injected operations preserve established patch points."""
    return guardrail_pdf_files.write_calc_pdf(out_path, pdf_data, auto_open, include_appendix,
        renderer=generate_pdf_calc_sheet, merger=merge_with_appendices)


def configure_logging() -> None:
    """Keep tracebacks available when the packaged GUI has no console."""
    import logging
    import os
    import tempfile
    from pathlib import Path
    folder = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "GuardrailCalculator"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=folder / "guardrail.log", encoding="utf-8",
                            level=logging.WARNING, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    except OSError:
        logging.basicConfig(level=logging.WARNING)


if __name__ == "__main__":
    configure_logging()
    ui_main()
