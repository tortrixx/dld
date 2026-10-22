#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""audit_diagram.py -- objective geometry auditor for generated SVG block diagrams.

WHY
    Diagram generators in this repo draw an SVG *and* emit a sidecar layout JSON
    that describes exactly what was drawn (boxes, zones, wires, labels).  The
    auditor reads that sidecar -- never the SVG -- and applies purely geometric,
    deterministic checks, so "the diagram looks cramped / a wire runs through a
    box" becomes a machine-checkable fact instead of a matter of taste.

USAGE
    python scripts/audit_diagram.py <layout.json> [--json] [--quiet] [--fidelity]

    exit 0   no ERROR-level violation
    exit 1   at least one ERROR-level violation (or unreadable/invalid input)
    --json   print the complete machine-readable report followed by the SCORE
             line, instead of the human table (so stdout is JSON + one final
             "SCORE <number>" line; --quiet then has no effect)
    --quiet  human output reduced to ERROR findings + the SCORE line
    --fidelity
             additionally cross-check the layout against scripts/arch_data.py
             (authoritative logical graph); skipped with a clear message when
             that module is absent or lacks the required names.

OUTPUT CONTRACT
    * a human-readable table grouped by code, with coordinates, and
    * exactly one final machine-readable line:  ``SCORE <number>``
      (also embedded in --json as the ``score`` field).

INPUT SCHEMA (all coordinates in SVG user units, y grows downward, floats allowed)
    {
      "id": "cand_A",
      "canvas": {"w": 2400, "h": 1500},
      "boxes": [{"id","kind":"entity|ext|glue","x","y","w","h",
                 "title","sub"?,"title_size"?,"sub_size"?,"globals"?}],
      "zones": [{"id","x","y","w","h","title"?}],
      "wires": [{"id","from","to","from_side"?,"to_side"?,"pts":[[x,y],...],
                 "nets"?,"label"?:{"text","x","y","anchor"?,"size"?,"lines"?},"width_px"?}]
    }

REQUIRED FIELDS (everything else is optional; a missing optional field is not an error)
    root   : id (non-empty string), canvas{w>0,h>0}, boxes (list), wires (list)
             zones is optional and defaults to []
    box    : id, kind, x, y, w, h, title          (w>0, h>0)
    zone   : id, x, y, w, h                       (w>0, h>0)
    wire   : id, from, to, pts (>=2 points)       (a point is [x,y], both finite)
    label  : text, x, y                           (anchor defaults "middle",
                                                   size defaults 13.5)

LABEL BOUNDING-BOX HEURISTIC (documented as required)
    A wire label's box is estimated from its text, not measured:
        char_px = 0.62 * size       for ASCII characters
        char_px = 1.00 * size       for CJK / full-width characters
                                    (detected with ``ord(c) > 0x2E7F``)
        width   = sum(char_px) + 12 px horizontal padding
        height  = 22 px total, times the number of drawn lines
    A label may optionally carry ``"lines": ["line 1", "line 2", ...]`` for a
    multi-line label: the box width then comes from the WIDEST line and the height
    is ``22 * len(lines)``.  ``text`` stays required and is what the human report
    prints; ``lines`` only refines the geometry.  Absent ``lines``, the label is
    one 22 px line, as before.
    ``size`` is ``label.size`` (default 13.5).  Horizontal placement follows
    ``anchor``: "start" -> x is the left edge, "end" -> x is the right edge,
    "middle" (default) -> x is the centre.  MODELLING CHOICE: ``y`` is treated
    as the *vertical centre* of the text block, so the box is
    ``[y - h/2, y + h/2]``.  (A baseline model would be
    ``[y - 0.80*size, y + 0.22*size]``; change ``label_rect()`` if the
    generator ever switches to SVG's alphabetic baseline.)

CHECKS, TOLERANCES AND THEIR EXACT MEANING
  E-SCHEMA       missing/invalid required fields, non-numeric or non-finite
                 coordinates, w/h <= 0, pts with fewer than 2 points, malformed
                 point, wire referencing an unknown box id, duplicate ids within
                 one collection (boxes / zones / wires), wrong JSON types.
                 A malformed box/wire is dropped from the *geometric* checks
                 (its own E-SCHEMA finding already says why) but its declared id
                 still counts as "known" for wire-reference checks.
  E-BOX-HIT      a wire segment passes through the interior of a box that is not
                 one of the wire's two endpoints.  Every box is inflated by
                 2 px for the test.  Ignored portions of the polyline:
                   * all boxes: first and last 6 px of arclength;
                   * the ``from`` box: also any part within 6 px (Euclidean) of
                     the attachment point (the first polyline point);
                   * the ``to`` box: also any part within 6 px of the last point.
                 A hit is reported only if the remaining incursion is longer than
                 0.5 px; one finding per (wire, box) pair, reporting the deepest
                 incursion.  "Interior" means positive-length overlap with the
                 *open* inflated rectangle, so a wire lying exactly on the
                 inflated rectangle's edge is *not* a hit, while a wire running
                 along the box's own edge (i.e. inside the 2 px clearance band)
                 is.
  E-LABEL-BOX    a wire label's box overlaps a box rectangle.  TOLERANCE: the
                 overlap must exceed 4 px in BOTH axes to be reported (smaller
                 overlaps are treated as touching, absorbing font-metric error).
  E-LABEL-LABEL  two wire label boxes overlap; same rule with a 2 px tolerance.
  E-ATTACH       the first point is not on the boundary of the ``from`` box
                 (within 3 px) or the last point is not on the boundary of the
                 ``to`` box (within 3 px).  "Boundary" = on an edge of the
                 rectangle: inside, the distance to the nearest edge; outside,
                 the distance to the nearest point of the rectangle.
  E-BOX-OVERLAP  two boxes overlap with strictly positive area (> 1e-6 px in
                 both axes).  Sharing an edge or a corner is not an overlap.
  E-ZONE-OVERLAP two zones overlap, same rule.
  E-MARGIN       a box or zone extends outside the canvas or comes within 20 px
                 of a canvas edge (safe area = [20, w-20] x [20, h-20]).
  W-CROSS        (counted) number of *proper* intersections between segments of
                 different wires: transversal crossings whose intersection point
                 is strictly interior to both segments (parameter in (1e-9,
                 1-1e-9)).  Endpoint touches / T-junctions are not proper
                 crossings; collinear overlaps are reported by W-COLLINEAR.
                 Reports the total plus the 5 worst wire pairs (with points).
  W-COLLINEAR    (counted) number of distinct wire *pairs* sharing an exactly
                 collinear, overlapping segment: both segments axis-aligned
                 (deviation <= 0.6 px), same axis, lateral offset <= 0.6 px,
                 overlap length > 0.6 px.  Non-axis-aligned segments are not
                 considered (the spec says "same axis").
  W-WHITESPACE   content bbox = union of all boxes + zones (clipped to the
                 canvas).  Reports the fraction of the canvas that is empty
                 outside that bbox, and the largest empty axis-aligned rectangle
                 inside it.  The rectangle is found exactly by an edge sweep over
                 candidate coordinates (a maximal empty rectangle is always
                 supported by obstacle edges / the bbox): for every pair of
                 candidate x coordinates, all obstacles overlapping that strip
                 block their y ranges, and the widest free y gap gives the best
                 rectangle for the strip.  Above 80 obstacles an O(cells) coarse
                 20 px grid + histogram search is used instead and flagged as
                 approximate (``"approx": true``).
  W-BALANCE      distinct box width / height counts (values rounded to 0.1 px),
                 plus per-column and per-row clustering: boxes are bucketed by
                 x-centre (new column when the centre is more than 24 px from the
                 running cluster mean) and by y-centre (same rule), reporting
                 distinct widths/heights per cluster and whether the cluster
                 shares a common left edge (columns) / top edge (rows) within
                 4 px.
  E-GLOBAL-MISSING
                 (--fidelity only) a box's ``globals`` list differs from
                 ``GLOBALS.get(id, [])``; lists are compared order-insensitively.
                 One finding per offending box, listing missing/extra nets.
  E-FIDELITY     (--fidelity only) the (from,to,net) triples implied by the
                 layout's wires (each wire expanded over its ``nets``) differ
                 from the authoritative link list; or the set of
                 ``kind=="entity"`` box ids differs from ``set(ENTITIES)``; or
                 the set of ``kind=="ext"`` box ids differs from
                 ``set(EXTERNAL)``.  One finding per mismatching category,
                 listing the exact missing/extra items.  The authoritative link
                 list is taken from ``LINKS`` (the contract), else from
                 ``wire_triples()``, else from ``WIRE_GROUPS`` expanded here;
                 ``fidelity.link_source`` in --json records which was used.
  W-ZONE-CONTAIN (extra, inferred) a box whose *centre* lies inside a zone is not
                 fully contained in that zone (1 px tolerance).  The schema has
                 no zone-membership field, so membership is inferred from the
                 centre; this is reported as a warning because the spec says
                 zones "should contain their member boxes".
  I-STATS        (info) canvas, box counts by kind, wire count, total and
                 longest wire length, wire-label count, content bbox, and the
                 empty-margin percentage on all four sides (content bbox edge
                 distance to the canvas edge, as a percentage of canvas w/h).

SCORING (lower is better; printed as the final ``SCORE`` line)
    score = 100*errors + 10*crossings + 5*collinear_pairs
            + 200*empty_fraction + 1*longest_wire/100
    errors            = number of ERROR-level findings (including fidelity ones)
    crossings         = W-CROSS total
    collinear_pairs   = W-COLLINEAR total
    empty_fraction    = W-WHITESPACE fraction (0..1)
    longest_wire      = length of the longest wire polyline, in px

LIMITATIONS / KNOWN DEVIATIONS (stated honestly)
    * The label box is estimated, never measured: the 0.62/1.0 char widths and
      the fixed 22 px height are heuristics, so label findings are approximate.
    * Only axis-aligned collinear overlaps are counted (W-COLLINEAR).
    * Wire/zone ``width_px`` and stroke widths are validated but ignored
      geometrically (a stroke has no width in this model).
    * Zone membership is inferred (see W-ZONE-CONTAIN); zones are never treated
      as obstacles for wires, as specified.
    * ``arch_data.py`` is imported lazily from the auditor's own directory.  If
      it is missing, unimportable, or lacks ENTITIES/EXTERNAL/GLOBALS, fidelity
      is skipped with a clear message on stderr (and ``fidelity.message`` in
      --json); a missing link source is never a silent pass.  When the module
      exists but exposes ``wire_triples()``/``WIRE_GROUPS`` instead of the
      contracted ``LINKS``, those documented fallbacks are used and
      ``fidelity.link_source`` says so.
    * ``E-SCHEMA`` is deliberately strict about the fields listed under REQUIRED
      FIELDS above, because the sidecar is a contract between the generator and
      this auditor.

Pure Python 3 standard library only.  No network, no third-party imports.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from importlib import util as _importlib_util

# Windows consoles default to a legacy code page; be explicit and lossless.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# --------------------------------------------------------------------------- #
# Tolerances and constants (each one is documented in the module docstring)
# --------------------------------------------------------------------------- #
EPS = 1e-6                 # generic "strictly positive area" epsilon, in px
BOX_INFLATE_PX = 2.0       # E-BOX-HIT: clearance band around every box
END_TRIM_PX = 6.0          # E-BOX-HIT: ignored arclength at both polyline ends
ATTACH_RADIUS_PX = 6.0     # E-BOX-HIT: ignored radius around an endpoint box
MIN_INTRUSION_PX = 0.5     # E-BOX-HIT: minimum reported incursion depth
ATTACH_TOL_PX = 3.0        # E-ATTACH
LABEL_BOX_TOL_PX = 4.0     # E-LABEL-BOX
LABEL_LABEL_TOL_PX = 2.0   # E-LABEL-LABEL
MARGIN_PX = 20.0           # E-MARGIN
COLLINEAR_TOL_PX = 0.6     # W-COLLINEAR lateral offset / axis deviation
COLLINEAR_MIN_OVERLAP_PX = 0.6   # W-COLLINEAR minimum shared length
PARAM_EPS = 1e-9           # W-CROSS: endpoint exclusion in segment parameters
COLUMN_TOL_PX = 24.0       # W-BALANCE: x-centre clustering radius
ALIGN_TOL_PX = 4.0         # W-BALANCE: shared left/top edge tolerance
SIZE_ROUND_DP = 1          # W-BALANCE: width/height distinctness rounding
ZONE_CONTAIN_TOL_PX = 1.0  # W-ZONE-CONTAIN
LABEL_DEFAULT_SIZE = 13.5  # label.size fallback
LABEL_PAD_X = 12.0         # label box horizontal padding
LABEL_BOX_H = 22.0         # label box total height
ASCII_CHAR_FACTOR = 0.62   # label box: ASCII advance per unit font size
CJK_CHAR_FACTOR = 1.00     # label box: CJK / full-width advance per unit size
CJK_ORD_THRESHOLD = 0x2E7F # ord(c) > this  =>  CJK / full-width
GRID_FALLBACK_STEP = 20.0  # W-WHITESPACE coarse grid when obstacles are many
GRID_FALLBACK_MAX_OBS = 80 # above this many obstacles use the coarse grid
HUMAN_MAX_PER_CODE = 40    # human table: findings printed per code before "..."
WORST_PAIRS = 5            # W-CROSS: worst wire pairs reported
MAX_COLLINEAR_DETAIL = 10  # W-COLLINEAR: pairs listed in the human table
MAX_BALANCE_DETAIL = 16    # W-BALANCE: columns/rows listed in the human table

# Fixed presentation order, also the order codes are documented in.
CODE_ORDER = [
    "E-SCHEMA", "E-BOX-HIT", "E-LABEL-BOX", "E-LABEL-LABEL", "E-ATTACH",
    "E-BOX-OVERLAP", "E-ZONE-OVERLAP", "E-MARGIN", "W-CROSS", "W-COLLINEAR",
    "W-WHITESPACE", "W-BALANCE", "E-GLOBAL-MISSING", "E-FIDELITY",
    "W-ZONE-CONTAIN", "I-STATS",
]
CODE_LEVEL = {
    "E-SCHEMA": "error", "E-BOX-HIT": "error", "E-LABEL-BOX": "error",
    "E-LABEL-LABEL": "error", "E-ATTACH": "error", "E-BOX-OVERLAP": "error",
    "E-ZONE-OVERLAP": "error", "E-MARGIN": "error", "E-GLOBAL-MISSING": "error",
    "E-FIDELITY": "error", "W-CROSS": "warning", "W-COLLINEAR": "warning",
    "W-WHITESPACE": "warning", "W-BALANCE": "warning",
    "W-ZONE-CONTAIN": "warning", "I-STATS": "info",
}


# --------------------------------------------------------------------------- #
# tiny geometry helpers
# --------------------------------------------------------------------------- #
def is_num(v):
    """True for a real, finite number (bools are rejected: they are ints)."""
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(float(v)))


