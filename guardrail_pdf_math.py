"""Searchable vector equations using MathText's textbook math spacing."""

from matplotlib.font_manager import FontProperties
from matplotlib.mathtext import MathTextParser
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable


_PARSER = MathTextParser("path")
_FONT = FontProperties(size=12, math_fontfamily="stix")


class MathEquation(Flowable):
    """Align left-hand symbols and relation signs across successive equations."""

    def __init__(self, lhs: str, expression: str, relation: str = "="):
        super().__init__()
        self.parts = [_PARSER.parse(f"${text}$", dpi=72, prop=_FONT) if text else None
                      for text in (lhs, relation, expression)]
        self.depth = max(part.depth for part in self.parts if part is not None)
        ascent = max(part.height - part.depth for part in self.parts if part is not None)
        self.height = ascent + self.depth + 6
        self.width = 70 + self.parts[2].width
        self.spaceAfter = 2

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setFillColorRGB(0, 0, 0)
        baseline = self.depth + 3
        for index, part in enumerate(self.parts):
            if part is None:
                continue
            x = 48 - part.width if index == 0 else (54 if index == 1 else 70)
            runs = []
            for glyph in part.glyphs:
                font, size, codepoint = glyph[:3]
                # Matplotlib 3.11 inserts a glyph index before the x/y offsets.
                offset_x, offset_y = glyph[-2:]
                name = "GRMath-" + font.postscript_name
                if name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(name, font.fname))
                char = chr(codepoint)
                if (runs and runs[-1][0:2] == [name, size] and runs[-1][3] == offset_y
                        and abs(offset_x - runs[-1][5]) < 0.15):
                    runs[-1][4] += char
                    runs[-1][5] += pdfmetrics.stringWidth(char, name, size)
                else:
                    runs.append([name, size, offset_x, offset_y, char,
                                 offset_x + pdfmetrics.stringWidth(char, name, size)])
            for name, size, offset_x, offset_y, text, _ in runs:
                canvas.setFont(name, size)
                canvas.drawString(x + offset_x, baseline + offset_y, text)
            for offset_x, offset_y, width, height in part.rects:
                canvas.rect(x + offset_x, baseline + offset_y, width, height, stroke=0, fill=1)
        canvas.restoreState()
