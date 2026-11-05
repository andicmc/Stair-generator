"""Quantity list for a guard."""
from .rails import length_3d


def build_bom(p, sides_out):
    posts = [q for s in sides_out for q in s["posts"]]
    bom = []
    if posts:
        bom.append({"part": "post", "count": len(posts),
                    "length_m": round(sum(q["height"] for q in posts) / 1000.0, 3),
                    "profile": posts[0]["profile"]["shape"]})
    top = sum(length_3d(s["top_rail"]["polyline"]) for s in sides_out)
    bom.append({"part": "top rail", "count": len(sides_out), "length_m": round(top / 1000.0, 3)})
    if p.bottom_rail:
        bot = sum(length_3d(s["bottom_rail"]["polyline"]) for s in sides_out if s["bottom_rail"])
        bom.append({"part": "bottom rail", "count": len(sides_out), "length_m": round(bot / 1000.0, 3)})
    if p.handrail:
        hr = [s["handrail"] for s in sides_out if s.get("handrail")]
        bom.append({"part": "handrail", "count": len(hr),
                    "length_m": round(sum(length_3d(h["polyline"]) for h in hr) / 1000.0, 3)})
        bom.append({"part": "handrail bracket", "count": sum(len(s.get("brackets", [])) for s in sides_out)})
    bal = [b for s in sides_out for b in s["infill"]["balusters"]]
    if bal:
        bom.append({"part": "baluster", "count": len(bal),
                    "length_m": round(sum(b["top"][2] - b["bottom"][2] for b in bal) / 1000.0, 3)})
    for key, part in (("bars", "horizontal bar"), ("cables", "cable")):
        items = [b for s in sides_out for b in s["infill"][key]]
        if items:
            bom.append({"part": part, "count": len(items),
                        "length_m": round(sum(length_3d(b["polyline"]) for b in items) / 1000.0, 3)})
    panels = [q for s in sides_out for q in s["infill"]["panels"]]
    if panels:
        bom.append({"part": "{} panel".format(panels[0]["kind"]), "count": len(panels),
                    "area_m2": round(sum(q["area_m2"] for q in panels), 3),
                    "thickness_mm": panels[0]["thickness"]})
    clamps = sum(len(s["infill"]["clamps"]) for s in sides_out)
    if clamps:
        bom.append({"part": "glass clamp", "count": clamps})
    return bom