def fmt(v):
    """Compact deterministic number formatting for reports."""
    if v is None:
        return "-"
    s = "{:.2f}".format(float(v))
    if s.endswith("0"):
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def point_str(p):
    return "({},{})".format(fmt(p[0]), fmt(p[1]))


class Rect(object):
    """Axis-aligned rectangle stored as edges (x0 <= x1, y0 <= y1 when built
    from x/y/w/h with w,h > 0)."""

    __slots__ = ("x0", "y0", "x1", "y1")

    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = (
            float(x0), float(y0), float(x1), float(y1))

    @classmethod
    def from_xywh(cls, x, y, w, h):
        return cls(x, y, float(x) + float(w), float(y) + float(h))

    @property
    def w(self):
        return self.x1 - self.x0

    @property
    def h(self):
        return self.y1 - self.y0

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self):
        return (self.y0 + self.y1) / 2.0

    def inflated(self, d):
        return Rect(self.x0 - d, self.y0 - d, self.x1 + d, self.y1 + d)

    def contains_point(self, p):
        return self.x0 <= p[0] <= self.x1 and self.y0 <= p[1] <= self.y1

    def as_dict(self):
        return {"x": self.x0, "y": self.y0, "w": self.w, "h": self.h}

    def __repr__(self):  # pragma: no cover - debugging aid
        return "Rect({},{},{},{})".format(self.x0, self.y0, self.x1, self.y1)


def union_rect(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return Rect(min(a.x0, b.x0), min(a.y0, b.y0), max(a.x1, b.x1), max(a.y1, b.y1))


def intersect_rect(a, b):
    return Rect(max(a.x0, b.x0), max(a.y0, b.y0), min(a.x1, b.x1), min(a.y1, b.y1))


def rects_overlap(a, b, tol=EPS):
    """Strictly positive-area overlap (> tol on both axes)."""
    iw = min(a.x1, b.x1) - max(a.x0, b.x0)
    ih = min(a.y1, b.y1) - max(a.y0, b.y0)
    return iw > tol and ih > tol


def point_boundary_distance(p, r):
    """Distance from p to the *boundary* of rectangle r, plus the nearest side."""
    x, y = p
    if r.x0 <= x <= r.x1 and r.y0 <= y <= r.y1:
        cands = [(x - r.x0, "left"), (r.x1 - x, "right"),
                 (y - r.y0, "top"), (r.y1 - y, "bottom")]
        d, side = min(cands, key=lambda t: t[0])
        return d, side
    cx = min(max(x, r.x0), r.x1)
    cy = min(max(y, r.y0), r.y1)
    d = math.hypot(x - cx, y - cy)
    # name the side the clamped point sits on (corner -> dominant axis)
    dxl, dxr = abs(cx - r.x0), abs(r.x1 - cx)
    dyt, dyb = abs(cy - r.y0), abs(r.y1 - cy)
    if min(dxl, dxr) <= min(dyt, dyb):
        side = "left" if dxl <= dxr else "right"
    else:
        side = "top" if dyt <= dyb else "bottom"
    return d, side


def seg_rect_clip(p0, p1, r):
    """Liang-Barsky clip of segment p0->p1 against closed rect r.

    Returns (t0, t1) with 0 <= t0 < t1 <= 1, or None when there is no overlap.
    """
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, p0[0] - r.x0), (dx, r.x1 - p0[0]),
                 (-dy, p0[1] - r.y0), (dy, r.y1 - p0[1])):
        if abs(p) < 1e-15:
            if q < 0:
                return None
        else:
            t = q / p
            if p < 0:
                if t > t1:
                    return None
                if t > t0:
                    t0 = t
            else:
                if t < t0:
                    return None
                if t < t1:
                    t1 = t
    if t1 - t0 <= 0.0:
        return None
    return (t0, t1)


def seg_enters_interior(p0, p1, r, eps=EPS):
    """True when the segment overlaps the *open* rectangle for a positive length."""
    clip = seg_rect_clip(p0, p1, r)
    if clip is None:
        return None
    t0, t1 = clip
    tm = (t0 + t1) / 2.0
    mx = p0[0] + (p1[0] - p0[0]) * tm
    my = p0[1] + (p1[1] - p0[1]) * tm
    if (mx > r.x0 + eps and mx < r.x1 - eps
            and my > r.y0 + eps and my < r.y1 - eps):
        return (t0, t1)
    return None


def seg_within_radius(p0, p1, c, radius):
    """Parameter interval of the segment whose points lie within `radius` of c."""
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    a = dx * dx + dy * dy
    if a <= 1e-18:
        return (0.0, 1.0) if dist(p0, c) <= radius else None
    fx = p0[0] - c[0]
    fy = p0[1] - c[1]
    b = 2.0 * (fx * dx + fy * dy)
    cc = fx * fx + fy * fy - radius * radius
    disc = b * b - 4.0 * a * cc
    if disc < 0.0:
        return None
    sq = math.sqrt(disc)
    t1 = (-b - sq) / (2.0 * a)
    t2 = (-b + sq) / (2.0 * a)
    lo = max(0.0, t1)
    hi = min(1.0, t2)
    if hi <= lo:
        return None
    return (lo, hi)


def merge_intervals(intervals):
    """Merge (a, b) intervals (a < b); returns a sorted list of tuples."""
    clean = sorted((float(a), float(b)) for a, b in intervals if b > a)
    out = []
    for a, b in clean:
        if out and a <= out[-1][1]:
            if b > out[-1][1]:
                out[-1][1] = b
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def subtract_intervals(base, cuts):
    """base: (a, b); cuts: merged interval list -> list of remaining intervals."""
    lo, hi = base
    if hi <= lo:
        return []
    res = []
    cur = lo
    for a, b in cuts:
        if b <= cur:
            continue
        if a >= hi:
            break
        if a > cur:
            res.append((cur, min(a, hi)))
        cur = max(cur, b)
        if cur >= hi:
            break
    if cur < hi:
        res.append((cur, hi))
    return [(a, b) for a, b in res if b > a]


def seg_proper_intersection(p0, p1, q0, q1):
    """Proper (transversal, interior-to-both) intersection point, else None."""
    rx, ry = p1[0] - p0[0], p1[1] - p0[1]
    sx, sy = q1[0] - q0[0], q1[1] - q0[1]
    denom = rx * sy - ry * sx
    if abs(denom) < 1e-12:
        return None  # parallel or collinear: not a proper crossing
    qpx, qpy = q0[0] - p0[0], q0[1] - p0[1]
    t = (qpx * sy - qpy * sx) / denom
    u = (qpx * ry - qpy * rx) / denom
    if t <= PARAM_EPS or t >= 1.0 - PARAM_EPS:
        return None
    if u <= PARAM_EPS or u >= 1.0 - PARAM_EPS:
        return None
    return (p0[0] + t * rx, p0[1] + t * ry)


