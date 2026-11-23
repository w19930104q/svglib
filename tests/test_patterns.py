"""Pattern fills (userSpaceOnUse and objectBoundingBox units)."""

import pytest
from reportlab.graphics.shapes import Circle, Group, Rect

from svglib.svglib import ClippingPath
from tests.utils import drawing_from_svg


def _find_pattern_wrapper(shape):
    """Return the first Group whose first child is a pattern ClippingPath."""
    if isinstance(shape, Group) and shape.contents:
        if isinstance(shape.contents[0], ClippingPath):
            return shape
        for child in shape.contents:
            found = _find_pattern_wrapper(child)
            if found is not None:
                return found
    return None


def _tile_origins(wrapper):
    """Translations of the tile groups placed directly inside the wrapper."""
    origins = set()
    for child in wrapper.contents[1:]:
        if not isinstance(child, Group) or not child.contents:
            # The last child is the original (un-clipped) filled shape.
            continue
        if not isinstance(child.contents[0], Group):
            continue
        _a, _b, _c, _d, tx, ty = child.transform
        origins.add((round(tx, 6), round(ty, 6)))
    return sorted(origins)


def _periods(values):
    return {round(values[i + 1] - values[i], 9) for i in range(len(values) - 1)}


class TestPatterns:
    """Tests for SVG <pattern> fill support."""

    def test_pattern_fill_produces_clipped_group(self):
        """A rect with a pattern fill must be wrapped in a clipping group."""
        drawing = drawing_from_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"
                 viewBox="0 0 200 200">
              <defs>
                <pattern id="dots" patternUnits="userSpaceOnUse"
                         width="20" height="20">
                  <circle cx="5" cy="5" r="4" fill="red"/>
                </pattern>
              </defs>
              <rect x="0" y="0" width="200" height="200" fill="url(#dots)"/>
            </svg>
            """
        )
        wrapper = _find_pattern_wrapper(drawing)
        assert wrapper is not None
        assert isinstance(wrapper.contents[0], ClippingPath)
        # The clip path follows the filled shape outline.
        assert wrapper.contents[0].getBounds() == (0.0, 0.0, 200.0, 200.0)
        # The drawing still has measurable bounds (see issue #466).
        x0, y0, x1, y1 = drawing.getBounds()
        assert x1 > x0 and y1 > y0

    def test_pattern_user_space_tiling_period(self):
        """Tiles repeat with the exact pattern width/height in user units."""
        drawing = drawing_from_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"
                 viewBox="0 0 200 200">
              <defs>
                <pattern id="dots" patternUnits="userSpaceOnUse"
                         width="20" height="20">
                  <circle cx="5" cy="5" r="4" fill="red"/>
                </pattern>
              </defs>
              <rect x="10" y="10" width="180" height="180" fill="url(#dots)"/>
            </svg>
            """
        )
        wrapper = _find_pattern_wrapper(drawing)
        origins = _tile_origins(wrapper)
        xs = sorted({x for x, _ in origins})
        ys = sorted({y for _, y in origins})
        assert _periods(xs) == {20.0}
        assert _periods(ys) == {20.0}
        # Tiles are anchored on the user-space origin, not the rect origin.
        assert xs[0] == 0.0 and ys[0] == 0.0
        # The covered area spans the whole rect.
        assert xs[0] <= 10 and xs[-1] + 20 >= 190
        assert ys[0] <= 10 and ys[-1] + 20 >= 190

    def test_pattern_object_bounding_box_units(self):
        """With objectBoundingBox, tile size is a fraction of the shape bbox."""
        drawing = drawing_from_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"
                 viewBox="0 0 200 200">
              <defs>
                <pattern id="dots" patternUnits="objectBoundingBox"
                         width="0.1" height="0.1">
                  <circle cx="0.25" cy="0.25" r="0.2" fill="blue"/>
                </pattern>
              </defs>
              <rect x="0" y="0" width="200" height="200" fill="url(#dots)"/>
            </svg>
            """
        )
        wrapper = _find_pattern_wrapper(drawing)
        origins = _tile_origins(wrapper)
        xs = sorted({x for x, _ in origins})
        ys = sorted({y for _, y in origins})
        # 0.1 of the 200-unit bbox = 20 user units per tile, 10 per axis.
        assert len(xs) == 10 and len(ys) == 10
        assert _periods(xs) == {20.0}
        assert _periods(ys) == {20.0}

    def test_pattern_content_units_object_bounding_box(self):
        """patternContentUnits=objectBoundingBox scales content to the tile."""
        drawing = drawing_from_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"
                 viewBox="0 0 200 200">
              <defs>
                <pattern id="p" patternUnits="objectBoundingBox"
                         patternContentUnits="objectBoundingBox"
                         width="0.1" height="0.1">
                  <rect x="0.1" y="0.1" width="0.8" height="0.8" fill="green"/>
                </pattern>
              </defs>
              <rect x="0" y="0" width="200" height="200" fill="url(#p)"/>
            </svg>
            """
        )
        wrapper = _find_pattern_wrapper(drawing)
        # The first placement group carries a scale wrapper (0.1 of 200 = 20).
        placement = next(
            child for child in wrapper.contents if isinstance(child, Group)
        )
        scale_group = placement.contents[0]
        assert isinstance(scale_group, Group)
        sx, ry = scale_group.transform[0], scale_group.transform[3]
        assert sx == pytest.approx(20.0)
        assert ry == pytest.approx(20.0)
        inner = [
            shape
            for tile in scale_group.contents
            if isinstance(tile, Group)
            for shape in tile.contents
            if isinstance(shape, Rect)
        ]
        assert inner
        # Coordinates stay in fraction space; the scale group maps them to
        # the 20x20 user-unit tile.
        assert inner[0].x == pytest.approx(0.1)
        assert inner[0].width == pytest.approx(0.8)

    def test_pattern_xy_origin_offset(self):
        """The pattern x/y attributes shift the tiling origin."""
        drawing = drawing_from_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"
                 viewBox="0 0 200 200">
              <defs>
                <pattern id="p" patternUnits="userSpaceOnUse" x="7" y="9"
                         width="25" height="25">
                  <circle cx="5" cy="5" r="3" fill="red"/>
                </pattern>
              </defs>
              <rect x="0" y="0" width="200" height="200" fill="url(#p)"/>
            </svg>
            """
        )
        wrapper = _find_pattern_wrapper(drawing)
        origins = _tile_origins(wrapper)
        xs = sorted({x for x, _ in origins})
        ys = sorted({y for _, y in origins})
        assert _periods(xs) == {25.0}
        assert _periods(ys) == {25.0}
        assert 7.0 in xs and 9.0 in ys

    def test_pattern_default_geometry(self):
        """A pattern without width/height defaults to a 100% bbox tile."""
        drawing = drawing_from_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"
                 viewBox="0 0 200 200">
              <defs>
                <pattern id="p">
                  <circle cx="50" cy="50" r="10" fill="red"/>
                </pattern>
              </defs>
              <rect x="0" y="0" width="200" height="200" fill="url(#p)"/>
            </svg>
            """
        )
        wrapper = _find_pattern_wrapper(drawing)
        # Default objectBoundingBox width/height = 1.0: a single tile.
        assert len(_tile_origins(wrapper)) == 1

    def test_pattern_keeps_shape_stroke(self):
        """The original shape stays in the output so its stroke is painted."""
        drawing = drawing_from_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"
                 viewBox="0 0 200 200">
              <defs>
                <pattern id="p" patternUnits="userSpaceOnUse" width="20" height="20">
                  <circle cx="5" cy="5" r="4" fill="red"/>
                </pattern>
              </defs>
              <rect x="0" y="0" width="200" height="200" fill="url(#p)"
                    stroke="black" stroke-width="2"/>
            </svg>
            """
        )
        wrapper = _find_pattern_wrapper(drawing)
        rects = [shape for shape in wrapper.contents if isinstance(shape, Rect)]
        # The original rect is the wrapper's last child.
        assert isinstance(wrapper.contents[-1], Rect)
        assert wrapper.contents[-1].strokeColor is not None
        assert rects

    def test_pattern_tile_content_rendered(self):
        """Each tile contains the pattern's rendered children."""
        drawing = drawing_from_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"
                 viewBox="0 0 200 200">
              <defs>
                <pattern id="p" patternUnits="userSpaceOnUse" width="20" height="20">
                  <circle cx="5" cy="5" r="4" fill="red"/>
                </pattern>
              </defs>
              <rect x="0" y="0" width="200" height="200" fill="url(#p)"/>
            </svg>
            """
        )
        wrapper = _find_pattern_wrapper(drawing)
        # Placement groups are the wrapper's children (apart from the leading
        # ClippingPath and the trailing original rect).
        placement_groups = [
            child for child in wrapper.contents if isinstance(child, Group)
        ]
        # 100 tile slots, each carrying the shared tile with one circle.
        assert len(placement_groups) == 100
        circles = [
            shape
            for placement in placement_groups
            for tile in placement.contents
            if isinstance(tile, Group)
            for shape in tile.contents
            if isinstance(shape, Circle)
        ]
        assert len(circles) == 100
        assert all(c.r == pytest.approx(4) for c in circles)

    def test_unknown_pattern_reference_does_not_break_conversion(self):
        """A dangling url(#missing) leaves the shape convertable."""
        drawing = drawing_from_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
              <rect x="0" y="0" width="100" height="100" fill="url(#missing)"/>
            </svg>
            """
        )
        assert _find_pattern_wrapper(drawing) is None
        rects = [
            child
            for group in drawing.contents
            for child in group.contents
            if isinstance(child, Rect)
        ]
        assert len(rects) == 1

    def test_document_without_pattern_unchanged(self):
        """Pattern support must not alter documents that do not use patterns."""
        drawing = drawing_from_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
              <rect x="0" y="0" width="100" height="100" fill="green"/>
            </svg>
            """
        )
        assert _find_pattern_wrapper(drawing) is None
        rect = drawing.contents[0].contents[0]
        assert isinstance(rect, Rect)
        assert rect.fillColor is not None

    def test_pattern_definition_registered(self):
        """renderPattern stores geometry in pattern_defs keyed by id."""
        from io import BytesIO

        from svglib.svglib import SvgRenderer, load_svg_file

        svg = b"""<?xml version="1.0"?>
            <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
                <defs>
                    <pattern id="p" patternUnits="userSpaceOnUse"
                             width="15" height="25" x="3" y="4">
                        <rect width="15" height="25" fill="red"/>
                    </pattern>
                </defs>
            </svg>"""
        renderer = SvgRenderer("")
        renderer.render(load_svg_file(BytesIO(svg)))
        definition = renderer.pattern_defs["p"]
        assert definition["patternUnits"] == "userSpaceOnUse"
        assert definition["width"] == 15.0
        assert definition["height"] == 25.0
        assert definition["x"] == 3.0
        assert definition["y"] == 4.0
        assert renderer.definitions["p"] is not None

    def test_pattern_shared_between_shapes_with_different_bbox(self):
        """A cached bbox-content tile scales correctly for every referencing shape."""
        drawing = drawing_from_svg(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"
                 viewBox="0 0 400 200">
              <defs>
                <pattern id="p" patternUnits="objectBoundingBox"
                         patternContentUnits="objectBoundingBox"
                         width="0.5" height="0.5">
                  <rect x="0" y="0" width="1" height="1" fill="red"/>
                </pattern>
              </defs>
              <rect x="0" y="0" width="100" height="100" fill="url(#p)"/>
              <rect x="200" y="0" width="200" height="200" fill="url(#p)"/>
            </svg>
            """
        )
        wrappers = []

        def collect(shape):
            if isinstance(shape, Group) and shape.contents:
                if isinstance(shape.contents[0], ClippingPath):
                    wrappers.append(shape)
                for child in shape.contents:
                    collect(child)

        collect(drawing)
        assert len(wrappers) == 2
        scales = []
        for wrapper in wrappers:
            placement = next(
                child for child in wrapper.contents if isinstance(child, Group)
            )
            scale_group = placement.contents[0]
            scales.append((scale_group.transform[0], scale_group.transform[3]))
        # Tiles are 0.5 of each bbox: 50 units for the first rect, 100 for
        # the second — the shared cached tile must not freeze the first scale.
        assert scales == [pytest.approx((50.0, 50.0)), pytest.approx((100.0, 100.0))]

    def test_pattern_href_inheritance(self):
        """A pattern referencing another via href inherits its geometry."""
        from io import BytesIO

        from svglib.svglib import SvgRenderer, load_svg_file

        svg = b"""<?xml version="1.0"?>
            <svg xmlns="http://www.w3.org/2000/svg"
                 xmlns:xlink="http://www.w3.org/1999/xlink"
                 width="100" height="100">
                <defs>
                    <pattern id="base" width="30" height="40">
                        <circle cx="5" cy="5" r="4" fill="red"/>
                    </pattern>
                    <pattern id="derived" xlink:href="#base" x="7"/>
                </defs>
            </svg>"""
        renderer = SvgRenderer("")
        renderer.render(load_svg_file(BytesIO(svg)))
        resolved = renderer._resolve_pattern("derived")
        assert resolved is not None
        assert resolved["width"] == 30.0
        assert resolved["height"] == 40.0
        assert resolved["x"] == 7.0
        # The tile content comes from the referenced pattern.
        node = renderer._pattern_node("derived")
        assert node is not None
        assert node.attrib.get("id") == "base"
