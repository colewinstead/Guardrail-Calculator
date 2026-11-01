"""Optional console compatibility interface; desktop launch uses guardrail_ui."""

from datetime import datetime
from guardrail_design import (DEFAULT_L1_FT, DEFAULT_TERMINAL_SECTION_FT, DEFAULT_GATING_FT,
                             TABLE_9_2_A, SUPPORTED_SPEEDS, SUPPORTED_FLARE_RATES)
from guardrail_parsing import parse_number as _first_number
from guardrail_engine import (speed_group_clearzone, adt_group_clearzone, resolve_clear_zone,
                             compute_guardrail_outputs)
from guardrail_presentation import fmt_ft_in, _safe_filename, _join_path
from guardrail_report import build_pdf_data
from guardrail_pdf_files import write_calc_pdf
from guardrail_validation import opposing_offset, roadway_inputs

def prompt_float(msg: str, allow_blank: bool = False, default=None) -> float:
    while True:
        s = input(msg).strip()
        if allow_blank and s == "":
            return default
        try:
            return _first_number(s)
        except ValueError:
            print("  Please enter a complete finite number (for example, 6000 or 6,000).")


def prompt_choice(msg: str, options: list[str]) -> str:
    opt_map = {str(i + 1): v for i, v in enumerate(options)}
    while True:
        print(msg)
        for i, v in enumerate(options, start=1):
            print(f"  {i}) {v}")
        sel = input("> ").strip()
        if sel in opt_map:
            return opt_map[sel]
        if sel in options:
            return sel
        print("  Pick one of the listed options.")


def choose_clear_zone(speed: float, adt: float) -> float:
    group_s = speed_group_clearzone(speed)
    group_a = adt_group_clearzone(adt)

    slope = prompt_choice(
        "Side slope category for Table 9-2-A:",
        ["6:1_or_flatter", "5:1_to_4:1"]
    )

    mn, mx = TABLE_9_2_A[group_s][group_a][slope]
    pick = prompt_choice(
        f"Recommended clear zone range is {mn}-{mx} ft. What do you want to use?",
        ["min", "mid", "max", "custom"]
    )
    custom_value = prompt_float("Enter clear zone value (ft): ") if pick == "custom" else None
    return resolve_clear_zone(speed, adt, slope, pick, custom_value)


