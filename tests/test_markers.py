"""Markers: marker-start, marker-mid and marker-end on markable shapes."""

import math

from reportlab.graphics.shapes import Circle, Group, Path
from reportlab.graphics.transform import mmult

from tests.utils import drawing_from_svg

DOT_MARKER = """
    <marker id="dot" markerWidth="10" markerHeight="10" refX="5" refY="5">
      <circle cx="5" cy="5" r="4" fill="red"/>
    </marker>
"""


def find_circles(shape, transform=(1, 0, 0, 1, 0, 0)):
    """Return the absolute (cx, cy, r) of every circle below a shape."""
    transform = mmult(transform, getattr(shape, "transform", (1, 0, 0, 1, 0, 0)))
    found = []
    if isinstance(shape, Circle):
        a, b, c, d, e, f = transform
        found.append(
            (
                a * shape.cx + c * shape.cy + e,
                b * shape.cx + d * shape.cy + f,
                math.hypot(a, b) * shape.r,
            )
        )
    for child in getattr(shape, "contents", []):
        found.extend(find_circles(child, transform))
    return found


def svg_with(body, markers=DOT_MARKER, size="300x120"):
    width, height = (int(v) for v in size.split("x"))
    return f"""
        <svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
             viewBox="0 0 {width} {height}">
          <defs>{markers}</defs>
          {body}
        </svg>
    """


class TestMarkerPlacement:
    def test_polyline_start_mid_end(self):
        """Markers are drawn on every vertex of a polyline."""
        drawing = drawing_from_svg(
            svg_with(
                '<polyline points="20,60 150,20 280,60" fill="none" stroke="black" '
                'stroke-width="2" marker-start="url(#dot)" marker-mid="url(#dot)" '
                'marker-end="url(#dot)"/>'
            )
        )
        circles = find_circles(drawing)
        assert len(circles) == 3
        # refX/refY center the marker on each vertex; the root group scales
        # user units to points (0.75) and flips y over the 120px height.
        expected = [(20, 60), (150, 20), (280, 60)]
        for (cx, cy, r), (vx, vy) in zip(sorted(circles), sorted(expected)):
            assert cx == vx * 0.75
            assert cy == (120 - vy) * 0.75
            # markerUnits defaults to strokeWidth: r = 4 * stroke-width 2.
            assert r == 4 * 2 * 0.75

    def test_path_end_marker(self):
        """A path gets a marker on its last vertex."""
        drawing = drawing_from_svg(
            svg_with(
                '<path d="M 20 60 L 280 60" fill="none" stroke="black" '
                'marker-end="url(#dot)"/>'
            )
        )
        circles = find_circles(drawing)
        assert len(circles) == 1
        cx, cy, _ = circles[0]
        assert (cx, cy) == (280 * 0.75, (120 - 60) * 0.75)

    def test_no_marker_leaves_shape_unwrapped(self):
        """A shape without markers is rendered exactly as before."""
        drawing = drawing_from_svg(
            svg_with(
                '<polyline points="20,60 150,20 280,60" fill="none" stroke="black"/>'
            )
        )

        def count_groups(shape):
            return sum(
                (1 + count_groups(child))
                if isinstance(child, Group)
                else count_groups(child)
                for child in getattr(shape, "contents", [])
            )

        # Only the root viewport group; no marker wrapper groups.
        assert count_groups(drawing) == 1
        assert find_circles(drawing) == []

    def test_marker_none(self):
        """marker-start="none" draws no marker."""
        drawing = drawing_from_svg(
            svg_with(
                '<path d="M 20 60 L 280 60" fill="none" stroke="black" '
                'marker-start="none" marker-end="url(#dot)"/>'
            )
        )
        assert len(find_circles(drawing)) == 1

    def test_marker_shorthand(self):
        """The marker shorthand sets start, mid and end at once."""
        drawing = drawing_from_svg(
            svg_with(
                '<polyline points="20,60 150,20 280,60" fill="none" stroke="black" '
                'marker="url(#dot)"/>'
            )
        )
        assert len(find_circles(drawing)) == 3

    def test_marker_inherited_from_group(self):
        """Marker properties inherit from ancestor elements."""
        drawing = drawing_from_svg(
            svg_with(
                '<g marker-end="url(#dot)">'
                '<path d="M 20 60 L 280 60" fill="none" stroke="black"/>'
                "</g>"
            )
        )
        assert len(find_circles(drawing)) == 1

    def test_undefined_marker_is_ignored(self):
        drawing = drawing_from_svg(
            svg_with(
                '<path d="M 20 60 L 280 60" fill="none" stroke="black" '
                'marker-end="url(#missing)"/>'
            )
        )
        assert find_circles(drawing) == []

    def test_closed_path_start_and_end_share_first_vertex(self):
        """On a closed subpath, start and end markers land on the same point."""
        drawing = drawing_from_svg(
            svg_with(
                '<path d="M 20 20 L 100 20 L 100 100 Z" fill="none" stroke="black" '
                'marker="url(#dot)"/>'
            )
        )
        circles = find_circles(drawing)
        # start + end on (20, 20), mid on (100, 20) and (100, 100)
        assert len(circles) == 4
        positions = sorted((round(cx, 3), round(cy, 3)) for cx, cy, _ in circles)
        assert positions == sorted(
            [
                (x * 0.75, (120 - y) * 0.75)
                for x, y in [(20, 20), (20, 20), (100, 20), (100, 100)]
            ]
        )

    def test_user_space_on_use_ignores_stroke_width(self):
        """markerUnits="userSpaceOnUse" does not scale by the stroke width."""
        markers = """
            <marker id="dot" markerWidth="10" markerHeight="10" refX="5" refY="5"
                    markerUnits="userSpaceOnUse">
              <circle cx="5" cy="5" r="4" fill="red"/>
            </marker>
        """
        drawing = drawing_from_svg(
            svg_with(
                '<path d="M 20 60 L 280 60" fill="none" stroke="black" '
                'stroke-width="4" marker-end="url(#dot)"/>',
                markers=markers,
            )
        )
        _, _, r = find_circles(drawing)[0]
        assert r == 4 * 0.75

    def test_viewbox_scales_marker_content(self):
        """The marker viewBox is mapped onto markerWidth/markerHeight."""
        markers = """
            <marker id="dot" markerWidth="20" markerHeight="20" refX="5" refY="5"
                    viewBox="0 0 10 10">
              <circle cx="5" cy="5" r="4" fill="red"/>
            </marker>
        """
        drawing = drawing_from_svg(
            svg_with(
                '<path d="M 20 60 L 280 60" fill="none" stroke="black" '
                'marker-end="url(#dot)"/>',
                markers=markers,
            )
        )
        cx, cy, r = find_circles(drawing)[0]
        # viewBox 10x10 -> viewport 20x20: scale 2, refX/refY in viewBox units.
        assert (cx, cy) == (280 * 0.75, (120 - 60) * 0.75)
        assert r == 4 * 2 * 0.75


