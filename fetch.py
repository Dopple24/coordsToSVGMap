import math
import requests
from dataclasses import dataclass, field
from typing import List

start = (48.8145328, 17.0831953) #south, west
end = (49.2576317, 17.7464947) #north, east

lat0 = (start[0] + end[0]) / 2
lon0 = (start[1] + end[1]) / 2

R = 6371000
SCALE = 0.001

# --------------------------- ROAD STRUCT ---------------------------

@dataclass
class Road:
    start: tuple[float, float] = None
    end: tuple[float, float] = None
    thickness: float = 1.0
    nodes: List[tuple[float, float]] = field(default_factory=list)
    color: str = "black"


# --------------------------- HIGHWAY STROKE ---------------------------

def setStroke(obj) -> float:
    match obj["tags"]["highway"]:
        case "motorway":     return 6.2
        case "trunk":        return 5.7
        case "primary":      return 5.7
        case "secondary":    return 3.75
        case "tertiary":     return 3
        case "unclassified": return 1
        case "residential":  return 1
    return 0


# --------------------------- FETCH ROAD DATA ---------------------------

def merge_road_into_list(new_road, road_list):
    """
    Try merging a new road into road_list.
    Only merge if thickness is identical.
    Returns True if merged, False if it should be appended separately.
    """

    for existing in road_list:

        # IMPORTANT: Only merge if road type is the same
        if existing.thickness != new_road.thickness:
            continue

        # Connect new.start → existing.end
        if new_road.start == existing.end:
            existing.nodes.extend(new_road.nodes)
            existing.end = new_road.end
            return True

        # Connect new.end → existing.start
        if new_road.end == existing.start:
            existing.nodes = new_road.nodes + existing.nodes
            existing.start = new_road.start
            return True

        # Reverse-match new.end → existing.end
        if new_road.end == existing.end:
            rev = list(reversed(new_road.nodes))
            existing.nodes.extend(rev)
            existing.end = new_road.start
            return True

        # Reverse-match new.start → existing.start
        if new_road.start == existing.start:
            rev = list(reversed(new_road.nodes))
            existing.nodes = rev + existing.nodes
            existing.start = new_road.end
            return True

    return False


def getMotorways(south, west, north, east):
    query = f"""
    [out:json][timeout:25];
    way["highway"]({south},{west},{north},{east});
    out geom;
    """

    response = requests.get("https://overpass-api.de/api/interpreter",
                             params={"data": query})
    data = response.json()

    black_roads = []
    white_roads = []

    for element in data["elements"]:
        geom = element["geometry"]
        base = setStroke(element)
        if base == 0:
            continue

        # Compute projected nodes
        projected_nodes = []
        for pt in geom:
            lat, lon = pt["lat"], pt["lon"]
            x = (lon - lon0) * math.cos(math.radians(lat0)) * R * SCALE
            y = (lat - lat0) * R * -1 * SCALE
            projected_nodes.append((round(x, 3), round(y, 3)))

        start = projected_nodes[0]
        end   = projected_nodes[-1]

        # Create black and white road objects
        new_black = Road(start=start, end=end, thickness=base, color="black",
                         nodes=projected_nodes.copy())
        new_white = Road(start=start, end=end, thickness=max(base - 1, 0.7), color="white",
                         nodes=projected_nodes.copy())

        # Try merge black
        if not merge_road_into_list(new_black, black_roads):
            black_roads.append(new_black)

        # Try merge white
        if not merge_road_into_list(new_white, white_roads):
            white_roads.append(new_white)

    # Correct drawing order: black → white
    return black_roads + white_roads



# --------------------------- SVG OUTPUT ---------------------------
def initializeSVG(filename="curve.svg"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-1000 -1000 2000 2000">')

def closeSVG(filename="curve.svg"):
    with open(filename, "a", encoding="utf-8") as f:
        f.write('</svg>')

def roadsToSVG(roads, filename="curve.svg"):
    with open(filename, "a", encoding="utf-8") as f:

        for road in roads:
            if not road.nodes:
                continue

            path_str = f"M {road.nodes[0][0]} {road.nodes[0][1]} "
            for x, y in road.nodes[1:]:
                path_str += f"L {x} {y} "

            f.write(
                f'<path d="{path_str}" stroke="{road.color}" '
                f'stroke-width="{road.thickness}" fill="none" />'
            )

# --------------------------- CITIES ---------------------------

def getCities(south, west, north, east):
    query = f"""
    [out:json][timeout:25];
    (
      node["place"="city"]({south},{west},{north},{east});
      node["place"="town"]({south},{west},{north},{east});
      node["place"="village"]({south},{west},{north},{east});
    );
    out body;
    """

    response = requests.get("https://overpass-api.de/api/interpreter",
                            params={"data": query})
    data = response.json()

    with open("curve.svg", "a", encoding="utf-8") as f:
        for element in data["elements"]:
            name = element["tags"].get("name")
            lat = element["lat"]
            lon = element["lon"]

            x = (lon - lon0) * math.cos(math.radians(lat0)) * R * SCALE
            y = (lat - lat0) * R * -1 * SCALE

            f.write(
                f'<rect width="18.6" height="18.6" x="{x}" y="{y}" fill="blue" />'
                f'<text x="{x}" y="{y - 12}" fill="black" font-size="16">{name}</text>'
            )


# --------------------------- RUN ---------------------------

initializeSVG()
roads = getMotorways(start[0], start[1], end[0], end[1])
roadsToSVG(roads)
getCities(start[0], start[1], end[0], end[1])
closeSVG()

