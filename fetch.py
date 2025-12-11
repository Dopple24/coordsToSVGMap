import math
import requests
from dataclasses import dataclass, field
from typing import List

start = (49.7251436, 11.9092547) #south, west
end = (50.4799014, 12.9414544) #north, east

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

def set_road_width(obj) -> float:
    match obj["tags"]["highway"]:
        case "motorway":     return 6.2
        case "trunk":        return 5.7
        case "primary":      return 5.7
        case "secondary":    return 3.75
        case "tertiary":     return 3
        case "unclassified": return 1
        case "residential":  return 1
    return 0

# --------------------------- FETCH -------------------------------------

def fetchAll(s, w, n, e):
    query = f"""
    [out:json][timeout:60];
    (
      way["highway"]({s},{w},{n},{e});
      way["railway"]({s},{w},{n},{e});
      way["waterway"]({s},{w},{n},{e});
      way["natural"="water"]({s},{w},{n},{e});
      way["water"]({s},{w},{n},{e});
      way["landuse"]({s},{w},{n},{e});
      node["place"]({s},{w},{n},{e});
    );
    out geom;
    """

    r = requests.get("https://overpass-api.de/api/interpreter", params={"data": query})
    r.raise_for_status()

    elements = r.json().get("elements", [])
    if not isinstance(elements, list):
        return {
            "highways": [],
            "railways": [],
            "rivers": [],
            "lakes": [],
            "landuse": [],
            "cities": []
        }

    highways = []
    railways = []
    rivers = []
    lakes = []
    landuse = []
    cities = []

    for elem in elements:

        # ---- Skip broken elements ----
        if not isinstance(elem, dict):
            continue
        if "tags" not in elem:
            continue

        tags = elem["tags"]

        # ---- If geometry exists, project it ----
        if "geometry" in elem:
            projected = []
            for pt in elem["geometry"]:
                if "lat" not in pt or "lon" not in pt:
                    continue
                lat, lon = pt["lat"], pt["lon"]
                x = (lon - lon0) * math.cos(math.radians(lat0)) * R * SCALE
                y = (lat - lat0) * R * -1 * SCALE
                projected.append((round(x, 3), round(y, 3)))

            elem["projected"] = projected

        # ---- Categorize ----
        if "highway" in tags:
            highways.append(elem)

        elif "railway" in tags:
            railways.append(elem)

        elif "waterway" in tags:
            rivers.append(elem)

        elif tags.get("natural") == "water" or "water" in tags:
            lakes.append(elem)

        elif "landuse" in tags:
            landuse.append(elem)

        elif "place" in tags:
            cities.append(elem)

    return {
        "highways": highways,
        "railways": railways,
        "rivers": rivers,
        "lakes": lakes,
        "landuse": landuse,
        "cities": cities
    }


# ------------------------ FETCH RAILROAD DATA --------------------------

def getRailways(south, west, north, east):
    query = f"""
    [out:json][timeout:25];
    way["railway"~"rail"]({south},{west},{north},{east});
    out geom;
    """
    response = requests.get("https://overpass-api.de/api/interpreter", params={"data": query})
    print(response.status_code)

    elements = response.json().get("elements", [])

    rails = []
    for element in elements:
        projected_nodes = []
        for pt in element["geometry"]:
            lat, lon = pt["lat"], pt["lon"]
            x = (lon - lon0) * math.cos(math.radians(lat0)) * R * SCALE
            y = (lat - lat0) * R * -1 * SCALE
            projected_nodes.append((round(x,3), round(y,3)))
        rails.append(projected_nodes)
    return rails

# -------------------------- FETCH RIVER DATA ---------------------------

def getRivers(south, west, north, east):
    query = f"""
    [out:json][timeout:25];
    way["waterway"~"river|rapids|dam|security_lock"]({south},{west},{north},{east});
    out geom;
    """
    response = requests.get("https://overpass-api.de/api/interpreter", params={"data": query})
    print(response.status_code)

    elements = response.json().get("elements", [])

    rivers = []
    for element in elements:
        projected_nodes = []
        for pt in element["geometry"]:
            lat, lon = pt["lat"], pt["lon"]
            x = (lon - lon0) * math.cos(math.radians(lat0)) * R * SCALE
            y = (lat - lat0) * R * -1 * SCALE
            projected_nodes.append((round(x,3), round(y,3)))
        rivers.append(projected_nodes)
    return rivers

# ------------------- Fetch lakes/ponds/reservoirs -------------------

def getLakes(south, west, north, east):
    query = f"""
    [out:json][timeout:25];
    way["water"~"lake|oxbow|basin|canal|harbour"]({south},{west},{north},{east});
    out geom;
    """
    response = requests.get("https://overpass-api.de/api/interpreter", params={"data": query})
    print(response.status_code)

    elements = response.json().get("elements", [])

    lakes = []
    for element in elements:
        projected_nodes = []
        for pt in element["geometry"]:
            lat, lon = pt["lat"], pt["lon"]
            x = (lon - lon0) * math.cos(math.radians(lat0)) * R * SCALE
            y = (lat - lat0) * R * -1 * SCALE
            projected_nodes.append((round(x,3), round(y,3)))
        lakes.append(projected_nodes)
    return lakes

