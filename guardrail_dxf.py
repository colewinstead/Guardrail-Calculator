"""DXF serialization of an already generated drawing; no engineering decisions."""

from pathlib import Path
from guardrail_drawing import DrawingGeometry, DrawingInputs, GeometryBuilder, build_drawing
from guardrail_design import (
    LAYERS, BRIDGE_END_SECTION, GATING_LENGTH, SHOULDER_FLARE_LENGTH,
    SHOULDER_TRANSITION_LENGTH, NORMAL_SHOULDER_EXTENSION, PATH_TOLERANCE,
    TEXT_HEIGHT, ENGINEERING_TEXT_STYLE, ENGINEERING_FONT_FILE,
    SHOULDER_CLEARANCE_BEHIND_RAIL, TERMINAL_LATERAL_FLARE,
    TERMINAL_END_LATERAL_FLARE, GATING_LATERAL_FLARE,
    TERMINAL_SHOULDER_CLEARANCE, GUARDRAIL_POST_SPACING,
)


def serialize_dxf(path: str | Path, drawing: DrawingGeometry) -> None:
    insunits = drawing.insunits
    try:
        import ezdxf
    except ImportError as exc:
        raise RuntimeError("DXF export requires ezdxf. Install it with: py -m pip install ezdxf") from exc
    doc = ezdxf.new("R2000", setup=False)
    doc.header["$INSUNITS"] = int(insunits)
    if not doc.styles.has_entry(ENGINEERING_TEXT_STYLE):
        doc.styles.add(ENGINEERING_TEXT_STYLE, font=ENGINEERING_FONT_FILE)
    # Match the Superelevation Calculator's MDOT/ORD handoff. The extended
    # family data makes ORD treat EngineeringRegular.ttf as TrueType rather
    # than attempting to resolve it as a missing SHX font.
    engineering_style = doc.styles.get(ENGINEERING_TEXT_STYLE)
    engineering_style.dxf.font = ENGINEERING_FONT_FILE
    engineering_style.set_extended_font_data(
        family=ENGINEERING_TEXT_STYLE,
        italic=False,
        bold=False,
    )
    styles = {
        LAYERS["alignment"]: (8, 18), LAYERS["road"]: (7, 35), LAYERS["bridge"]: (7, 50),
        LAYERS["lane"]: (8, 18), LAYERS["shoulder"]: (3, 25), LAYERS["normal_shoulder"]: (3, 25),
        LAYERS["foreslope"]: (94, 18), LAYERS["rail"]: (1, 50), LAYERS["post"]: (1, 35),
        LAYERS["terminal"]: (30, 50), LAYERS["gating"]: (6, 50), LAYERS["dimension"]: (5, 18),
        LAYERS["leader"]: (8, 18), LAYERS["text"]: (7, 18), LAYERS["traffic"]: (7, 35),
    }
    if not doc.linetypes.has_entry("DASHED"):
        doc.linetypes.add("DASHED", pattern=[0.6, 0.3, -0.3], description="Guardrail shoulder line")
    for layer, (color, weight) in styles.items():
        linetype = "DASHED" if layer == LAYERS["normal_shoulder"] else "CONTINUOUS"
        if not doc.layers.has_entry(layer): doc.layers.add(layer, color=color, linetype=linetype)
        doc.layers.get(layer).dxf.linetype = linetype
        doc.layers.get(layer).dxf.lineweight = weight
    space = doc.modelspace()
    from ezdxf.enums import TextEntityAlignment

    for record in drawing.records:
        if record[0] == "LINE":
            _, x1, y1, x2, y2, layer = record
            space.add_line((x1, y1, 0), (x2, y2, 0), dxfattribs={"layer": layer})
        else:
            _, x, y, text, height, layer, rotation, alignment = record
            space.add_text(
                text,
                dxfattribs={
                    "height": height,
                    "rotation": rotation,
                    "layer": layer,
                    "style": ENGINEERING_TEXT_STYLE,
                },
            ).set_placement(
                (x, y, 0),
                align=(
                    TextEntityAlignment.MIDDLE_CENTER
                    if alignment == "CENTER"
                    else TextEntityAlignment.LEFT
                ),
            )
    doc.saveas(path)


def export_guardrail_dxf(path: str | Path, model: DrawingInputs) -> DrawingGeometry:
    drawing = build_drawing(model)
    serialize_dxf(path, drawing)
    return drawing


class DxfWriter(GeometryBuilder):
    """Compatibility builder; geometry construction itself has no file operations."""
    def save(self, path: str | Path, insunits: int = 2) -> None:
        serialize_dxf(path, self.build(insunits))

from guardrail_alignment import LineAlignment, _point, _path, _taper_path
from guardrail_drawing import (_upright_angle, validate_supported_installations, validate_model, _dimension, _callout, _arrow, _feet, _installation)

# Backward-compatible configuration name; generated geometry is DrawingGeometry.
DrawingModel = DrawingInputs