class TestMarkerOrientation:
    ARROW = """
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="5" refY="5"
                orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="blue"/>
        </marker>
    """

    def arrow_angles(self, drawing):
        """Return the rotation angle of every filled path below a shape."""
        angles = []

        def walk(shape, transform):
            transform = mmult(
                transform, getattr(shape, "transform", (1, 0, 0, 1, 0, 0))
            )
            if isinstance(shape, Path) and shape.fillColor is not None:
                a, b = transform[0], transform[1]
                angles.append(math.degrees(math.atan2(b, a)))
            for child in getattr(shape, "contents", []):
                walk(child, transform)

        walk(drawing, (1, 0, 0, 1, 0, 0))
        return angles

    def test_orient_auto_follows_path_direction(self):
        """orient="auto" rotates markers to the direction of the path."""
        drawing = drawing_from_svg(
            svg_with(
                '<polyline points="20,60 150,60 280,20" fill="none" stroke="black" '
                'marker="url(#arrow)"/>',
                markers=self.ARROW,
            )
        )
        angles = self.arrow_angles(drawing)
        assert len(angles) == 3
        # y is flipped at the root, so SVG angles appear negated.
        outgoing = math.degrees(math.atan2(-40, 130))
        bisector = outgoing / 2
        assert sorted(angles) == sorted([0.0, -bisector, -outgoing])

    def test_orient_defaults_to_zero(self):
        """Without orient="auto", markers keep their own orientation."""
        markers = self.ARROW.replace('orient="auto"', "")
        drawing = drawing_from_svg(
            svg_with(
                '<path d="M 20 20 L 280 100" fill="none" stroke="black" '
                'marker-end="url(#arrow)"/>',
                markers=markers,
            )
        )
        assert self.arrow_angles(drawing) == [0.0]

    def test_auto_start_reverse(self):
        """orient="auto-start-reverse" adds 180° to the path direction."""
        markers = self.ARROW.replace('orient="auto"', 'orient="auto-start-reverse"')
        drawing = drawing_from_svg(
            svg_with(
                '<path d="M 20 60 L 280 60" fill="none" stroke="black" '
                'marker-start="url(#arrow)"/>',
                markers=markers,
            )
        )
        assert abs(self.arrow_angles(drawing)[0]) == 180.0


class TestMarkerShapes:
    """Markers apply to every markable element, not only paths."""

    def test_line(self):
        drawing = drawing_from_svg(
            svg_with(
                '<line x1="20" y1="60" x2="280" y2="60" stroke="black" '
                'marker-start="url(#dot)" marker-end="url(#dot)"/>'
            )
        )
        assert len(find_circles(drawing)) == 2

    def test_rect(self):
        drawing = drawing_from_svg(
            svg_with(
                '<rect x="20" y="20" width="80" height="40" fill="none" '
                'stroke="black" marker="url(#dot)"/>'
            )
        )
        # Closed shape: start and end share the first corner.
        assert len(find_circles(drawing)) == 5

    def test_circle(self):
        drawing = drawing_from_svg(
            svg_with(
                '<circle cx="150" cy="60" r="40" fill="none" stroke="black" '
                'marker="url(#dot)"/>'
            )
        )
        # Four vertices, the first one carrying both start and end. The
        # referenced circle itself is filtered out by its larger radius.
        markers = [c for c in find_circles(drawing) if c[2] < 10]
        assert len(markers) == 5

    def test_shape_transform_moves_markers(self):
        """The transform of the referencing shape applies to its markers."""
        drawing = drawing_from_svg(
            svg_with(
                '<line x1="0" y1="0" x2="100" y2="0" stroke="black" '
                'transform="translate(50 60)" marker-end="url(#dot)"/>'
            )
        )
        cx, cy, _ = find_circles(drawing)[0]
        assert (cx, cy) == (150 * 0.75, (120 - 60) * 0.75)
