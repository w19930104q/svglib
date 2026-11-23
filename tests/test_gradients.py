"""Linear and radial gradients."""

from io import BytesIO

import pytest
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import (
    Group,
    Rect,
)
from reportlab.lib import colors

from svglib.svglib import LinearGradientShape
from tests.utils import (
    drawing_from_svg,
)


def _render_pdf(svg_content: str) -> bytes:
    """Render an SVG string to PDF bytes through the real PDF renderer."""
    drawing = drawing_from_svg(svg_content)
    buffer = BytesIO()
    renderPDF.drawToFile(drawing, buffer, showBoundary=0)
    return buffer.getvalue()


# A red -> blue horizontal gradient with a fully transparent first stop.
_TRANSLUCENT_GRADIENT_SVG = """
    <?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
        <defs>
            <linearGradient id="grad1" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0" stop-color="red" stop-opacity="0"/>
                <stop offset="1" stop-color="blue" stop-opacity="1"/>
            </linearGradient>
        </defs>
        <rect x="0" y="0" width="80" height="80" fill="url(#grad1)"/>
    </svg>
"""


class TestGradients:
    """Tests for SVG linearGradient and radialGradient support."""

    @staticmethod
    def _find_groups(shape):
        """Recursively collect all Group objects in a drawing."""
        from reportlab.graphics.shapes import Group as RLGroup

        result = []
        if isinstance(shape, RLGroup):
            result.append(shape)
        if hasattr(shape, "contents"):
            for item in shape.contents:
                result.extend(TestGradients._find_groups(item))
        return result

    def test_linear_gradient_rect(self):
        """A rect with a linearGradient fill must produce a Group (not a bare Rect)."""
        drawing = drawing_from_svg(
            """
            <?xml version="1.0"?>
            <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
                <defs>
                    <linearGradient id="grad1" x1="0" y1="0" x2="1" y2="0"
                                    gradientUnits="objectBoundingBox">
                        <stop offset="0" stop-color="red" stop-opacity="1"/>
                        <stop offset="1" stop-color="blue" stop-opacity="1"/>
                    </linearGradient>
                </defs>
                <rect x="10" y="10" width="80" height="80" fill="url(#grad1)"/>
            </svg>
        """
        )
        groups = self._find_groups(drawing)
        # The rect's fill must have been replaced by a gradient group
        assert len(groups) > 1
        # The gradient shape must implement getBounds() so the drawing can be
        # measured (e.g. when used as a flowable by rst2pdf); see issue #466.
        x0, y0, x1, y1 = drawing.getBounds()
        assert x1 > x0 and y1 > y0

    def test_radial_gradient_circle(self):
        """A circle with a radialGradient fill must produce a Group."""
        drawing = drawing_from_svg(
            """
            <?xml version="1.0"?>
            <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
                <defs>
                    <radialGradient id="rgrad" cx="0.5" cy="0.5" r="0.5"
                                    gradientUnits="objectBoundingBox">
                        <stop offset="0" stop-color="yellow" stop-opacity="1"/>
                        <stop offset="1" stop-color="green" stop-opacity="1"/>
                    </radialGradient>
                </defs>
                <circle cx="50" cy="50" r="40" fill="url(#rgrad)"/>
            </svg>
        """
        )
        groups = self._find_groups(drawing)
        assert len(groups) > 1
        # See issue #466: the gradient shape must implement getBounds().
        x0, y0, x1, y1 = drawing.getBounds()
        assert x1 > x0 and y1 > y0

    def test_gradient_stops_parsed(self):
        """Stop colors and offsets must be correctly stored in gradient_defs."""
        from io import BytesIO

        from svglib.svglib import SvgRenderer, load_svg_file

        svg_content = b"""<?xml version="1.0"?>
            <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
                <defs>
                    <linearGradient id="g1">
                        <stop offset="0" stop-color="#ff0000" stop-opacity="1"/>
                        <stop offset="0.5" stop-color="#00ff00" stop-opacity="0.5"/>
                        <stop offset="1" stop-color="#0000ff" stop-opacity="1"/>
                    </linearGradient>
                </defs>
            </svg>"""
        root = load_svg_file(BytesIO(svg_content))
        renderer = SvgRenderer("")
        renderer.render(root)
        grad = renderer.gradient_defs.get("g1")
        assert grad is not None
        assert len(grad["stops"]) == 3
        assert grad["stops"][0][0] == 0.0
        assert grad["stops"][1][0] == 0.5
        assert grad["stops"][2][0] == 1.0

    def test_gradient_href_inheritance(self):
        """A gradient that references another via href must inherit its stops."""
        from io import BytesIO

        from svglib.svglib import SvgRenderer, load_svg_file

        svg_content = b"""<?xml version="1.0"?>
            <svg xmlns="http://www.w3.org/2000/svg"
                 xmlns:xlink="http://www.w3.org/1999/xlink"
                 width="100" height="100">
                <defs>
                    <linearGradient id="base">
                        <stop offset="0" stop-color="red"/>
                        <stop offset="1" stop-color="blue"/>
                    </linearGradient>
                    <linearGradient id="derived" xlink:href="#base"
                                    x1="0" y1="0" x2="0" y2="1"/>
                </defs>
            </svg>"""
        root = load_svg_file(BytesIO(svg_content))
        renderer = SvgRenderer("")
        renderer.render(root)
        resolved = renderer._resolve_gradient("derived")
        assert resolved is not None
        assert len(resolved["stops"]) == 2  # inherited from "base"
        assert resolved["x2"] == 0.0  # from derived
        assert resolved["y2"] == 1.0  # from derived

    def test_gradient_userSpaceOnUse(self):
        """A gradient with gradientUnits=userSpaceOnUse must also produce a Group."""
        drawing = drawing_from_svg(
            """
            <?xml version="1.0"?>
            <svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">
                <defs>
                    <linearGradient id="usg" x1="0" y1="0" x2="200" y2="0"
                                    gradientUnits="userSpaceOnUse">
                        <stop offset="0" stop-color="black"/>
                        <stop offset="1" stop-color="white"/>
                    </linearGradient>
                </defs>
                <rect x="0" y="0" width="200" height="200" fill="url(#usg)"/>
            </svg>
        """
        )
        groups = self._find_groups(drawing)
        assert len(groups) > 1

    def test_gradient_stop_opacity_in_style(self):
        """Stop opacity specified in a style attribute must be respected."""
        from io import BytesIO

        from svglib.svglib import SvgRenderer, load_svg_file

        svg_content = b"""<?xml version="1.0"?>
            <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
                <defs>
                    <linearGradient id="g2">
                        <stop offset="0"
                              style="stop-color:rgb(255,0,0);stop-opacity:0.5"/>
                        <stop offset="1"
                              style="stop-color:#0000ff;stop-opacity:1"/>
                    </linearGradient>
                </defs>
            </svg>"""
        root = load_svg_file(BytesIO(svg_content))
        renderer = SvgRenderer("")
        renderer.render(root)
        grad = renderer.gradient_defs.get("g2")
        assert grad is not None
        stop0_color = grad["stops"][0][1]
        assert stop0_color.alpha == pytest.approx(0.5)

    def _get_svg(self, fill, name):
        return f"""
            <?xml version="1.0"?>
            <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
                <defs>
                    <linearGradient id="{name}" x1="0" y1="0" x2="1" y2="0"
                            gradientUnits="objectBoundingBox">
                        <stop offset="0" stop-color="red" stop-opacity="1"/>
                        <stop offset="1" stop-color="blue" stop-opacity="1"/>
                    </linearGradient>
                </defs>
                <rect x="10" y="10" width="80" height="80" fill={fill}/>
            </svg>"""

    def _process_test_fill_url(self, fill, name="grad1"):
        """Process test fill url."""
        drawing = drawing_from_svg(self._get_svg(fill, name))

        assert len(drawing.contents) == 1
        group = drawing.contents[0]
        assert isinstance(group, Group)

        assert len(group.contents) == 1
        group2 = group.contents[0]
        assert isinstance(group2, Group)

        gradient, rect = group2.contents
        assert isinstance(gradient, LinearGradientShape)
        assert isinstance(rect, Rect)

        assert gradient._positions == [0.0, 1.0]
        assert gradient._rl_colors == [
            colors.Color(1, 0, 0, 1),
            colors.Color(0, 0, 1, 1),
        ]

    def test_fill_url_witout_quotes(self):
        """Fill url witout quotes."""
        self._process_test_fill_url('"url(#grad1)"')

    def test_fill_url_witout_quotes_space(self):
        """Fill url witout quotes."""
        self._process_test_fill_url('"url(#grad 1)"', "grad 1")

    def test_fill_url_witout_quotes_parenthesis(self):
        """Fill url witout quotes."""
        self._process_test_fill_url('"url(#grad)1)"', "grad)1")

    def test_fill_url_witout_quotes_strip(self):
        """Fill url witout quotes."""
        self._process_test_fill_url('"url( #grad1 )"')

    def test_fill_url_witout_quotes_strip_space(self):
        """Fill url witout quotes."""
        self._process_test_fill_url('"url( #grad 1 )"', "grad 1")

    def test_fill_url_enclosed_single_quotes(self):
        """Fill url enclosed single quotes."""
        self._process_test_fill_url('''"url('#grad1')"''')

    def test_fill_url_enclosed_single_quotes_space(self):
        """Fill url enclosed single quotes."""
        self._process_test_fill_url('''"url('#grad 1')"''', "grad 1")

    def test_fill_url_enclosed_single_quotes_strip(self):
        """Fill url enclosed single quotes."""
        self._process_test_fill_url('''"url( '#grad1' )"''')

    def test_fill_url_enclosed_single_quotes_strip_space(self):
        """Fill url enclosed single quotes."""
        self._process_test_fill_url('''"url( '#grad 1' )"''', "grad 1")

    def test_fill_url_enclosed_double_quotes(self):
        """Fill url enclosed double quotes."""
        self._process_test_fill_url("""'url("#grad1")'""")

    def test_fill_url_enclosed_double_quotes_parenthesis(self):
        """Fill url enclosed double quotes."""
        self._process_test_fill_url("""'url("#grad())1")'""", "grad())1")

    def test_fill_url_enclosed_double_quotes_strip(self):
        """Fill url enclosed double quotes."""
        self._process_test_fill_url("""'url( "#grad1" )'""")

    def test_fill_url_enclosed_double_quotes_strip_space(self):
        """Fill url enclosed double quotes."""
        self._process_test_fill_url("""'url( "#grad 1" )'""", "grad 1")

    def test_fill_url_enclosed_double_quotes_strip_parenthesis(self):
        """Fill url enclosed double quotes."""
        self._process_test_fill_url("""'url( "#grad)1" )'""", "grad)1")

    def test_opaque_gradient_uses_plain_shading(self):
        """An opaque gradient must stay a single shading, without soft masks."""
        svg = """
            <?xml version="1.0"?>
            <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
                <defs>
                    <linearGradient id="grad1" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0" stop-color="red"/>
                        <stop offset="1" stop-color="blue"/>
                    </linearGradient>
                </defs>
                <rect x="0" y="0" width="80" height="80" fill="url(#grad1)"/>
            </svg>
        """
        pdf = _render_pdf(svg)
        assert b"/ShadingType 2" in pdf
        # No transparency machinery is needed when every stop is opaque.
        assert b"/SMask" not in pdf
        assert b"/Luminosity" not in pdf

    def test_stop_opacity_emits_soft_mask(self):
        """A translucent stop must survive into the PDF as an alpha soft mask.

        ReportLab's canvas gradient API drops the alpha channel, so svglib
        has to emit a DeviceGray alpha shading wrapped in a luminosity
        /SMask graphics state rather than only the RGB shading.
        """
        pdf = _render_pdf(_TRANSLUCENT_GRADIENT_SVG)
        # The color gradient stays an RGB axial shading ...
        assert b"/ShadingType 2" in pdf
        assert b"/DeviceRGB" in pdf
        # ... and the per-stop opacity is represented as a gray shading used
        # by a luminosity soft mask (white = opaque, black = transparent).
        assert b"/DeviceGray" in pdf
        assert b"/Luminosity" in pdf
        assert b"/SMask" in pdf

    def test_stop_opacity_zero_is_black_in_mask(self):
        """The alpha shading must interpolate from black (opacity 0) to white."""
        pdf = _render_pdf(_TRANSLUCENT_GRADIENT_SVG)
        # The gray function's C0/C1 encode the stop-opacity values 0 and 1.
        assert b"/C0 [ 0 ]" in pdf
        assert b"/C1 [ 1 ]" in pdf

    def test_soft_mask_keeps_clip_inside_forms(self):
        """The clip path must live in the form streams, not on the page state.

        A page-level clip combined with an active soft mask makes viewers
        zero the mask coverage outside the clip, so the clip operators are
        emitted inside each shading form instead.
        """
        pdf = _render_pdf(_TRANSLUCENT_GRADIENT_SVG)
        assert b"/Subtype /Form" in pdf
        # Clip operators appear in a form stream together with the shading.
        assert b"W* n" in pdf

    def test_radial_gradient_stop_opacity(self):
        """Radial gradients must also carry their stop opacity into the PDF."""
        svg = """
            <?xml version="1.0"?>
            <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
                <defs>
                    <radialGradient id="rg" cx="0.5" cy="0.5" r="0.5">
                        <stop offset="0" stop-color="red" stop-opacity="1"/>
                        <stop offset="1" stop-color="blue" stop-opacity="0"/>
                    </radialGradient>
                </defs>
                <circle cx="50" cy="50" r="40" fill="url(#rg)"/>
            </svg>
        """
        pdf = _render_pdf(svg)
        assert b"/ShadingType 3" in pdf  # radial shading
        assert b"/Luminosity" in pdf
        assert b"/SMask" in pdf

    def test_solid_fill_unaffected_by_gradient_code(self):
        """A plain solid fill must produce no shading or soft mask objects."""
        svg = """
            <?xml version="1.0"?>
            <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
                <rect x="0" y="0" width="80" height="80" fill="green"/>
            </svg>
        """
        pdf = _render_pdf(svg)
        assert b"/ShadingType" not in pdf
        assert b"/SMask" not in pdf
        assert b"/Luminosity" not in pdf