def text_width(text, size):
    """Label width heuristic: 0.62*size per ASCII char, 1.0*size per CJK char,
    plus 12 px of horizontal padding (see module docstring)."""
    total = 0.0
    for ch in text:
        total += (CJK_CHAR_FACTOR if ord(ch) > CJK_ORD_THRESHOLD
                  else ASCII_CHAR_FACTOR) * size
    return total + LABEL_PAD_X


def label_lines(label):
    """The text lines actually drawn for a label.

    ``label["lines"]`` (optional, list of strings) wins when present; otherwise the
    label is a single line of ``label["text"]``.  ``text`` is always required and is
    what the human report prints.
    """
    lines = label.get("lines")
    return list(lines) if lines else [label["text"]]


def label_rect(label):
    """Estimated bounding box of a wire label (see module docstring).

    Multi-line labels (``lines``) use the width of the WIDEST line and a total
    height of ``LABEL_BOX_H * len(lines)``; a single-line label is unchanged
    (``LABEL_BOX_H`` tall).
    """
    size = label["size"]
    lines = label_lines(label)
    w = max(text_width(t, size) for t in lines)
    anchor = label["anchor"]
    if anchor == "start":
        x0 = label["x"]
    elif anchor == "end":
        x0 = label["x"] - w
    else:
        x0 = label["x"] - w / 2.0
    h = LABEL_BOX_H * len(lines)
    y = label["y"]
    return Rect(x0, y - h / 2.0, x0 + w, y + h / 2.0)


def polyline_length(pts):
    return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def _round_key(v, dp=SIZE_ROUND_DP):
    return round(float(v), dp)


# --------------------------------------------------------------------------- #
# largest empty rectangle (W-WHITESPACE)
# --------------------------------------------------------------------------- #
def _clip_obstacles(obstacles, bbox):
    out = []
    for r in obstacles:
        x0 = max(r.x0, bbox.x0)
        x1 = min(r.x1, bbox.x1)
        y0 = max(r.y0, bbox.y0)
        y1 = min(r.y1, bbox.y1)
        if x1 - x0 > EPS and y1 - y0 > EPS:
            out.append((x0, y0, x1, y1))
    return out


def largest_empty_rect_exact(obstacles, bbox):
    """Exact maximal empty axis-aligned rectangle inside `bbox`.

    Candidate x/y coordinates are the bbox edges plus every obstacle edge; a
    maximal empty rectangle is always supported by those.  For each x-strip we
    collect the obstacles that overlap it and take the widest free y gap.
    """
    obs = _clip_obstacles(obstacles, bbox)
    xs = {bbox.x0, bbox.x1}
    ys = {bbox.y0, bbox.y1}
    for x0, y0, x1, y1 in obs:
        xs.add(x0)
        xs.add(x1)
        ys.add(y0)
        ys.add(y1)
    xs = sorted(xs)
    ys = sorted(ys)
    best = None  # (area, x0, y0, x1, y1)
    for i in range(len(xs) - 1):
        x0 = xs[i]
        for j in range(i + 1, len(xs)):
            x1 = xs[j]
            w = x1 - x0
            if w <= EPS:
                continue
            blocked = []
            for ox0, oy0, ox1, oy1 in obs:
                if ox0 < x1 - EPS and ox1 > x0 + EPS:
                    blocked.append((oy0, oy1))
            if not blocked:
                free = [(bbox.y0, bbox.y1)]
            else:
                free = subtract_intervals((bbox.y0, bbox.y1), merge_intervals(blocked))
            for a, b in free:
                h = b - a
                if h <= EPS:
                    continue
                area = w * h
                if best is None or area > best[0] + 1e-9:
                    best = (area, x0, a, x1, b)
    if best is None:
        return None
    return {"x": best[1], "y": best[2], "w": best[3] - best[1], "h": best[4] - best[2],
            "area": best[0], "approx": False}


def _largest_rect_in_matrix(grid, nx, ny):
    """Largest all-free rectangle in a boolean blocked matrix (histogram sweep).
    Returns (area_cells, ix0, iy0, ix1, iy1) with iy1/ix1 exclusive."""
    best = (0, 0, 0, 0, 0)
    heights = [0] * nx
    for iy in range(ny):
        row = grid[iy]
        for ix in range(nx):
            heights[ix] = 0 if row[ix] else heights[ix] + 1
        stack = []
        for ix in range(nx + 1):
            h = heights[ix] if ix < nx else 0
            start = ix
            while stack and stack[-1][1] >= h:
                sx, sh = stack.pop()
                area = sh * (ix - sx)
                if area > best[0]:
                    best = (area, sx, iy - sh + 1, ix, iy + 1)
                start = sx
            stack.append((start, h))
    return best


def largest_empty_rect_grid(obstacles, bbox, step=GRID_FALLBACK_STEP):
    """Coarse 20 px grid fallback: cell is blocked when an obstacle interior
    overlaps the cell interior; largest free rectangle via histogram sweep."""
    obs = _clip_obstacles(obstacles, bbox)
    nx = max(1, int(math.ceil(bbox.w / step)))
    ny = max(1, int(math.ceil(bbox.h / step)))
    grid = [[False] * nx for _ in range(ny)]
    for x0, y0, x1, y1 in obs:
        ix0 = max(0, int(math.floor((x0 - bbox.x0) / step)))
        ix1 = min(nx - 1, int(math.ceil((x1 - bbox.x0) / step)) - 1)
        iy0 = max(0, int(math.floor((y0 - bbox.y0) / step)))
        iy1 = min(ny - 1, int(math.ceil((y1 - bbox.y0) / step)) - 1)
        for iy in range(iy0, iy1 + 1):
            cy0 = bbox.y0 + iy * step
            cy1 = min(cy0 + step, bbox.y1)
            if not (y0 < cy1 - EPS and y1 > cy0 + EPS):
                continue
            row = grid[iy]
            for ix in range(ix0, ix1 + 1):
                cx0 = bbox.x0 + ix * step
                cx1 = min(cx0 + step, bbox.x1)
                if x0 < cx1 - EPS and x1 > cx0 + EPS:
                    row[ix] = True
    area_cells, ix0, iy0, ix1, iy1 = _largest_rect_in_matrix(grid, nx, ny)
    if area_cells <= 0:
        return None
    x0 = bbox.x0 + ix0 * step
    y0 = bbox.y0 + iy0 * step
    x1 = min(bbox.x0 + ix1 * step, bbox.x1)
    y1 = min(bbox.y0 + iy1 * step, bbox.y1)
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0,
            "area": (x1 - x0) * (y1 - y0), "approx": True,
            "grid_step": step, "grid_cells": [nx, ny]}


def largest_empty_rect(obstacles, bbox):
    obs = _clip_obstacles(obstacles, bbox)
    if len(obs) > GRID_FALLBACK_MAX_OBS:
        return largest_empty_rect_grid(obstacles, bbox)
    return largest_empty_rect_exact(obstacles, bbox)


# --------------------------------------------------------------------------- #
# fidelity module loading
# --------------------------------------------------------------------------- #
def _resolve_links(mod):
    """Authoritative (from, to, net) triples from an arch_data module.

    Contract first, then two documented compatibility fallbacks, because the
    repo's arch_data.py currently exposes ``WIRE_GROUPS`` / ``wire_triples()``
    rather than a materialised ``LINKS`` list:
        1. ``LINKS``           -- list of (from, to, net) tuples (the contract)
        2. ``wire_triples()``  -- callable returning that list
        3. ``WIRE_GROUPS``     -- list of (from, to, [nets]) expanded here
    Returns (triples, source_name) or (None, None) when none is available.
    """
    if hasattr(mod, "LINKS"):
        return list(mod.LINKS or []), "LINKS"
    fn = getattr(mod, "wire_triples", None)
    if callable(fn):
        return list(fn() or []), "wire_triples()"
    groups = getattr(mod, "WIRE_GROUPS", None)
    if groups:
        out = []
        for entry in groups:
            try:
                frm, to, nets = entry
            except Exception:  # noqa: BLE001
                continue
            for n in (nets or []):
                out.append((frm, to, n))
        return out, "WIRE_GROUPS"
    return None, None


def load_arch_data(script_dir):
    """Lazily import arch_data.py from `script_dir`.

    Returns (module, links, source, message):
      * module is not None on success, with `links` the authoritative triple
        list and `source` naming where it came from;
      * module is None when the file is absent / unimportable / lacks the
        required names, and `message` is the clear skip message.
    """
    path = os.path.join(script_dir, "arch_data.py")
    if not os.path.isfile(path):
        return None, None, None, ("fidelity skipped: scripts/arch_data.py not "
                                  "found at " + path)
    try:
        spec = _importlib_util.spec_from_file_location("arch_data", path)
        if spec is None or spec.loader is None:
            return None, None, None, ("fidelity skipped: cannot build an import "
                                      "spec for " + path)
        mod = _importlib_util.module_from_spec(spec)
        sys.modules.setdefault("arch_data", mod)
        spec.loader.exec_module(mod)
    except ImportError as exc:
        return None, None, None, ("fidelity skipped: import arch_data failed: {}"
                                  .format(exc))
    except Exception as exc:  # noqa: BLE001 - defensive: never crash the audit
        return None, None, None, ("fidelity skipped: arch_data failed to load: "
                                  "{}: {}".format(type(exc).__name__, exc))
    missing = [n for n in ("ENTITIES", "EXTERNAL", "GLOBALS")
               if not hasattr(mod, n)]
    if missing:
        return None, None, None, ("fidelity skipped: arch_data.py lacks {}"
                                  .format(", ".join(missing)))
    try:
        links, source = _resolve_links(mod)
    except Exception as exc:  # noqa: BLE001
        return None, None, None, ("fidelity skipped: arch_data link source "
                                  "failed: {}: {}".format(type(exc).__name__, exc))
    if links is None:
        return None, None, None, ("fidelity skipped: arch_data.py exposes none "
                                  "of LINKS, wire_triples(), WIRE_GROUPS")
    return mod, links, source, None