def main():
    print("\nGuardrail Calculator Starting....")
    print("Bridge Approach Guardrail (MDOT Table 9-6-A) + outputs A/B/C/D per GR-4\n")

    project = input("Project name (optional): ").strip()

    facility = prompt_choice(
        "Facility type:",
        ["two_lane_two_way", "divided_highway"]
    )

    speed = int(prompt_choice(
        "Design speed (mph) (must match MDOT Table 9-6-A):",
        [str(speed) for speed in SUPPORTED_SPEEDS]
    ))

    adt = prompt_float("Design ADT (total both directions, design year): ")

    la_mode = prompt_choice(
        "How do you want to set LA (distance from edge of traveled way to back of hazard)?",
        ["Help me choose a clear zone from Table 9-2-A (then LA = clear zone)", "I will enter LA directly"]
    )

    if la_mode.startswith("I will enter"):
        LA = prompt_float("LA (ft): ")
        clear_zone_used = None
    else:
        clear_zone_used = choose_clear_zone(speed, adt)
        LA = clear_zone_used
        print(f"Using LA = {LA:.4f} ft based on Table 9-2-A selection.\n")

    # Near-side L2 (edge of traveled way -> barrier face line)
    L2 = prompt_float("Near-side L2 (ft) = offset from edge of traveled way to guardrail (barrier face line): ")

    lane_width = None

    # Opposite-side L2 rule:
    # LA DOES NOT CHANGE, only L2 changes by + one lane width (two-lane, two-way).
    if facility == "two_lane_two_way":
        lane_width = prompt_float("Lane width (ft): ")
        L2_opp = opposing_offset(L2, lane_width)
    else:
        mode = prompt_choice(
            "Opposing-side L2 adjustment (divided):",
            ["Enter added distance to opposite traveled-way edge (custom)", "Compute from lanes + median (helper)"]
        )
        if mode.startswith("Enter"):
            add_dist = prompt_float("Added distance to reach opposite traveled-way edge (ft): ")
        else:
            lane_w = prompt_float("Lane width (ft): ")
            lanes_this = prompt_float("Number of lanes in your direction: ")
            lanes_opp = prompt_float("Number of lanes in opposing direction: ")
            median_w = prompt_float("Median width between traveled ways (ft): ")
            add_dist = roadway_inputs("divided_highway", L2, lane_w, lanes_this, lanes_opp, median_w)["added_distance"]
            print(f"Computed added distance = {add_dist:.4f} ft")
        L2_opp = opposing_offset(L2, add_dist)

    # L1 option
    l1_mode = prompt_choice(
        f"L1 option (Example 9-6-1 uses L1 = 18'-1.75\" = {DEFAULT_L1_FT:.4f} ft):",
        ["Use standard L1", "Enter custom L1"]
    )
    L1 = DEFAULT_L1_FT if l1_mode.startswith("Use") else prompt_float("Enter L1 (ft): ")

    # Terminal section option
    term_mode = prompt_choice(
        f"Terminal section length to use for B/D (default = {DEFAULT_TERMINAL_SECTION_FT:.1f} ft):",
        ["Use 25.0 ft", "Enter custom"]
    )
    terminal_section = DEFAULT_TERMINAL_SECTION_FT if term_mode.startswith("Use") else prompt_float("Enter terminal section length (ft): ")

    # Flare rate (a/b)
    flare_pick = prompt_choice(
        "Flare rate a/b:",
        [str(rate) if rate else "0 (non-flared)" for rate in SUPPORTED_FLARE_RATES]
    )
    a_over_b = 0.0 if flare_pick.startswith("0") else float(flare_pick)
    results = compute_guardrail_outputs(speed, adt, LA, L2, L2_opp, L1, terminal_section, a_over_b)

    # -------------------------
    # PRINT
    # -------------------------
    print("\n--- Inputs ---")
    print(f"Project: {project or '(blank)'}")
    print(f"Facility: {facility}")
    print(f"Design speed: {speed} mph")
    print(f"Design ADT: {adt:.0f}")
    if clear_zone_used is not None:
        print(f"Clear zone selected (Table 9-2-A): {clear_zone_used:.4f} ft (used as LA)")
    print(f"LA: {LA:.4f} ft")
    print(f"Near-side L2: {L2:.4f} ft")
    print(f"Opp-side L2 (near L2 + crossing): {L2_opp:.4f} ft")
    print(f"L1: {L1:.4f} ft  ({fmt_ft_in(L1)})")
    print(f"Terminal section for B/D: {terminal_section:.4f} ft")
    print(f"Flare rate a/b: {a_over_b:.0f}/1" if a_over_b != 0 else "Flare rate: non-flared (a/b = 0)")
    print(f"LR (Table 9-6-A): {results['LR']:.0f} ft")

    print("\n--- Near-side calculation ---")
    print(f"X(min) before rounding: {results['X_min_near']:.4f} ft")
    print(f"B required = X(min) - L1 - terminal: {results['B_required']:.4f} ft")
    print(f"B after 12.5000-ft minimum and increment rounding: {results['B']:.4f} ft")
    print(f"A = B + L1 + terminal: {results['A']:.4f} ft")

    print("\n--- Opposing-side calculation (LA same, L2 increased) ---")
    print(f"X(min) before rounding: {results['X_min_opp']:.4f} ft")
    print(f"D required = X(min) - L1 - terminal: {results['D_required']:.4f} ft")
    print(f"D after 12.5000-ft minimum and increment rounding: {results['D']:.4f} ft")
    print(f"C = D + L1 + terminal: {results['C']:.4f} ft")

    print("\n=== GR-4 / GR-4a Outputs ===")
    print(f"A (near) = B + L1 + terminal: {results['A']:.4f} ft")
    print(f"B (near) = rounded rail length: {results['B']:.4f} ft")
    print(f"C (opp)  = D + L1 + terminal: {results['C']:.4f} ft")
    print(f"D (opp)  = rounded rail length: {results['D']:.4f} ft")

    print("\n(Extra) If you want the MDOT example add gating portion total:")
    print(f"Near total with +{DEFAULT_GATING_FT} ft gating: {results['A_plus_gating']:.4f} ft")
    print(f"Opp  total with +{DEFAULT_GATING_FT} ft gating: {results['C_plus_gating']:.4f} ft")

    # =========================
    # PDF OUTPUT (FIXED)
    # =========================
    make_pdf = input("\nGenerate PDF calc sheet now? (y/n): ").strip().lower()
    if make_pdf in ("y", "yes"):
        print("\nWhere do you want to save the PDF?")
        print("Examples:")
        print(r"  C:\Users\colew\Desktop")
        print(r"  C:\Users\colew\Documents\Guardrail Calcs")
        out_folder = input("Folder path (Enter = current folder): ").strip()

        default_name = _safe_filename(f"{project}_guardrail_calc_sheet" if project else "guardrail_calc_sheet")
        out_name = input(f"PDF filename (Enter for '{default_name}'): ").strip()
        if not out_name:
            out_name = default_name
        out_name = _safe_filename(out_name)

        full_pdf_path = _join_path(out_folder, out_name)

        pdf_style = prompt_choice(
            "PDF style:",
            ["1 (summary)", "2 (calc boxes only)", "3 (summary + example calc boxes)"]
        )
        pdf_style_num = int(pdf_style.split()[0])
        pdf_data = build_pdf_data(
            project=project,
            facility=facility,
            speed=speed,
            adt=adt,
            LA=LA,
            L2=L2,
            L2_opp=L2_opp,
            lane_width=lane_width,
            L1=L1,
            terminal_section=terminal_section,
            a_over_b=a_over_b,
            pdf_style_num=pdf_style_num,
            results=results,
            generated_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

        try:
            appendix_used = write_calc_pdf(full_pdf_path, pdf_data, auto_open=False)
            if appendix_used:
                print(f"\nPDF written (manual appended): {full_pdf_path}")
            else:
                print(f"\nPDF written (no appendix found; calc sheet only): {full_pdf_path}")
        except Exception as e:
            print(f"\nPDF generation failed: {e}")
