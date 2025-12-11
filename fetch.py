import math
import requests
from dataclasses import dataclass, field
from typing import List

# --------------------------- CONFIG ---------------------------------

start = (49.7251436, 11.8592547)    # south, west
end   = (50.4799014, 12.9914544)    # north, east

plants = [(50.0832989, 12.4063761)]

lat0 = (start[0] + end[0]) / 2
lon0 = (start[1] + end[1]) / 2

R = 6371000
SCALE = 0.001   # projection scale
zoneRange = 5000 / (R * SCALE)

# --------------------------- HELPERS ---------------------------------

def project(lat, lon):
    """Project (lat,lon) into local XY SVG space."""
    x = (lon - lon0) * math.cos(math.radians(lat0)) * R * SCALE
    y = (lat - lat0) * R * -1 * SCALE
    return round(x, 3), round(y, 3)


def distanceToNearest(lat1, lon1):
    """Distance to nearest plant in projected SVG space."""
    px, py = project(lat1, lon1)
    nearest = math.inf

    for plat, plon in plants:
        ppx, ppy = project(plat, plon)
        dist = math.hypot(px - ppx, py - ppy)
        nearest = min(nearest, dist)

    return nearest



# --------------------------- DATA STRUCTS -----------------------------

@dataclass
class Road:
    start: tuple = None
    end: tuple = None
    thickness: float = 1.0
    nodes: List[tuple] = field(default_factory=list)
    color: str = "black"

# --------------------------- ROAD WIDTH ------------------------------

def set_road_width(elem) -> float:
    """Return road stroke width based on highway tag."""
    h = elem["tags"]["highway"]
    return {
        "motorway": 6.2,
        "trunk": 5.7,
        "primary": 5.7,
        "secondary": 3.75,
        "tertiary": 3,
        "unclassified": 0,
        "residential": 0,
    }.get(h, 0)

# --------------------------- FETCH ALL -------------------------------

def fetchAll(s, w, n, e):
    """Single Overpass request for everything."""
    query = f"""
    [out:json][timeout:60];
    (
        way["highway"]({s},{w},{n},{e});
        way["railway"~"rail"]({s},{w},{n},{e});
        way["waterway"]({s},{w},{n},{e});
        way["waterway"~"river|rapids|dam|security_lock"]({s},{w},{n},{e});
        way["water"~"lake|oxbow|basin|canal|harbour"]({s},{w},{n},{e});
        way["landuse"~"residential|industrial|education"]({s},{w},{n},{e});
        relation["landuse"="residential"]["type"="multipolygon"]({s},{w},{n},{e});
        node["place"~"city|town|village|hamlet|isolated_dwelling|allotments|borough|suburb|quarter"]({s},{w},{n},{e});
    );
    out geom;
    """

    r = requests.get("https://overpass-api.de/api/interpreter", params={"data": query})
    r.raise_for_status(),
    print(r.status_code)

    results = {
        "highways": [],
        "railways": [],
        "rivers": [],
        "lakes": [],
        "landuse": [],
        "cities": []
    }

    for elem in r.json().get("elements", []):
        if "tags" not in elem:
            continue

        tags = elem["tags"]

        # Optional: project geometry immediately
        if "geometry" in elem:
            elem["projected"] = [project(pt["lat"], pt["lon"])
                                 for pt in elem["geometry"]]

        # Categorize
        if "highway" in tags:
            results["highways"].append(elem)
        elif "railway" in tags:
            results["railways"].append(elem)
        elif "waterway" in tags:
            results["rivers"].append(elem)
        elif tags.get("natural") == "water" or "water" in tags:
            results["lakes"].append(elem)
        elif "landuse" in tags:
            # Simple polygon (way)
            if elem["type"] == "way":
                elem["projected"] = [project(pt["lat"], pt["lon"]) for pt in elem["geometry"]]
                results["landuse"].append(elem)

            # Multipolygon (relation)

            elif elem["type"] == "relation" and "members" in elem:
                rings = []
                for mem in elem["members"]:
                    if mem["role"] in ("outer", "inner") and "geometry" in mem:
                        ring = [project(n["lat"], n["lon"]) for n in mem["geometry"]]
                        # Close ring if needed
                        if ring[0] != ring[-1]:
                            ring.append(ring[0])
                        rings.append(ring)
                elem["polyrings"] = rings
                results["landuse"].append(elem)

        elif "place" in tags:
            results["cities"].append(elem)

    return results


# --------------------------- ROAD MERGING ----------------------------