# ------------------- Fetch residential areas -------------------

def getResAreas(south, west, north, east):
    query = f"""
    [out:json][timeout:25];
    way["landuse"~"residential|industrial|education"]({south},{west},{north},{east});
    out geom;
    """
    response = requests.get("https://overpass-api.de/api/interpreter", params={"data": query})
    print(response.status_code)

    elements = response.json().get("elements", [])

    lakes = []
    for element in elements:
        projected_nodes = []
        for pt in element["geometry"]:
            lat, lon = pt["lat"], pt["lon"]
            x = (lon - lon0) * math.cos(math.radians(lat0)) * R * SCALE
            y = (lat - lat0) * R * -1 * SCALE
            projected_nodes.append((round(x,3), round(y,3)))
        lakes.append(projected_nodes)
    return lakes


# --------------------------- FETCH ROAD DATA ---------------------------

def processRoads(highway_elements):
    black = []
    white = []

    for elem in highway_elements:
        tags = elem["tags"]
        geom = elem["projected"]
        base = set_road_width({"tags": tags})

        if base == 0:
            continue

        start = geom[0]
        end = geom[-1]

        new_black = Road(start=start, end=end, thickness=base,
                         color="black", nodes=geom.copy())
        new_white = Road(start=start, end=end, thickness=max(base - 1, 0.7),
                         color="white", nodes=geom.copy())

        if not merge_road_into_list(new_black, black):
            black.append(new_black)

        if not merge_road_into_list(new_white, white):
            white.append(new_white)

    return black + white


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
    [out:json][timeout:60];
    way["highway"]({south},{west},{north},{east});
    out geom;
    """

    response = requests.get("https://overpass-api.de/api/interpreter",
                             params={"data": query})
    print(response.status_code)

    data = response.json()

    black_roads = []
    white_roads = []

    for element in data["elements"]:
        geom = element["geometry"]
        base = set_road_width(element)
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

def citiesToSVG(cities, filename="curve.svg"):
    with open(filename, "a", encoding="utf-8") as f:
        for elem in cities:
            name = elem["tags"].get("name", "")
            lat = elem["lat"]
            lon = elem["lon"]

            x = (lon - lon0) * math.cos(math.radians(lat0)) * R * SCALE
            y = (lat - lat0) * R * -1 * SCALE

            f.write(
                f'<rect width="18.6" height="18.6" x="{x}" y="{y}" fill="pink" />'
                f'<text x="{x}" y="{y - 12}" fill="black" font-size="16">{name}</text>'
            )
# ------------------- Write rivers as SVG paths -------------------

def riversToSVG(rivers, filename="curve.svg"):
    with open(filename, "a", encoding="utf-8") as f:
        for river in rivers:
            if not river:
                continue
            path_str = f"M {river[0][0]} {river[0][1]} "
            for x, y in river[1:]:
                path_str += f"L {x} {y} "
            f.write(f'<path d="{path_str}" stroke="blue" stroke-width="3" fill="none"/>\n')

# ------------------- Write lakes as SVG polygons -------------------

def lakesToSVG(lakes, filename="curve.svg"):
    with open(filename, "a", encoding="utf-8") as f:
        for lake in lakes:
            if not lake:
                continue
            points_str = " ".join(f"{x},{y}" for x, y in lake)
            f.write(f'<polygon points="{points_str}" fill="blue" stroke="blue" stroke-width="2"/>\n')


def railwaysToSVG(rails, filename="curve.svg"):
    with open(filename, "a", encoding="utf-8") as f:
        for rail in rails:
            if not rail:
                continue
            path_str = f"M {rail[0][0]} {rail[0][1]} "
            for x, y in rail[1:]:
                path_str += f"L {x} {y} "
            f.write(f'<path d="{path_str}" stroke="black" stroke-width="3.2" fill="none" />\n')
            f.write(f'<path d="{path_str}" stroke="white" stroke-width="3" fill="none" />\n')
            f.write(f'<path d="{path_str}" stroke="black" stroke-width="3" fill="none" stroke-dasharray="10,10" />\n')



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
                f'<rect width="18.6" height="18.6" x="{x}" y="{y}" fill="green" />'
                f'<text x="{x}" y="{y - 12}" fill="black" font-size="16">{name}</text>'
            )


# --------------------------- RUN ---------------------------
roads_raw, railways_raw, rivers_raw, lakes_raw, landuse_raw, cities_raw = fetchAll(
    start[0], start[1], end[0], end[1]
)

initializeSVG()

# Roads
roads = processRoads(roads_raw)         # NEW helper (scroll down)
roadsToSVG(roads)

# Cities
citiesToSVG(cities_raw)                 # NEW helper (scroll down)

# Rivers
rivers = [elem["projected"] for elem in rivers_raw]
riversToSVG(rivers)

# Lakes
lakes = [elem["projected"] for elem in lakes_raw]
lakesToSVG(lakes)

# Railways
rails = [elem["projected"] for elem in railways_raw]
railwaysToSVG(rails)



closeSVG()

