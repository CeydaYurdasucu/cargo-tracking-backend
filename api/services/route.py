# api/services/route.py

def build_route_with_coords(stations):
    """
    stations: List[Station]
    """
    route = []

    for s in stations:
        route.append({
            "name": s.name,
            "lat": float(s.latitude),
            "lon": float(s.longitude),
        })

    return route