# --------------------------------------------------------------------------- #
# the auditor
# --------------------------------------------------------------------------- #
class Auditor(object):
    def __init__(self, doc, path, fidelity=False, script_dir=None):
        self.doc = doc
        self.path = path
        self.want_fidelity = fidelity
        self.script_dir = script_dir or os.path.dirname(os.path.abspath(__file__))
        self.findings = []
        self.layout_id = None
        self.canvas = None
        self.boxes = []          # {"id","kind","title","rect","globals"}
        self.zones = []          # {"id","title","rect"}
        self.wires = []          # {"id","from","to","pts","nets","label","rect"}
        self.boxes_by_id = {}
        self.declared_box_ids = set()
        self.fidelity = {"requested": bool(fidelity), "available": False,
                         "message": None}
        self.crossings_total = 0
        self.crossing_pairs = []
        self.collinear_pairs = []
        self.whitespace = {}
        self.balance = {}
        self.stats = {}

    # ---------------------------------------------------------------- helpers
    def add(self, code, message, **data):
        f = {"code": code, "level": CODE_LEVEL.get(code, "warning"),
             "message": message}
        if data:
            f["data"] = data
        self.findings.append(f)
        return f

    def errors(self):
        return [f for f in self.findings if f["level"] == "error"]

    # ------------------------------------------------------------- validation
    def validate(self):
        doc = self.doc
        if not isinstance(doc, dict):
            self.add("E-SCHEMA",
                     "layout root is {}, expected a JSON object".format(
                         type(doc).__name__), field="$")
            return
        lid = doc.get("id")
        if not isinstance(lid, str) or not lid:
            self.add("E-SCHEMA",
                     "missing/invalid required field 'id' "
                     "(expected a non-empty string)", field="id")
        else:
            self.layout_id = lid

        cv = doc.get("canvas")
        if not isinstance(cv, dict):
            self.add("E-SCHEMA",
                     "missing/invalid required field 'canvas' "
                     "(expected an object with numeric w,h)", field="canvas")
        else:
            bad = []
            if not is_num(cv.get("w")) or float(cv["w"]) <= 0:
                bad.append("w")
            if not is_num(cv.get("h")) or float(cv["h"]) <= 0:
                bad.append("h")
            if bad:
                self.add("E-SCHEMA",
                         "canvas has missing/invalid/zero-or-negative {} "
                         "(got w={!r}, h={!r})".format(
                             "/".join(bad), cv.get("w"), cv.get("h")),
                         field="canvas")
            else:
                self.canvas = Rect(0.0, 0.0, float(cv["w"]), float(cv["h"]))

        self._validate_boxes(doc.get("boxes"))
        self._validate_zones(doc.get("zones"))
        self._validate_wires(doc.get("wires"))

    def _validate_boxes(self, raw):
        if raw is None:
            self.add("E-SCHEMA",
                     "missing required field 'boxes' (expected a list; "
                     "use [] for none)", field="boxes")
            return
        if not isinstance(raw, list):
            self.add("E-SCHEMA", "'boxes' must be a list, got {}".format(
                type(raw).__name__), field="boxes")
            return
        seen = {}
        for i, b in enumerate(raw):
            where = "boxes[{}]".format(i)
            if not isinstance(b, dict):
                self.add("E-SCHEMA", "{} is not an object".format(where),
                         where=where)
                continue
            bid = b.get("id")
            label = repr(bid) if isinstance(bid, str) and bid else where
            if not isinstance(bid, str) or not bid:
                self.add("E-SCHEMA",
                         "{}: missing/invalid required field 'id'".format(where),
                         where=where)
                bid = None
            elif bid in seen:
                self.add("E-SCHEMA",
                         "duplicate box id {!r} (first declared at boxes[{}])"
                         .format(bid, seen[bid]), id=bid, where=where)
            else:
                seen[bid] = i
                self.declared_box_ids.add(bid)

            kind = b.get("kind")
            if kind not in ("entity", "ext", "glue"):
                self.add("E-SCHEMA",
                         "box {}: 'kind' must be one of entity|ext|glue, "
                         "got {!r}".format(label, kind),
                         where=where, id=bid, kind=kind)
            title = b.get("title")
            if not isinstance(title, str):
                self.add("E-SCHEMA",
                         "box {}: missing/invalid required field 'title' "
                         "(expected a string, got {})".format(
                             label, type(title).__name__),
                         where=where, id=bid)
            if b.get("sub") is not None and not isinstance(b["sub"], str):
                self.add("E-SCHEMA",
                         "box {}: 'sub' must be a string when present, got {}"
                         .format(label, type(b["sub"]).__name__),
                         where=where, id=bid)
            for size_key in ("title_size", "sub_size"):
                sv = b.get(size_key)
                if sv is not None and (not is_num(sv) or float(sv) <= 0):
                    self.add("E-SCHEMA",
                             "box {}: '{}' must be a positive number when "
                             "present, got {!r}".format(label, size_key, sv),
                             where=where, id=bid, field=size_key)
            globals_list = b.get("globals")
            if globals_list is not None:
                if not isinstance(globals_list, list) or not all(
                        isinstance(g, str) for g in globals_list):
                    self.add("E-SCHEMA",
                             "box {}: 'globals' must be a list of strings when "
                             "present, got {!r}".format(label, globals_list),
                             where=where, id=bid, field="globals")
                    globals_list = None

            bad_fields = []
            for key in ("x", "y", "w", "h"):
                v = b.get(key)
                if not is_num(v):
                    bad_fields.append("{}={!r}".format(key, v))
                elif key in ("w", "h") and float(v) <= 0:
                    bad_fields.append("{}={!r} (must be > 0)".format(key, v))
            if bad_fields:
                self.add("E-SCHEMA",
                         "box {}: non-numeric or non-positive geometry: {}"
                         .format(label, ", ".join(bad_fields)),
                         where=where, id=bid)
                continue

            rect = Rect.from_xywh(b["x"], b["y"], b["w"], b["h"])
            rec = {"id": bid if bid is not None else where,
                   "kind": kind, "title": title if isinstance(title, str) else "",
                   "rect": rect,
                   "globals": list(globals_list) if globals_list else []}
            self.boxes.append(rec)
            if bid is not None:
                self.boxes_by_id[bid] = rec

    def _validate_zones(self, raw):
        if raw is None:
            return  # zones are optional
        if not isinstance(raw, list):
            self.add("E-SCHEMA", "'zones' must be a list when present, got {}"
                     .format(type(raw).__name__), field="zones")
            return
        seen = {}
        for i, z in enumerate(raw):
            where = "zones[{}]".format(i)
            if not isinstance(z, dict):
                self.add("E-SCHEMA", "{} is not an object".format(where),
                         where=where)
                continue
            zid = z.get("id")
            label = repr(zid) if isinstance(zid, str) and zid else where
            if not isinstance(zid, str) or not zid:
                self.add("E-SCHEMA",
                         "{}: missing/invalid required field 'id'".format(where),
                         where=where)
                zid = None
            elif zid in seen:
                self.add("E-SCHEMA",
                         "duplicate zone id {!r} (first declared at zones[{}])"
                         .format(zid, seen[zid]), id=zid, where=where)
            else:
                seen[zid] = i
            if z.get("title") is not None and not isinstance(z["title"], str):
                self.add("E-SCHEMA",
                         "zone {}: 'title' must be a string when present"
                         .format(label), where=where, id=zid)
            bad_fields = []
            for key in ("x", "y", "w", "h"):
                v = z.get(key)
                if not is_num(v):
                    bad_fields.append("{}={!r}".format(key, v))
                elif key in ("w", "h") and float(v) <= 0:
                    bad_fields.append("{}={!r} (must be > 0)".format(key, v))
            if bad_fields:
                self.add("E-SCHEMA",
                         "zone {}: non-numeric or non-positive geometry: {}"
                         .format(label, ", ".join(bad_fields)),
                         where=where, id=zid)
                continue
            self.zones.append({
                "id": zid if zid is not None else where,
                "title": z["title"] if isinstance(z.get("title"), str) else "",
                "rect": Rect.from_xywh(z["x"], z["y"], z["w"], z["h"])})

    def _validate_wires(self, raw):
        if raw is None:
            self.add("E-SCHEMA",
                     "missing required field 'wires' (expected a list; "
                     "use [] for none)", field="wires")
            return
        if not isinstance(raw, list):
            self.add("E-SCHEMA", "'wires' must be a list, got {}".format(
                type(raw).__name__), field="wires")
            return
        seen = {}
        for i, w in enumerate(raw):
            where = "wires[{}]".format(i)
            if not isinstance(w, dict):
                self.add("E-SCHEMA", "{} is not an object".format(where),
                         where=where)
                continue
            wid = w.get("id")
            label = repr(wid) if isinstance(wid, str) and wid else where
            if not isinstance(wid, str) or not wid:
                self.add("E-SCHEMA",
                         "{}: missing/invalid required field 'id'".format(where),
                         where=where)
                wid = None
            elif wid in seen:
                self.add("E-SCHEMA",
                         "duplicate wire id {!r} (first declared at wires[{}])"
                         .format(wid, seen[wid]), id=wid, where=where)
            else:
                seen[wid] = i
            wire_key = wid if wid is not None else where

            frm = w.get("from")
            to = w.get("to")
            for key, v in (("from", frm), ("to", to)):
                if not isinstance(v, str) or not v:
                    self.add("E-SCHEMA",
                             "wire {}: missing/invalid required field '{}' "
                             "(expected a box id)".format(label, key),
                             where=where, id=wid, field=key)
                elif v not in self.declared_box_ids:
                    self.add("E-SCHEMA",
                             "wire {}: '{}' references unknown box id {!r} "
                             "(known ids: {})".format(
                                 label, key, v,
                                 ", ".join(sorted(self.declared_box_ids)) or "none"),
                             where=where, id=wid, field=key, ref=v)
            for key in ("from_side", "to_side"):
                v = w.get(key)
                if v is not None and v not in ("left", "right", "top", "bottom"):
                    self.add("E-SCHEMA",
                             "wire {}: '{}' must be left|right|top|bottom when "
                             "present, got {!r}".format(label, key, v),
                             where=where, id=wid, field=key)

            nets = w.get("nets")
            if nets is not None:
                if not isinstance(nets, list) or not all(
                        isinstance(n, str) for n in nets):
                    self.add("E-SCHEMA",
                             "wire {}: 'nets' must be a list of strings when "
                             "present, got {!r}".format(label, nets),
                             where=where, id=wid, field="nets")
                    nets = None
            width_px = w.get("width_px")
            if width_px is not None and (not is_num(width_px)
                                         or float(width_px) <= 0):
                self.add("E-SCHEMA",
                         "wire {}: 'width_px' must be a positive number when "
                         "present, got {!r}".format(label, width_px),
                         where=where, id=wid, field="width_px")

            pts_raw = w.get("pts")
            pts = None
            if not isinstance(pts_raw, list):
                self.add("E-SCHEMA",
                         "wire {}: missing/invalid required field 'pts' "
                         "(expected a list of [x,y] points)".format(label),
                         where=where, id=wid, field="pts")
            elif len(pts_raw) < 2:
                self.add("E-SCHEMA",
                         "wire {}: 'pts' has {} point(s), at least 2 are "
                         "required".format(label, len(pts_raw)),
                         where=where, id=wid, field="pts", points=len(pts_raw))
            else:
                good = []
                bad = []
                for k, pt in enumerate(pts_raw):
                    if (isinstance(pt, (list, tuple)) and len(pt) == 2
                            and is_num(pt[0]) and is_num(pt[1])):
                        good.append((float(pt[0]), float(pt[1])))
                    else:
                        bad.append("pts[{}]={!r}".format(k, pt))
                if bad:
                    self.add("E-SCHEMA",
                             "wire {}: malformed point(s): {}".format(
                                 label, ", ".join(bad[:6])
                                 + (" (+{} more)".format(len(bad) - 6)
                                    if len(bad) > 6 else "")),
                             where=where, id=wid, field="pts")
                elif len(good) >= 2:
                    pts = good

            lbl = w.get("label")
            label_rec = None
            if lbl is not None:
                if not isinstance(lbl, dict):
                    self.add("E-SCHEMA",
                             "wire {}: 'label' must be an object when present"
                             .format(label), where=where, id=wid, field="label")
                else:
                    bad = []
                    if not isinstance(lbl.get("text"), str) or not lbl.get("text"):
                        bad.append("text")
                    for key in ("x", "y"):
                        if not is_num(lbl.get(key)):
                            bad.append("{}={!r}".format(key, lbl.get(key)))
                    anchor = lbl.get("anchor", "middle")
                    if anchor not in ("start", "middle", "end"):
                        bad.append("anchor={!r}".format(anchor))
                    size = lbl.get("size", LABEL_DEFAULT_SIZE)
                    if not is_num(size) or float(size) <= 0:
                        bad.append("size={!r}".format(lbl.get("size")))
                    lines = lbl.get("lines")
                    if lines is not None and (
                            not isinstance(lines, list) or not lines
                            or any(not isinstance(t, str) or not t for t in lines)):
                        bad.append("lines={!r}".format(lines))
                    if bad:
                        self.add("E-SCHEMA",
                                 "wire {}: invalid label field(s): {}".format(
                                     label, ", ".join(bad)),
                                 where=where, id=wid, field="label")
                    else:
                        label_rec = {"text": lbl["text"], "x": float(lbl["x"]),
                                     "y": float(lbl["y"]), "anchor": anchor,
                                     "size": float(size),
                                     "lines": [str(t) for t in lines] if lines else None}

            if pts is None:
                continue  # geometry unusable; E-SCHEMA already reported why
            rec = {"id": wire_key,
                   "from": frm if isinstance(frm, str) else None,
                   "to": to if isinstance(to, str) else None,
                   "pts": pts,
                   "nets": list(nets) if nets else [],
                   "label": label_rec,
                   "rect": (label_rect(label_rec) if label_rec else None)}
            self.wires.append(rec)

    # ------------------------------------------------------------ E-BOX-HIT
    def check_box_hit(self):
        for wire in self.wires:
            pts = wire["pts"]
            segs = []
            total = 0.0
            for i in range(len(pts) - 1):
                ln = dist(pts[i], pts[i + 1])
                if ln <= 1e-12:
                    continue
                segs.append((i, pts[i], pts[i + 1], total, ln))
                total += ln
            if not segs or total <= 0:
                continue
            # ignored arclength windows per box id
            ignored = {}
            trim = [(0.0, min(END_TRIM_PX, total)),
                    (max(0.0, total - END_TRIM_PX), total)]
            for box in self.boxes:
                ignored[box["id"]] = list(trim)
            for key, anchor in (("from", pts[0]), ("to", pts[-1])):
                bid = wire.get(key)
                if not bid:
                    continue
                extra = []
                for (_i, p0, p1, base, ln) in segs:
                    iv = seg_within_radius(p0, p1, anchor, ATTACH_RADIUS_PX)
                    if iv is None:
                        continue
                    extra.append((base + iv[0] * ln, base + iv[1] * ln))
                if extra:
                    ignored.setdefault(bid, []).extend(extra)

            hits = {}
            for box in self.boxes:
                bid = box["id"]
                # Endpoint boxes are tested too: the ignored windows above are
                # exactly what the spec excuses (6 px at both polyline ends for
                # every box, plus a 6 px radius around the attachment point for
                # the wire's own endpoint box).
                inflated = box["rect"].inflated(BOX_INFLATE_PX)
                for (i, p0, p1, base, ln) in segs:
                    clip = seg_enters_interior(p0, p1, inflated)
                    if clip is None:
                        continue
                    s0 = base + clip[0] * ln
                    s1 = base + clip[1] * ln
                    residual = subtract_intervals((s0, s1), merge_intervals(ignored.get(bid, [])))
                    if not residual:
                        continue
                    best = max(residual, key=lambda iv: iv[1] - iv[0])
                    depth = best[1] - best[0]
                    if depth <= MIN_INTRUSION_PX:
                        continue
                    mid = (best[0] + best[1]) / 2.0
                    t = (mid - base) / ln if ln else 0.0
                    hx = p0[0] + (p1[0] - p0[0]) * t
                    hy = p0[1] + (p1[1] - p0[1]) * t
                    prev = hits.get(bid)
                    if prev is None or depth > prev["depth"]:
                        hits[bid] = {"depth": depth, "seg": i,
                                     "point": (hx, hy), "rect": box["rect"]}
            for bid in sorted(hits):
                h = hits[bid]
                r = h["rect"]
                self.add("E-BOX-HIT",
                         "wire {} runs {:.1f} px through box {} "
                         "(box x={}..{}, y={}..{}; deepest at {})".format(
                             wire["id"], h["depth"], bid, fmt(r.x0), fmt(r.x1),
                             fmt(r.y0), fmt(r.y1), point_str(h["point"])),
                         wire=wire["id"], box=bid,
                         depth=round(h["depth"], 3),
                         segment=h["seg"],
                         point=[round(h["point"][0], 3), round(h["point"][1], 3)],
                         box_rect=r.as_dict())

    # --------------------------------------------------------- E-LABEL-BOX
    def check_label_box(self):
        for wire in self.wires:
            lr = wire["rect"]
            if lr is None:
                continue
            for box in self.boxes:
                inter = intersect_rect(lr, box["rect"])
                if inter.w > LABEL_BOX_TOL_PX and inter.h > LABEL_BOX_TOL_PX:
                    self.add("E-LABEL-BOX",
                             "label {!r} of wire {} overlaps box {} by "
                             "{}x{} px (label x={}..{}, y={}..{}; "
                             "box x={}..{}, y={}..{})".format(
                                 wire["label"]["text"], wire["id"], box["id"],
                                 fmt(inter.w), fmt(inter.h),
                                 fmt(lr.x0), fmt(lr.x1), fmt(lr.y0), fmt(lr.y1),
                                 fmt(box["rect"].x0), fmt(box["rect"].x1),
                                 fmt(box["rect"].y0), fmt(box["rect"].y1)),
                             wire=wire["id"], box=box["id"],
                             overlap=[round(inter.w, 3), round(inter.h, 3)],
                             label_rect=lr.as_dict(), box_rect=box["rect"].as_dict())

    # ------------------------------------------------------- E-LABEL-LABEL
    def check_label_label(self):
        labeled = [w for w in self.wires if w["rect"] is not None]
        for i in range(len(labeled)):
            for j in range(i + 1, len(labeled)):
                a, b = labeled[i], labeled[j]
                inter = intersect_rect(a["rect"], b["rect"])
                if inter.w > LABEL_LABEL_TOL_PX and inter.h > LABEL_LABEL_TOL_PX:
                    self.add("E-LABEL-LABEL",
                             "labels {!r} (wire {}) and {!r} (wire {}) overlap "
                             "by {}x{} px at ({},{})".format(
                                 a["label"]["text"], a["id"],
                                 b["label"]["text"], b["id"],
                                 fmt(inter.w), fmt(inter.h),
                                 fmt(inter.x0), fmt(inter.y0)),
                             wires=[a["id"], b["id"]],
                             overlap=[round(inter.w, 3), round(inter.h, 3)],
                             at=[round(inter.x0, 3), round(inter.y0, 3)])

    # ------------------------------------------------------------- E-ATTACH
    def check_attach(self):
        for wire in self.wires:
            pts = wire["pts"]
            for key, pt, which in (("from", pts[0], "first"), ("to", pts[-1], "last")):
                bid = wire.get(key)
                if not bid:
                    continue
                box = self.boxes_by_id.get(bid)
                if box is None:
                    continue  # box geometry invalid: already an E-SCHEMA finding
                d, side = point_boundary_distance(pt, box["rect"])
                if d > ATTACH_TOL_PX:
                    self.add("E-ATTACH",
                             "wire {} {} point {} is {} px from the boundary of "
                             "box {} ({} side, tolerance {} px; box x={}..{}, "
                             "y={}..{})".format(
                                 wire["id"], which, point_str(pt), fmt(d), bid,
                                 side, fmt(ATTACH_TOL_PX),
                                 fmt(box["rect"].x0), fmt(box["rect"].x1),
                                 fmt(box["rect"].y0), fmt(box["rect"].y1)),
                             wire=wire["id"], box=bid, end=key,
                             distance=round(d, 3), nearest_side=side,
                             point=[round(pt[0], 3), round(pt[1], 3)])

    # ------------------------------------------------- E-BOX/ZONE-OVERLAP
    def check_box_overlap(self):
        for i in range(len(self.boxes)):
            for j in range(i + 1, len(self.boxes)):
                a, b = self.boxes[i], self.boxes[j]
                if rects_overlap(a["rect"], b["rect"]):
                    inter = intersect_rect(a["rect"], b["rect"])
                    self.add("E-BOX-OVERLAP",
                             "boxes {} and {} overlap by {}x{} px "
                             "(intersection x={}..{}, y={}..{})".format(
                                 a["id"], b["id"], fmt(inter.w), fmt(inter.h),
                                 fmt(inter.x0), fmt(inter.x1),
                                 fmt(inter.y0), fmt(inter.y1)),
                             boxes=[a["id"], b["id"]],
                             overlap=[round(inter.w, 3), round(inter.h, 3)])

    def check_zone_overlap(self):
        for i in range(len(self.zones)):
            for j in range(i + 1, len(self.zones)):
                a, b = self.zones[i], self.zones[j]
                if rects_overlap(a["rect"], b["rect"]):
                    inter = intersect_rect(a["rect"], b["rect"])
                    self.add("E-ZONE-OVERLAP",
                             "zones {} and {} overlap by {}x{} px "
                             "(intersection x={}..{}, y={}..{})".format(
                                 a["id"], b["id"], fmt(inter.w), fmt(inter.h),
                                 fmt(inter.x0), fmt(inter.x1),
                                 fmt(inter.y0), fmt(inter.y1)),
                             zones=[a["id"], b["id"]],
                             overlap=[round(inter.w, 3), round(inter.h, 3)])

    # -------------------------------------------------------------- E-MARGIN
    def check_margin(self):
        if self.canvas is None:
            return
        safe = Rect(MARGIN_PX, MARGIN_PX,
                    self.canvas.x1 - MARGIN_PX, self.canvas.y1 - MARGIN_PX)
        for group, kind in ((self.boxes, "box"), (self.zones, "zone")):
            for item in group:
                r = item["rect"]
                bad = []
                if r.x0 < safe.x0:
                    bad.append("left x={} (needs >= {})".format(fmt(r.x0), fmt(safe.x0)))
                if r.x1 > safe.x1:
                    bad.append("right x={} (needs <= {})".format(fmt(r.x1), fmt(safe.x1)))
                if r.y0 < safe.y0:
                    bad.append("top y={} (needs >= {})".format(fmt(r.y0), fmt(safe.y0)))
                if r.y1 > safe.y1:
                    bad.append("bottom y={} (needs <= {})".format(fmt(r.y1), fmt(safe.y1)))
                if bad:
                    outside = (r.x0 < 0 or r.y0 < 0
                               or r.x1 > self.canvas.x1 or r.y1 > self.canvas.y1)
                    self.add("E-MARGIN",
                             "{} {} violates the {} px canvas margin: {}{}"
                             .format(kind, item["id"], fmt(MARGIN_PX),
                                     "; ".join(bad),
                                     " [extends outside the canvas]" if outside else ""),
                             kind=kind, id=item["id"],
                             rect=r.as_dict(), outside_canvas=bool(outside),
                             violations=bad)

    # --------------------------------------------------------------- W-CROSS
    def check_crossings(self):
        segs_by_wire = []
        for wire in self.wires:
            pts = wire["pts"]
            segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)
                    if dist(pts[i], pts[i + 1]) > 1e-12]
            segs_by_wire.append((wire["id"], segs))
        total = 0
        pair_counts = {}
        pair_points = {}
        for i in range(len(segs_by_wire)):
            ida, sega = segs_by_wire[i]
            for j in range(i + 1, len(segs_by_wire)):
                idb, segb = segs_by_wire[j]
                pts_hit = []
                for p0, p1 in sega:
                    for q0, q1 in segb:
                        pt = seg_proper_intersection(p0, p1, q0, q1)
                        if pt is not None:
                            pts_hit.append(pt)
                if pts_hit:
                    total += len(pts_hit)
                    key = (ida, idb)
                    pair_counts[key] = pair_counts.get(key, 0) + len(pts_hit)
                    pair_points.setdefault(key, []).extend(pts_hit)
        self.crossings_total = total
        worst = sorted(pair_counts.items(),
                       key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))[:WORST_PAIRS]
        self.crossing_pairs = [
            {"wires": [a, b], "count": n,
             "points": [[round(x, 2), round(y, 2)]
                        for x, y in pair_points[(a, b)][:6]]}
            for (a, b), n in worst]
        if total:
            self.add("W-CROSS",
                     "{} proper crossing(s) between segments of different wires; "
                     "worst pair: {} x {} ({} crossing(s))".format(
                         total, self.crossing_pairs[0]["wires"][0],
                         self.crossing_pairs[0]["wires"][1],
                         self.crossing_pairs[0]["count"]),
                     total=total, worst_pairs=self.crossing_pairs)
        else:
            self.add("W-CROSS", "no proper crossings between different wires",
                     total=0, worst_pairs=[])

    # ------------------------------------------------------------ W-COLLINEAR
    def check_collinear(self):
        segs = []  # (wire_id, axis, offset, lo, hi)
        for wire in self.wires:
            pts = wire["pts"]
            for i in range(len(pts) - 1):
                p, q = pts[i], pts[i + 1]
                dx = abs(q[0] - p[0])
                dy = abs(q[1] - p[1])
                if dy <= COLLINEAR_TOL_PX and dx > COLLINEAR_TOL_PX:
                    segs.append((wire["id"], "h", (p[1] + q[1]) / 2.0,
                                 min(p[0], q[0]), max(p[0], q[0])))
                elif dx <= COLLINEAR_TOL_PX and dy > COLLINEAR_TOL_PX:
                    segs.append((wire["id"], "v", (p[0] + q[0]) / 2.0,
                                 min(p[1], q[1]), max(p[1], q[1])))
        pairs = {}
        for i in range(len(segs)):
            ida, axa, offa, loa, hia = segs[i]
            for j in range(i + 1, len(segs)):
                idb, axb, offb, lob, hib = segs[j]
                if ida == idb or axa != axb:
                    continue
                if abs(offa - offb) > COLLINEAR_TOL_PX:
                    continue
                lo = max(loa, lob)
                hi = min(hia, hib)
                overlap = hi - lo
                if overlap <= COLLINEAR_MIN_OVERLAP_PX:
                    continue
                key = (ida, idb) if ida <= idb else (idb, ida)
                prev = pairs.get(key)
                if prev is None or overlap > prev["overlap"]:
                    pairs[key] = {"overlap": overlap, "axis": axa,
                                  "offset": (offa + offb) / 2.0,
                                  "span": [lo, hi]}
        self.collinear_pairs = [
            {"wires": [a, b], "axis": d["axis"],
             "offset": round(d["offset"], 3),
             "span": [round(d["span"][0], 3), round(d["span"][1], 3)],
             "overlap": round(d["overlap"], 3)}
            for (a, b), d in sorted(pairs.items(),
                                    key=lambda kv: (-kv[1]["overlap"], kv[0]))]
        if self.collinear_pairs:
            self.add("W-COLLINEAR",
                     "{} wire pair(s) share a collinear overlapping segment; "
                     "longest overlap: {} px between {} and {}".format(
                         len(self.collinear_pairs),
                         fmt(self.collinear_pairs[0]["overlap"]),
                         self.collinear_pairs[0]["wires"][0],
                         self.collinear_pairs[0]["wires"][1]),
                     total=len(self.collinear_pairs),
                     pairs=self.collinear_pairs[:MAX_COLLINEAR_DETAIL])
        else:
            self.add("W-COLLINEAR",
                     "no collinear overlapping segments between different wires",
                     total=0, pairs=[])

    # ---------------------------------------------------------- W-WHITESPACE
    def check_whitespace(self):
        content = None
        for item in list(self.boxes) + list(self.zones):
            content = union_rect(content, item["rect"])
        canvas = self.canvas
        empty_fraction = 1.0
        largest = None
        clipped = None
        if canvas is not None:
            if content is None:
                empty_fraction = 1.0
                largest = {"x": 0.0, "y": 0.0, "w": canvas.w, "h": canvas.h,
                           "area": canvas.w * canvas.h, "approx": False}
                clipped = canvas
            else:
                clipped = intersect_rect(content, canvas)
                if clipped.w <= EPS or clipped.h <= EPS:
                    empty_fraction = 1.0
                    largest = {"x": 0.0, "y": 0.0, "w": canvas.w, "h": canvas.h,
                               "area": canvas.w * canvas.h, "approx": False}
                    clipped = canvas
                else:
                    area = clipped.w * clipped.h
                    empty_fraction = 1.0 - (area / (canvas.w * canvas.h))
                    empty_fraction = min(1.0, max(0.0, empty_fraction))
                    obstacles = [i["rect"] for i in list(self.boxes) + list(self.zones)]
                    largest = largest_empty_rect(obstacles, clipped)
        self.whitespace = {
            "empty_fraction": round(empty_fraction, 6),
            "empty_pct": round(empty_fraction * 100.0, 3),
            "content_bbox": (content.as_dict() if content else None),
            "content_bbox_clipped_to_canvas": (clipped.as_dict() if clipped else None),
            "content_area": (clipped.w * clipped.h if clipped else 0.0),
            "canvas_area": (canvas.w * canvas.h if canvas else 0.0),
            "largest_empty_rect": largest,
        }
        if largest:
            msg = ("{:.1f}% of the canvas is empty outside the content bbox; "
                   "largest empty rectangle inside it: {}x{} px at ({},{}){}"
                   .format(empty_fraction * 100.0, fmt(largest["w"]),
                           fmt(largest["h"]), fmt(largest["x"]), fmt(largest["y"]),
                           " [approx, {} px grid]".format(fmt(GRID_FALLBACK_STEP))
                           if largest.get("approx") else ""))
        else:
            msg = ("{:.1f}% of the canvas is empty outside the content bbox; "
                   "no empty rectangle could be measured (no canvas)"
                   .format(empty_fraction * 100.0))
        self.add("W-WHITESPACE", msg, **self.whitespace)

    # ------------------------------------------------------------- W-BALANCE
    def check_balance(self):
        widths = {}
        heights = {}
        for b in self.boxes:
            widths[_round_key(b["rect"].w)] = widths.get(_round_key(b["rect"].w), 0) + 1
            heights[_round_key(b["rect"].h)] = heights.get(_round_key(b["rect"].h), 0) + 1

        def clusters(axis):
            if axis == "x":
                items = sorted(self.boxes, key=lambda b: (b["rect"].cx, b["id"]))
                centre = lambda b: b["rect"].cx
                edge = lambda b: b["rect"].x0
                size = lambda b: b["rect"].w
            else:
                items = sorted(self.boxes, key=lambda b: (b["rect"].cy, b["id"]))
                centre = lambda b: b["rect"].cy
                edge = lambda b: b["rect"].y0
                size = lambda b: b["rect"].h
            out = []
            cur = []
            mean = None
            for b in items:
                c = centre(b)
                if mean is None or abs(c - mean) <= COLUMN_TOL_PX:
                    cur.append(b)
                    mean = sum(centre(x) for x in cur) / len(cur)
                else:
                    out.append(cur)
                    cur = [b]
                    mean = c
            if cur:
                out.append(cur)
            res = []
            for idx, group in enumerate(out, start=1):
                edges = [edge(b) for b in group]
                res.append({
                    "index": idx,
                    "ids": [b["id"] for b in group],
                    "centre_range": [round(min(centre(b) for b in group), 2),
                                     round(max(centre(b) for b in group), 2)],
                    "distinct_widths": len({_round_key(size(b)) for b in group}),
                    "distinct_heights": len({_round_key(b["rect"].h) for b in group}),
                    "edge_min": round(min(edges), 2),
                    "edge_max": round(max(edges), 2),
                    "edge_span": round(max(edges) - min(edges), 2),
                    "aligned": (max(edges) - min(edges)) <= ALIGN_TOL_PX,
                })
            return res

        self.balance = {
            "distinct_widths": {"count": len(widths),
                                "values": [{"w": k, "count": v}
                                           for k, v in sorted(widths.items())]},
            "distinct_heights": {"count": len(heights),
                                 "values": [{"h": k, "count": v}
                                            for k, v in sorted(heights.items())]},
            "columns": clusters("x"),
            "rows": clusters("y"),
            "column_tolerance_px": COLUMN_TOL_PX,
            "align_tolerance_px": ALIGN_TOL_PX,
        }
        mis_cols = [c for c in self.balance["columns"] if not c["aligned"]]
        mis_rows = [r for r in self.balance["rows"] if not r["aligned"]]
        self.add("W-BALANCE",
                 "{} distinct box width(s), {} distinct height(s); "
                 "{} column(s) and {} row(s) do not share a common left/top edge "
                 "within {} px".format(
                     len(widths), len(heights), len(mis_cols), len(mis_rows),
                     fmt(ALIGN_TOL_PX)),
                 **self.balance)

    # ------------------------------------------------------- W-ZONE-CONTAIN
    def check_zone_containment(self):
        tol = ZONE_CONTAIN_TOL_PX
        for box in self.boxes:
            c = (box["rect"].cx, box["rect"].cy)
            for zone in self.zones:
                zr = zone["rect"]
                if not zr.contains_point(c):
                    continue
                slack = min(box["rect"].x0 - zr.x0, zr.x1 - box["rect"].x1,
                            box["rect"].y0 - zr.y0, zr.y1 - box["rect"].y1)
                if slack < -tol:
                    self.add("W-ZONE-CONTAIN",
                             "box {} (centre inside zone {}) is not contained by "
                             "it: overhang {} px (box x={}..{}, y={}..{}; "
                             "zone x={}..{}, y={}..{})".format(
                                 box["id"], zone["id"], fmt(-slack),
                                 fmt(box["rect"].x0), fmt(box["rect"].x1),
                                 fmt(box["rect"].y0), fmt(box["rect"].y1),
                                 fmt(zr.x0), fmt(zr.x1), fmt(zr.y0), fmt(zr.y1)),
                             box=box["id"], zone=zone["id"],
                             overhang=round(-slack, 3),
                             note="membership inferred from the box centre; "
                                  "the schema has no explicit membership field")

    # --------------------------------------------------------------- I-STATS
    def collect_stats(self):
        kinds = {}
        for b in self.boxes:
            k = b["kind"] if isinstance(b["kind"], str) else "?"
            kinds[k] = kinds.get(k, 0) + 1
        total_len = 0.0
        longest = None
        for w in self.wires:
            ln = polyline_length(w["pts"])
            total_len += ln
            if longest is None or ln > longest[1]:
                longest = (w["id"], ln)
        content = None
        for item in list(self.boxes) + list(self.zones):
            content = union_rect(content, item["rect"])
        margins = None
        if self.canvas is not None and content is not None:
            margins = {
                "left": round(max(0.0, content.x0) / self.canvas.w * 100.0, 3),
                "right": round(max(0.0, self.canvas.w - content.x1) / self.canvas.w * 100.0, 3),
                "top": round(max(0.0, content.y0) / self.canvas.h * 100.0, 3),
                "bottom": round(max(0.0, self.canvas.h - content.y1) / self.canvas.h * 100.0, 3),
            }
        self.stats = {
            "canvas": ({"w": self.canvas.w, "h": self.canvas.h}
                       if self.canvas else None),
            "boxes_total": len(self.boxes),
            "boxes_by_kind": kinds,
            "zones_total": len(self.zones),
            "wires_total": len(self.wires),
            "wire_labels": sum(1 for w in self.wires if w["label"] is not None),
            "total_wire_length": round(total_len, 3),
            "longest_wire": ({"id": longest[0], "length": round(longest[1], 3)}
                             if longest else None),
            "content_bbox": (content.as_dict() if content else None),
            "empty_margin_pct": margins,
            "empty_margin_pct_note": ("content bbox edge distance to the canvas "
                                      "edge, as a percentage of canvas w/h"),
        }
        canvas_s = ("{}x{}".format(fmt(self.canvas.w), fmt(self.canvas.h))
                    if self.canvas else "invalid")
        self.add("I-STATS",
                 "canvas {}; boxes {} ({}); zones {}; wires {}; wire labels {}; "
                 "total wire length {} px; longest wire {} ({} px); "
                 "content bbox {}; empty margins L/R/T/B {}% / {}% / {}% / {}%"
                 .format(canvas_s, len(self.boxes),
                         ", ".join("{}={}".format(k, kinds[k]) for k in sorted(kinds)) or "-",
                         len(self.zones), len(self.wires),
                         self.stats["wire_labels"],
                         fmt(self.stats["total_wire_length"]),
                         (longest[0] if longest else "-"),
                         fmt(longest[1] if longest else 0.0),
                         (("x={}..{}, y={}..{}".format(
                             fmt(content.x0), fmt(content.x1), fmt(content.y0),
                             fmt(content.y1))) if content else "-"),
                         fmt(margins["left"]) if margins else "-",
                         fmt(margins["right"]) if margins else "-",
                         fmt(margins["top"]) if margins else "-",
                         fmt(margins["bottom"]) if margins else "-"),
                 **self.stats)

    # ------------------------------------------------------------- fidelity
    def check_fidelity(self):
        if not self.want_fidelity:
            return
        mod, links_list, source, msg = load_arch_data(self.script_dir)
        if mod is None:
            self.fidelity["available"] = False
            self.fidelity["message"] = msg
            sys.stderr.write("audit_diagram: {}\n".format(msg))
            return
        self.fidelity["available"] = True
        self.fidelity["link_source"] = source
        links = set()
        for item in links_list:
            try:
                a, b, n = item
            except Exception:  # noqa: BLE001
                self.add("E-FIDELITY",
                         "arch_data link entry is not a 3-tuple: {!r}".format(item),
                         category="LINKS", malformed=repr(item))
                continue
            links.add((a, b, n))
        layout_links = set()
        for w in self.wires:
            if not w.get("from") or not w.get("to"):
                continue
            for net in w["nets"]:
                layout_links.add((w["from"], w["to"], net))
        missing = sorted(links - layout_links, key=lambda t: (str(t[0]), str(t[1]), str(t[2])))
        extra = sorted(layout_links - links, key=lambda t: (str(t[0]), str(t[1]), str(t[2])))
        if missing or extra:
            self.add("E-FIDELITY",
                     "LINKS mismatch: {} missing, {} extra (missing={}; extra={})"
                     .format(len(missing), len(extra),
                             _brief([list(t) for t in missing]),
                             _brief([list(t) for t in extra])),
                     category="LINKS",
                     missing=[list(t) for t in missing],
                     extra=[list(t) for t in extra])

        entities = set(mod.ENTITIES or {})
        layout_entities = {b["id"] for b in self.boxes if b["kind"] == "entity"}
        miss = sorted(entities - layout_entities)
        ext = sorted(layout_entities - entities)
        if miss or ext:
            self.add("E-FIDELITY",
                     "ENTITIES mismatch: {} missing, {} extra (missing={}; "
                     "extra={})".format(len(miss), len(ext), _brief(miss), _brief(ext)),
                     category="ENTITIES", missing=miss, extra=ext)

        externals = set(mod.EXTERNAL or {})
        layout_ext = {b["id"] for b in self.boxes if b["kind"] == "ext"}
        miss = sorted(externals - layout_ext)
        extra = sorted(layout_ext - externals)
        if miss or extra:
            self.add("E-FIDELITY",
                     "EXTERNAL mismatch: {} missing, {} extra (missing={}; "
                     "extra={})".format(len(miss), len(extra), _brief(miss), _brief(extra)),
                     category="EXTERNAL", missing=miss, extra=extra)

        globals_map = mod.GLOBALS or {}
        for b in self.boxes:
            want = list(globals_map.get(b["id"], []) or [])
            got = list(b["globals"] or [])
            if sorted(want) != sorted(got):
                missing = sorted(set(want) - set(got))
                extra = sorted(set(got) - set(want))
                detail = []
                if missing:
                    detail.append("missing={}".format(_brief(missing)))
                if extra:
                    detail.append("extra={}".format(_brief(extra)))
                if not detail:
                    detail.append("same members, different order")
                self.add("E-GLOBAL-MISSING",
                         "box {} globals mismatch with GLOBALS[{}]: {} "
                         "(layout={}, arch_data={})".format(
                             b["id"], b["id"], "; ".join(detail),
                             _brief(got), _brief(want)),
                         box=b["id"], missing=missing, extra=extra,
                         layout=sorted(got), expected=sorted(want))

    # ----------------------------------------------------------------- run
    def run(self):
        self.validate()
        self.check_box_hit()
        self.check_label_box()
        self.check_label_label()
        self.check_attach()
        self.check_box_overlap()
        self.check_zone_overlap()
        self.check_margin()
        self.check_crossings()
        self.check_collinear()
        self.check_whitespace()
        self.check_balance()
        self.check_zone_containment()
        self.collect_stats()
        self.check_fidelity()
        return self.report()

    def report(self):
        errors = self.errors()
        longest = self.stats.get("longest_wire") or {"length": 0.0}
        empty_fraction = float(self.whitespace.get("empty_fraction", 0.0) or 0.0)
        score = (100.0 * len(errors)
                 + 10.0 * self.crossings_total
                 + 5.0 * len(self.collinear_pairs)
                 + 200.0 * empty_fraction
                 + 1.0 * float(longest["length"]) / 100.0)
        by_code = {}
        for f in self.findings:
            by_code[f["code"]] = by_code.get(f["code"], 0) + 1
        return {
            "tool": "audit_diagram.py",
            "version": "1.0",
            "file": self.path,
            "layout_id": self.layout_id,
            "canvas": ({"w": self.canvas.w, "h": self.canvas.h}
                       if self.canvas else None),
            "fidelity": self.fidelity,
            "findings": self.findings,
            "counts": {
                "errors": len(errors),
                "warnings": sum(1 for f in self.findings if f["level"] == "warning"),
                "info": sum(1 for f in self.findings if f["level"] == "info"),
                "by_code": by_code,
            },
            "crossings": {"total": self.crossings_total,
                          "worst_pairs": self.crossing_pairs},
            "collinear": {"pairs": len(self.collinear_pairs),
                          "details": self.collinear_pairs},
            "whitespace": self.whitespace,
            "balance": self.balance,
            "stats": self.stats,
            "score": round(score, 2),
            "score_components": {
                "errors": len(errors),
                "crossings": self.crossings_total,
                "collinear_pairs": len(self.collinear_pairs),
                "empty_fraction": round(empty_fraction, 6),
                "longest_wire": round(float(longest["length"]), 3),
                "formula": ("100*errors + 10*crossings + 5*collinear_pairs "
                            "+ 200*empty_fraction + longest_wire/100"),
            },
        }


