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
    candidates = []
    for v, rem in remaining.items():
        if rem >= weight:
            candidates.append((rem - weight, v))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def assign_cargo_limited(objective="max_weight", created_by=None):
    """
    FIXED PROBLEM

    - Sadece OWNED araçlar (kiralık YOK)
    - Best-Fit yerleştirme
    - max_weight  → ağırdan hafife
    - max_count   → hafiften ağıra
    - Gerçek yol ağı: OSRM
    """

    # --------------------
    # ARAÇLAR
    # --------------------
    vehicles = list(
        Vehicle.objects.filter(
            is_active=True,
            is_rented=False
        ).order_by("-max_weight")
    )

    if not vehicles:
        return {"error": "Aktif sabit araç yok"}

    # --------------------
    # KARGOLAR
    # --------------------
    cargos_qs = Cargo.objects.filter(status="pending")

    if objective == "max_count":
        cargos = list(cargos_qs.order_by("weight"))     # hafif → ağır
    else:
        cargos = list(cargos_qs.order_by("-weight"))    # ağır → hafif

    if not cargos:
        return {"error": "Bekleyen kargo yok"}

    remaining = {v: float(v.max_weight) for v in vehicles}
    selected_assignments = []  # (cargo, vehicle)
    unserved = []

    # =========================
    # 1) KARGO YERLEŞTİRME
    # =========================
    for cargo in cargos:
        vehicle = _best_fit_vehicle(float(cargo.weight), remaining)

        if not vehicle:
            unserved.append({
                "cargo_id": cargo.id,
                "station": cargo.station.name,
                "weight": float(cargo.weight),
                "quantity": cargo.quantity,
            })
            continue

        remaining[vehicle] -= float(cargo.weight)
        selected_assignments.append((cargo, vehicle))

    if not selected_assignments:
        return {
            "error": "Hiçbir kargo mevcut araç kapasitelerine sığmadı",
            "unserved": unserved
        }

    used_vehicles = {v for _, v in selected_assignments}

    # =========================
    # 2) RUN + ASSIGNMENT
    # =========================
    with transaction.atomic():

        run = OptimizationRun.objects.create(
            problem_type="fixed",
            vehicles_used=len(used_vehicles),
            total_weight=sum(float(c.weight) for c, _ in selected_assignments),
            total_distance=0,
            total_cost=0,
            created_by=created_by
        )

        for cargo, vehicle in selected_assignments:
            CargoAssignment.objects.create(
                cargo=cargo,
                vehicle=vehicle,
                optimization_run=run
            )
            cargo.status = "assigned"
            cargo.save(update_fields=["status"])

        # =========================
        # 3) ROTALAR + OSRM
        # =========================
        total_distance = 0.0
        total_cost = 0.0
        km_cost = getattr(settings, "KM_COST", 1)

        for vehicle in used_vehicles:

            assignments = (
                CargoAssignment.objects
                .filter(vehicle=vehicle, optimization_run=run)
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

            v_cost = v_distance * km_cost

            VehicleRoute.objects.create(
                optimization_run=run,
                vehicle=vehicle,
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
        "problem_type": "fixed",
        "objective": objective,
        "vehicles_used": run.vehicles_used,
        "total_weight": run.total_weight,
        "total_distance": run.total_distance,
        "total_cost": run.total_cost,
        "unserved": unserved,
    }
