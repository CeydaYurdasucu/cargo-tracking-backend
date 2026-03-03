from django.db import transaction
from django.conf import settings

from api.models import (
    Cargo,
    Vehicle,
    CargoAssignment,
    OptimizationRun,
    VehicleRoute
)

from api.services.route_ordering import (
    order_stations_nearest,
    build_route_with_coords
)

from api.services.osrm import osrm_route


def _best_fit_vehicle(weight: float, remaining: dict):
    """
    Best-Fit:
    Kargo sığan araçlar içinden,
    yerleştirdikten sonra EN AZ boşluk kalanı seç.
    """
    candidates = [
        (rem - weight, v)
        for v, rem in remaining.items()
        if rem >= weight
    ]

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def assign_cargo_to_vehicles(problem_type="unlimited", created_by=None):
    """
    UNLIMITED PROBLEM – FINAL

    - Sabit araçlar: 500 / 750 / 1000 (ücretsiz)
    - Kiralık araç: SADECE 500 kg, maliyet = 200
    - Kargolar BÖLÜNEBİLİR
    - Amaç: minimum kiralık araç sayısı
    - Mesafe: OSRM (gerçek yol)
    """

    # --------------------
    # BEKLEYEN KARGOLAR
    # --------------------
    pending_cargos = list(
        Cargo.objects
        .filter(status="pending")
        .order_by("-weight")  # ağırdan başla
    )

    if not pending_cargos:
        return {"error": "Bekleyen kargo yok"}

    # --------------------
    # SABİT ARAÇLAR
    # --------------------
    owned_vehicles = list(
        Vehicle.objects.filter(
            is_active=True,
            is_rented=False
        ).order_by("-max_weight")
    )

    remaining = {v: float(v.max_weight) for v in owned_vehicles}
    used_vehicles = set()

    RENTED_CAPACITY = 500
    RENTED_COST = 200
    KM_COST = getattr(settings, "KM_COST", 1)

    with transaction.atomic():

        # --------------------
        # OPTIMIZATION RUN
        # --------------------
        run = OptimizationRun.objects.create(
            problem_type="unlimited",
            vehicles_used=0,
            total_weight=0,
            total_distance=0,
            total_cost=0,
            created_by=created_by
        )

        rented_counter = 0

        # --------------------
        # KARGO ATAMA
        # --------------------
        for cargo in pending_cargos:
            remaining_weight = float(cargo.weight)

            while remaining_weight > 0:
                vehicle = _best_fit_vehicle(
                    remaining_weight,
                    remaining
                )

                if not vehicle:
                    rented_counter += 1
                    vehicle = Vehicle.objects.create(
                        name=f"Rented-{run.id}-{rented_counter}",
                        max_weight=RENTED_CAPACITY,
                        is_rented=True,
                        rental_cost=RENTED_COST,
                        is_active=True
                    )
                    remaining[vehicle] = RENTED_CAPACITY

                load = min(
                    remaining_weight,
                    remaining[vehicle]
                )

                CargoAssignment.objects.create(
                    cargo=cargo,
                    vehicle=vehicle,
                    optimization_run=run,
                    loaded_weight=load
                )

                remaining[vehicle] -= load
                remaining_weight -= load
                used_vehicles.add(vehicle)

            cargo.status = "assigned"
            cargo.save(update_fields=["status"])

        # --------------------
        # RUN ÖZET
        # --------------------
        run.vehicles_used = len(used_vehicles)
        run.total_weight = sum(
            a.loaded_weight
            for a in CargoAssignment.objects.filter(
                optimization_run=run
            )
        )
        run.save(update_fields=["vehicles_used", "total_weight"])

        # --------------------
        # ROTALAR (OSRM)
        # --------------------
        total_distance = 0.0
        total_cost = 0.0

        for v in used_vehicles:
            assignments = (
                CargoAssignment.objects
                .filter(vehicle=v, optimization_run=run)
                .select_related("cargo__station")
            )

            if not assignments.exists():
                continue

            stations = list({a.cargo.station for a in assignments})
            ordered = order_stations_nearest(stations)
            route = build_route_with_coords(ordered)

            if len(route) < 2:
                continue

            v_distance = 0.0
            full_geometry = []

            for i in range(len(route) - 1):
                res = osrm_route(
                    route[i]["lat"], route[i]["lon"],
                    route[i + 1]["lat"], route[i + 1]["lon"]
                )

                v_distance += res["distance_km"]

                coords = res["geometry"]
                if full_geometry:
                    coords = coords[1:]  # overlap önle

                full_geometry.extend(coords)

            v_cost = v_distance * KM_COST
            if v.is_rented:
                v_cost += RENTED_COST

            VehicleRoute.objects.create(
                optimization_run=run,
                vehicle=v,
                stations=[p["name"] for p in route],
                path=[
                    {"lat": lat, "lon": lon}
                    for lon, lat in full_geometry
                ],
                total_distance=round(v_distance, 2),
                total_cost=round(v_cost, 2)
            )

            total_distance += v_distance
            total_cost += v_cost

        run.total_distance = round(total_distance, 2)
        run.total_cost = round(total_cost, 2)
        run.save(update_fields=["total_distance", "total_cost"])

    return {
        "optimization_id": run.id,
        "problem_type": "unlimited",
        "vehicles_used": run.vehicles_used,
        "total_weight": run.total_weight,
        "total_distance": run.total_distance,
        "total_cost": run.total_cost,
    }
