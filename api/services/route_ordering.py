from api.services.distance import calculate_distance_km
from django.conf import settings


def order_stations_nearest(stations):
    """
    1) Umuttepe'ye EN UZAK istasyondan başla
    2) Nearest Neighbor ile sırala
    """

    if not stations:
        return []

    # 🔥 en uzak istasyon
    start = max(
        stations,
        key=lambda s: calculate_distance_km(
            s.latitude,
            s.longitude,
            settings.KOCAELI_UNI_LAT,
            settings.KOCAELI_UNI_LON
        )
    )

    ordered = [start]
    remaining = [s for s in stations if s != start]
    current = start

    while remaining:
        nearest = min(
            remaining,
            key=lambda s: calculate_distance_km(
                current.latitude,
                current.longitude,
                s.latitude,
                s.longitude
            )
        )
        ordered.append(nearest)
        remaining.remove(nearest)
        current = nearest

    return ordered


def build_route_with_coords(ordered_stations):
    """
    Frontend için {name, lat, lon} dizisi üretir
    BAŞLANGIÇ: ilk istasyon
    VARIŞ: Umuttepe
    """

    route = []

    for st in ordered_stations:
        route.append({
            "name": st.name,
            "lat": st.latitude,
            "lon": st.longitude,
        })

    # 🔴 sadece VARIŞ
    route.append({
        "name": "Umuttepe",
        "lat": settings.KOCAELI_UNI_LAT,
        "lon": settings.KOCAELI_UNI_LON,
    })

    return route