def _brief(items, limit=8):
    """Compact list rendering for finding messages."""
    items = list(items)
    if not items:
        return "[]"
    shown = ", ".join(repr(i) for i in items[:limit])
    if len(items) > limit:
        shown += ", ... (+{} more)".format(len(items) - limit)
    return "[" + shown + "]"


# --------------------------------------------------------------------------- #
# human-readable rendering
# --------------------------------------------------------------------------- #
def render_finding(f, out):
    code = f["code"]
    d = f.get("data", {})
    out.append("  - " + f["message"])
    if code == "W-CROSS" and d.get("worst_pairs"):
        out.append("    worst wire pairs (crossings, points):")
        for p in d["worst_pairs"]:
            out.append("      {} x {}: {}  {}".format(
                p["wires"][0], p["wires"][1], p["count"],
                " ".join("({},{})".format(fmt(x), fmt(y)) for x, y in p["points"])))
    elif code == "W-COLLINEAR" and d.get("pairs"):
        for p in d["pairs"]:
            out.append("      {} x {}: axis={} offset={} span={}..{} overlap={} px"
                       .format(p["wires"][0], p["wires"][1], p["axis"],
                               fmt(p["offset"]), fmt(p["span"][0]),
                               fmt(p["span"][1]), fmt(p["overlap"])))
    elif code == "W-WHITESPACE":
        r = d.get("largest_empty_rect")
        out.append("      content bbox: {}   canvas area {} px^2, content area {} px^2"
                   .format(_bbox_str(d.get("content_bbox")),
                           fmt(d.get("canvas_area")), fmt(d.get("content_area"))))
        if r:
            out.append("      largest empty rect: x={} y={} w={} h={} (area {} px^2{})"
                       .format(fmt(r["x"]), fmt(r["y"]), fmt(r["w"]), fmt(r["h"]),
                               fmt(r["area"]),
                               ", approx" if r.get("approx") else ""))
    elif code == "W-BALANCE":
        dw = d.get("distinct_widths", {})
        dh = d.get("distinct_heights", {})
        out.append("      widths: {} distinct -> {}".format(
            dw.get("count"),
            ", ".join("{} px x{}".format(fmt(v["w"]), v["count"])
                      for v in dw.get("values", []))))
        out.append("      heights: {} distinct -> {}".format(
            dh.get("count"),
            ", ".join("{} px x{}".format(fmt(v["h"]), v["count"])
                      for v in dh.get("values", []))))
        for kind, key, edge in (("column", "columns", "left"),
                                ("row", "rows", "top")):
            groups = d.get(key, [])
            if not groups:
                continue
            out.append("      {}s ({}; clustering tolerance {} px, shared-{} edge "
                       "tolerance {} px):".format(
                           kind, len(groups), fmt(d.get("column_tolerance_px")),
                           edge, fmt(d.get("align_tolerance_px"))))
            for g in groups[:MAX_BALANCE_DETAIL]:
                out.append("        #{} {} widths={} heights={} {}-edge span {} px "
                           "({}..{}) aligned={}".format(
                               g["index"], ",".join(g["ids"]), g["distinct_widths"],
                               g["distinct_heights"], edge, fmt(g["edge_span"]),
                               fmt(g["edge_min"]), fmt(g["edge_max"]),
                               "yes" if g["aligned"] else "NO"))
            if len(groups) > MAX_BALANCE_DETAIL:
                out.append("        ... (+{} more)".format(len(groups) - MAX_BALANCE_DETAIL))
    elif code == "I-STATS":
        st = d
        out.append("      canvas: {}".format(
            "{}x{}".format(fmt(st["canvas"]["w"]), fmt(st["canvas"]["h"]))
            if st.get("canvas") else "invalid"))
        out.append("      boxes: {} total ({})".format(
            st.get("boxes_total"),
            ", ".join("{}={}".format(k, v)
                      for k, v in sorted((st.get("boxes_by_kind") or {}).items())) or "-"))
        out.append("      zones: {}   wires: {}   wire labels: {}".format(
            st.get("zones_total"), st.get("wires_total"), st.get("wire_labels")))
        out.append("      total wire length: {} px   longest: {} ({} px)".format(
            fmt(st.get("total_wire_length")),
            (st.get("longest_wire") or {}).get("id", "-"),
            fmt((st.get("longest_wire") or {}).get("length", 0.0))))
        out.append("      content bbox: {}".format(_bbox_str(st.get("content_bbox"))))
        m = st.get("empty_margin_pct")
        if m:
            out.append("      empty margins (bbox edge -> canvas edge): "
                       "left {}%  right {}%  top {}%  bottom {}%".format(
                           fmt(m["left"]), fmt(m["right"]), fmt(m["top"]),
                           fmt(m["bottom"])))
    elif code in ("E-FIDELITY", "E-GLOBAL-MISSING"):
        if d.get("missing"):
            out.append("      missing: {}".format(_brief(d["missing"], 20)))
        if d.get("extra"):
            out.append("      extra: {}".format(_brief(d["extra"], 20)))


