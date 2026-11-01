"""Convert taiwan-atlas counties TopoJSON into projected, simplified SVG paths.

Projection (shared with src/app.html):
    x = (lon - LON0) * cos(LAT_REF) * K
    y = (LAT0 - lat) * K
"""
import json, math, sys

LON0, LAT0, LAT_REF, K = 119.25, 25.40, 23.7, 1000.0
COS = math.cos(math.radians(LAT_REF))
VIEW_W = round((122.10 - LON0) * COS * K)
VIEW_H = round((LAT0 - 21.85) * K)
TOL = 0.9  # Douglas-Peucker tolerance in view units (~90 m)


def project(lon, lat):
    return ((lon - LON0) * COS * K, (LAT0 - lat) * K)


def decode_arcs(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    out = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        out.append(pts)
    return out


def ring_points(ring, arcs):
    pts = []
    for idx in ring:
        a = arcs[idx] if idx >= 0 else arcs[~idx][::-1]
        pts.extend(a if not pts else a[1:])
    return pts


def dp(points, tol):
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = points[i], points[j]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        best, bi = 0, -1
        for k in range(i + 1, j):
            x0, y0 = points[k]
            # closed rings start and end on the same point: fall back to point distance
            d = (abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / norm) if norm > 1e-6 else math.hypot(x0 - x1, y0 - y1)
            if d > best:
                best, bi = d, k
        if best > tol:
            keep[bi] = True
            stack += [(i, bi), (bi, j)]
    return [p for p, k in zip(points, keep) if k]


def in_view(pts):
    return any(-50 < x < VIEW_W + 50 and -50 < y < VIEW_H + 50 for x, y in pts)


def path_for(geom, arcs):
    polys = geom["arcs"] if geom["type"] == "MultiPolygon" else [geom["arcs"]]
    parts = []
    for poly in polys:
        for ring in poly:
            pts = [project(lon, lat) for lon, lat in ring_points(ring, arcs)]
            if not in_view(pts):
                continue
            pts = dp(pts, TOL)
            if len(pts) < 4:
                continue
            d = "M" + "L".join(f"{x:.0f},{y:.0f}" for x, y in pts) + "Z"
            parts.append(d)
    return "".join(parts)


def main(src, dst):
    topo = json.load(open(src, encoding="utf-8"))
    arcs = decode_arcs(topo)
    counties = []
    for g in topo["objects"]["counties"]["geometries"]:
        d = path_for(g, arcs)
        if d:
            counties.append({"name": g["properties"]["COUNTYNAME"], "d": d})
    out = {"w": VIEW_W, "h": VIEW_H, "proj": [LON0, LAT0, LAT_REF, K], "counties": counties}
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(counties)} counties, {sum(len(c['d']) for c in counties)/1024:.1f} KB of path data, view {VIEW_W}x{VIEW_H}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
