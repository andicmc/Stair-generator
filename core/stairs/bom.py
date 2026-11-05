"""Simple quantity list: (part, count, length / area)."""


def build_bom(b, info):
    bom = []
    treads = [t for t in b.treads if t["kind"] in ("tread", "top_tread")]
    winders = [t for t in b.treads if t["kind"] == "winder"]
    risers = [r for r in b.risers if not r.get("open")]
    if treads:
        bom.append({"part": "tread", "count": len(treads),
                    "area_m2": round(sum(t["area_m2"] for t in treads), 3),
                    "thickness_mm": b.p.tread_thk})
    if winders:
        bom.append({"part": "winder", "count": len(winders),
                    "area_m2": round(sum(t["area_m2"] for t in winders), 3),
                    "thickness_mm": b.p.tread_thk})
    if risers:
        bom.append({"part": "riser", "count": len(risers),
                    "area_m2": round(sum(r["area_m2"] for r in risers), 3),
                    "thickness_mm": b.p.riser_thk})
    if b.landings:
        bom.append({"part": "landing", "count": len(b.landings),
                    "area_m2": round(sum(l["area_m2"] for l in b.landings), 3),
                    "thickness_mm": b.p.landing_thk})
    if b.stringers:
        bom.append({"part": "stringer ({})".format(b.p.stringer_type), "count": len(b.stringers),
                    "length_m": round(sum(s["length"] for s in b.stringers) / 1000.0, 3),
                    "thickness_mm": b.p.stringer_thk})
    for s in b.supports:
        bom.append({"part": s["kind"], "count": 1, "length_m": round(s["height"] / 1000.0, 3),
                    "radius_mm": s.get("radius")})
    return bom