def _bbox_str(b):
    if not b:
        return "-"
    return "x={}..{}, y={}..{} ({}x{})".format(
        fmt(b["x"]), fmt(b["x"] + b["w"]), fmt(b["y"]), fmt(b["y"] + b["h"]),
        fmt(b["w"]), fmt(b["h"]))


def render_human(report, quiet=False):
    lines = []
    findings = report["findings"]
    if not quiet:
        st = report.get("stats") or {}
        lines.append("audit_diagram.py: {} (id={})".format(
            report["file"], report["layout_id"] or "-"))
        lines.append("canvas {}   boxes {}   zones {}   wires {}   labels {}".format(
            "{}x{}".format(fmt(report["canvas"]["w"]), fmt(report["canvas"]["h"]))
            if report.get("canvas") else "invalid",
            st.get("boxes_total", 0), st.get("zones_total", 0),
            st.get("wires_total", 0), st.get("wire_labels", 0)))
        if report.get("fidelity", {}).get("requested"):
            fi = report["fidelity"]
            lines.append("fidelity: {}".format(
                "checked against scripts/arch_data.py" if fi.get("available")
                else (fi.get("message") or "skipped")))
        lines.append("")
    by_code = {}
    for f in findings:
        by_code.setdefault(f["code"], []).append(f)
    for code in CODE_ORDER:
        group = by_code.get(code)
        if not group:
            continue
        if quiet and CODE_LEVEL.get(code) != "error":
            continue
        lines.append("== {} ({}) ==".format(code, len(group)))
        for f in group[:HUMAN_MAX_PER_CODE]:
            render_finding(f, lines)
        if len(group) > HUMAN_MAX_PER_CODE:
            lines.append("  - ... (+{} more {} finding(s))".format(
                len(group) - HUMAN_MAX_PER_CODE, code))
        lines.append("")
    if not quiet:
        c = report["counts"]
        lines.append("== summary ==")
        codes = " ".join("{}={}".format(k, c["by_code"][k])
                         for k in CODE_ORDER if k in c["by_code"]) or "none"
        lines.append("  errors={} warnings={} info={}   {}".format(
            c["errors"], c["warnings"], c["info"], codes))
        sc = report["score_components"]
        lines.append("  score = 100*{errors} + 10*{crossings} + 5*{collinear_pairs}"
                     " + 200*{empty_fraction} + {longest_wire}/100".format(**sc))
        lines.append("  = 100*{} + 10*{} + 5*{} + 200*{} + {}/100 = {}".format(
            sc["errors"], sc["crossings"], sc["collinear_pairs"],
            sc["empty_fraction"], fmt(sc["longest_wire"]), fmt(report["score"])))
        lines.append("  exit code: {}".format(1 if c["errors"] else 0))
        lines.append("")
    lines.append("SCORE {}".format(fmt(report["score"])))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def build_report(path, fidelity=False, script_dir=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        audit = Auditor({}, path, fidelity=fidelity, script_dir=script_dir)
        audit.add("E-SCHEMA", "cannot read layout file: {}".format(exc),
                  field="$", path=path)
        audit.check_fidelity()
        return audit.report()
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        audit = Auditor({}, path, fidelity=fidelity, script_dir=script_dir)
        audit.add("E-SCHEMA",
                  "layout file is not valid JSON: {}".format(exc), field="$",
                  path=path)
        audit.check_fidelity()
        return audit.report()
    audit = Auditor(doc, path, fidelity=fidelity, script_dir=script_dir)
    try:
        return audit.run()
    except Exception as exc:  # noqa: BLE001 - defensive: never crash on input
        audit.add("E-SCHEMA",
                  "internal audit error: {}: {}".format(type(exc).__name__, exc),
                  field="$")
        return audit.report()


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="audit_diagram.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("Objective geometry auditor for generated SVG block "
                     "diagrams. Reads the layout sidecar JSON and reports "
                     "stable-coded geometric violations."),
        epilog=("exit codes:\n"
                "  0  no ERROR-level violation\n"
                "  1  at least one ERROR-level violation "
                "(or unreadable/invalid input)\n"
                "  2  command-line usage error\n\n"
                "The last stdout line is always 'SCORE <number>' (lower is "
                "better):\n"
                "  score = 100*errors + 10*crossings + 5*collinear_pairs\n"
                "          + 200*empty_fraction + longest_wire/100\n\n"
                "checks: E-SCHEMA E-BOX-HIT E-LABEL-BOX E-LABEL-LABEL "
                "E-ATTACH E-BOX-OVERLAP\n"
                "        E-ZONE-OVERLAP E-MARGIN W-CROSS W-COLLINEAR "
                "W-WHITESPACE W-BALANCE\n"
                "        E-GLOBAL-MISSING E-FIDELITY W-ZONE-CONTAIN I-STATS"))
    ap.add_argument("layout", metavar="layout.json",
                    help="path to the layout sidecar JSON emitted by the generator")
    ap.add_argument("--json", action="store_true",
                    help="print the complete machine-readable report followed by "
                         "the SCORE line, instead of the human table")
    ap.add_argument("--quiet", action="store_true",
                    help="human output limited to ERROR findings + the SCORE line")
    ap.add_argument("--fidelity", action="store_true",
                    help="cross-check against scripts/arch_data.py "
                         "(skipped with a message when absent)")
    args = ap.parse_args(argv)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    report = build_report(args.layout, fidelity=args.fidelity, script_dir=script_dir)

    if args.json:
        # Machine mode: complete JSON report + exactly one trailing SCORE line.
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2,
                                    sort_keys=False))
        sys.stdout.write("\n")
        sys.stdout.write("SCORE {}\n".format(fmt(report["score"])))
    else:
        sys.stdout.write(render_human(report, quiet=args.quiet))
        sys.stdout.write("\n")
    sys.stdout.flush()
    return 1 if report["counts"]["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