def merge_road_into_list(new_road, road_list):
    """Attempt to merge geometrically adjacent roads."""
    for existing in road_list:
        if existing.thickness != new_road.thickness:
            continue

        if new_road.start == existing.end:
            existing.nodes.extend(new_road.nodes)
            existing.end = new_road.end
            return True

        if new_road.end == existing.start:
            existing.nodes = new_road.nodes + existing.nodes
            existing.start = new_road.start
            return True

        if new_road.end == existing.end:
            rev = list(reversed(new_road.nodes))
            existing.nodes.extend(rev)
            existing.end = new_road.start
            return True

        if new_road.start == existing.start:
            rev = list(reversed(new_road.nodes))
            existing.nodes = rev + existing.nodes
            existing.start = new_road.end
            return True

    return False


def processRoads(highway_elements):
    """Convert OSM highway data into merged road structures."""
    black, white = [], []

    for elem in highway_elements:
        base = set_road_width(elem)
        if base == 0:
            continue

        geom = elem["projected"]
        start, end = geom[0], geom[-1]

        r_black = Road(start, end, base, geom.copy(), "black")
        r_white = Road(start, end, max(base - 1, 0.7), geom.copy(), "white")

        if not merge_road_into_list(r_black, black):
            black.append(r_black)

        if not merge_road_into_list(r_white, white):
            white.append(r_white)

    return black + white


# --------------------------- SVG WRITING ------------------------------

def write(path):
    """Append raw SVG string."""
    with open("curve.svg", "a", encoding="utf-8") as f:
        f.write(path)


def initializeSVG():
    with open("curve.svg", "w", encoding="utf-8") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-1000 -1000 2000 2000">')

def closeSVG():
    write('</svg>')


def roadsToSVG(roads):
    for r in roads:
        if not r.nodes:
            continue
        path = "M " + " ".join(f"{x} {y}" for x, y in r.nodes)
        write(f'<path d="{path}" stroke="{r.color}" stroke-width="{r.thickness}" fill="none" />')


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Function to get distance to nearest plant
def distance_to_nearest(lat, lon):
    return min(haversine(lat, lon, p_lat, p_lon) for p_lat, p_lon in plants)

def citiesToSVG(cities, color1, color2):
    for elem in cities:
        name = elem["tags"].get("name", "")
        px, py = project(elem["lat"], elem["lon"])
        dist = distance_to_nearest(elem["lat"], elem["lon"])

        # Determine color based on distance bands of 5 km
        band = int(dist // 5)  # integer division
        color = color1 if band % 2 == 0 else color2

        write(f'<rect width="18.6" height="18.6" x="{px}" y="{py}" fill="{color}" />')
        write(f'<text x="{px}" y="{py - 12}" fill="black" font-size="16">{name}</text>')


def pathToSVG(lines, stroke, width, dash=None):
    for line in lines:
        if not line:
            continue
        path = "M " + " ".join(f"{x} {y}" for x, y in line)
        dashattr = f' stroke-dasharray="{dash}"' if dash else ""
        write(f'<path d="{path}" stroke="{stroke}" stroke-width="{width}" fill="none"{dashattr} />')


def polygonsToSVG(polys, color):
    for poly in polys:
        if not poly:
            continue
        pts = " ".join(f"{x},{y}" for x, y in poly)
        write(f'<polygon points="{pts}" fill="{color}" stroke="{color}" stroke-width="2" />')


# --------------------------- RUN ------------------------------

data = fetchAll(start[0], start[1], end[0], end[1])

roads     = processRoads(data["highways"])
railways  = [elem["projected"] for elem in data["railways"]]
rivers    = [elem["projected"] for elem in data["rivers"]]
lakes     = [elem["projected"] for elem in data["lakes"]]
cities    = data["cities"]

initializeSVG()


#pathToSVG(rivers, "blue", 3)
#polygonsToSVG(lakes, "blue")


# Collect landuse polygons (both ways and multipolygons)
landuse = []
for elem in data["landuse"]:
    if "projected" in elem:
        ring = elem["projected"]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        landuse.append(ring)
    elif "polyrings" in elem:
        for ring in elem["polyrings"]:
            landuse.append(ring)

polygonsToSVG(landuse, "gray")
roadsToSVG(roads)
citiesToSVG(cities, "green", "yellow")

# Railways (multi-stroke style)
pathToSVG(railways, "black", 3.2)
pathToSVG(railways, "white", 3.0)
pathToSVG(railways, "black", 3.0, dash="10,10")

closeSVG()
