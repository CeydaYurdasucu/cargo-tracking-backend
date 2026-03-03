import requests

OSRM_URL = "https://router.project-osrm.org"

def osrm_route(from_lat, from_lon, to_lat, to_lon):
    """
    OSRM'den gerçek yol mesafesi + geometry alır
    """
    url = (
        f"{OSRM_URL}/route/v1/driving/"
        f"{from_lon},{from_lat};{to_lon},{to_lat}"
        "?overview=full&geometries=geojson"
    )

    res = requests.get(url, timeout=10)
    res.raise_for_status()

    data = res.json()
    route = data["routes"][0]

    return {
        "distance_km": route["distance"] / 1000,   # metre → km
        "duration_sec": route["duration"],
        "geometry": route["geometry"]["coordinates"]  # frontend için
    }

def osrm_table(sources, destinations):
    """
    OSRM'den gerçek yol mesafesi matrisi alır
    """
    def format_coords(coords):
        return ";".join([f"{lon},{lat}" for lat, lon in coords])

    url = (
        f"{OSRM_URL}/table/v1/driving/"
        f"{format_coords(sources)};"
        f"{format_coords(destinations)}"
        "?annotations=distance,duration"
    )

    res = requests.get(url, timeout=10)
    res.raise_for_status()

    data = res.json()

    return {
        "distances_km": [
            [dist / 1000 if dist is not None else None for dist in row]
            for row in data["distances"]
        ],
        "durations_sec": data["durations"]
    }