# Django & DRF
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

# Django utils
from django.db.models import Sum
from django.utils import timezone

# Models
from api.models import (
    Cargo,
    Station,
    Vehicle,
    CargoAssignment,
)

# Services
from api.services.assignment import assign_cargo_to_vehicles
from django.conf import settings
from api.services.distance import calculate_distance_km

from api.services.assignment_limited import assign_cargo_limited
from .models import OptimizationRun
from django.shortcuts import get_object_or_404
from api.models import VehicleRoute
from api.services.osrm import osrm_route

from django.db.models import Sum, Count, Q



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_auth(request):
    return Response({
        "message": "Giriş başarılı",
        "username": request.user.username,
        "role": request.user.role,
    })


@api_view(['GET'])
def station_list(request):
    stations = Station.objects.filter(is_active=True)
    data = [
        {
            "id": s.id,
            "name": s.name,
            "latitude": s.latitude,
            "longitude": s.longitude,
        }
        for s in stations
    ]
    return Response(data)



@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_station(request, station_id):
    """
    Admin: İstasyon silme endpoint'i
    """

    try:
        station = Station.objects.get(id=station_id)
    except Station.DoesNotExist:
        return Response(
            {"detail": "İstasyon bulunamadı"},
            status=status.HTTP_404_NOT_FOUND
        )

    # (Opsiyonel) Ana merkez silinmesin
    if "KOU" in station.name or "İzmit" in station.name:
        return Response(
            {"detail": "Ana istasyon silinemez"},
            status=status.HTTP_400_BAD_REQUEST
        )

    station.delete()
    return Response(
        {"detail": "İstasyon silindi"},
        status=status.HTTP_204_NO_CONTENT
    )

@api_view(['POST'])
@permission_classes([IsAuthenticated]) # Sadece giriş yapmış kullanıcılar (Admin) ekleyebilsin
def create_station(request):
    """
    Yeni istasyon oluşturma endpoint'i
    """
    name = request.data.get("name")
    latitude = request.data.get("latitude")
    longitude = request.data.get("longitude")

    # --- VALIDATION ---
    if not name or latitude is None or longitude is None:
        return Response(
            {"error": "name, latitude ve longitude alanları zorunludur"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # İstasyon zaten var mı kontrolü (Opsiyonel)
    if Station.objects.filter(name=name).exists():
        return Response(
            {"error": "Bu isimde bir istasyon zaten mevcut"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # İstasyonu oluştur
    station = Station.objects.create(
        name=name,
        latitude=latitude,
        longitude=longitude,
        is_active=True
    )

    return Response(
        {
            "id": station.id,
            "name": station.name,
            "latitude": station.latitude,
            "longitude": station.longitude,
            "message": "İstasyon başarıyla oluşturuldu"
        },
        status=status.HTTP_201_CREATED
    )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_cargo(request):
    """
    Kullanıcı kargo gönderme endpoint'i
    """
    user = request.user

    station_id = request.data.get("station_id")
    quantity = request.data.get("quantity")
    weight = request.data.get("weight")

    # --- VALIDATION ---
    if not station_id or not quantity or not weight:
        return Response(
            {"error": "station_id, quantity ve weight zorunludur"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        station = Station.objects.get(id=station_id, is_active=True)
    except Station.DoesNotExist:
        return Response(
            {"error": "Geçersiz istasyon"},
            status=status.HTTP_404_NOT_FOUND
        )

    cargo = Cargo.objects.create(
        station=station,
        user=user,
        quantity=quantity,
        weight=weight,
        status="pending"
    )

    return Response(
        {
            "message": "Kargo başarıyla oluşturuldu",
            "cargo_id": cargo.id,
            "station": station.name,
            "quantity": cargo.quantity,
            "weight": cargo.weight,
            "status": cargo.status,
        },
        status=status.HTTP_201_CREATED
    )




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_cargo_summary(request):
    """
    Admin için istasyon bazlı kargo özeti
    (sadece pending kargolar)
    """

    cargos = (
        Cargo.objects
        .filter(status="pending")
        .values("station__id", "station__name")
        .annotate(
            total_quantity=Sum("quantity"),
            total_weight=Sum("weight")
        )
        .order_by("station__name")
    )

    data = [
        {
            "station_id": c["station__id"],
            "station": c["station__name"],
            "total_quantity": c["total_quantity"] or 0,
            "total_weight": c["total_weight"] or 0,
        }
        for c in cargos
    ]

    return Response(data)





@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_cargos(request):
    cargos = Cargo.objects.filter(user=request.user).prefetch_related(
        "assignments__optimization_run"
    )

    data = []

    for cargo in cargos:
        assignment = cargo.assignments.filter(
            optimization_run__isnull=False
        ).order_by("-optimization_run__created_at").first()

        route = None

        if assignment:
            route_obj = VehicleRoute.objects.filter(
                vehicle=assignment.vehicle,
                optimization_run=assignment.optimization_run
            ).first()

            route = route_obj.path if route_obj else []

        data.append({
            "id": cargo.id,
            "station": cargo.station.name,
            "status": cargo.status,
            "quantity": cargo.quantity,
            "weight": cargo.weight,
            "vehicle": assignment.vehicle.name if assignment else None,
            "route": route
        })

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vehicle_cargo_list(request, vehicle_id):
    """
    Belirli bir araca atanmış kargoların listesini döner
    (admin için).
    """

    assignments = (
        CargoAssignment.objects
        .filter(vehicle_id=vehicle_id)
        .select_related("cargo", "cargo__user")
    )

    data = []

    for a in assignments:
        cargo = a.cargo
        data.append({
            "cargo_id": cargo.id,
            "weight": cargo.weight,
            "status": cargo.status,
            "user": cargo.user.username,
            "assigned_at": a.assigned_at,
        })

    return Response({
        "vehicle_id": vehicle_id,
        "cargo_count": len(data),
        "cargos": data
    })





@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deliver_vehicle_cargos(request, vehicle_id):
    """
    Araca atanmış kargoları teslim eder:
    - Cargo.status -> delivered
    - CargoAssignment.completed_at -> now
    """

    assignments = CargoAssignment.objects.filter(
        vehicle_id=vehicle_id,
        completed_at__isnull=True
    )

    delivered_count = 0

    for assignment in assignments:
        cargo = assignment.cargo
        if cargo.status == "assigned":
            cargo.status = "delivered"
            cargo.save()

            assignment.completed_at = timezone.now()
            assignment.save()

            delivered_count += 1

    return Response({
        "vehicle_id": vehicle_id,
        "delivered_cargo_count": delivered_count
    })



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vehicle_report(request, vehicle_id):
    """
    Araç bazlı kargo raporu
    """

    try:
        vehicle = Vehicle.objects.get(id=vehicle_id)
    except Vehicle.DoesNotExist:
        return Response({"detail": "Araç bulunamadı"}, status=404)

    assignments = (
        CargoAssignment.objects
        .filter(vehicle=vehicle)
        .select_related("cargo__user", "cargo__station")
    )

    total_cargo = assignments.count()

    delivered_count = assignments.filter(
        cargo__status="delivered"
    ).count()

    assigned_count = assignments.filter(
        cargo__status="assigned"
    ).count()

    total_weight = (
        assignments.aggregate(
            total=Sum("cargo__weight")
        )["total"] or 0
    )

    users = list(
        assignments.values(
            "cargo__user__id",
            "cargo__user__username"
        ).distinct()
    )

    # --- MESAFE & MALİYET HESABI ---

    stations = {
        a.cargo.station
        for a in assignments
    }

    total_distance = 0


    for station in stations:
        result = osrm_route(
            station.latitude,
            station.longitude,
            settings.KOCAELI_UNI_LAT,
            settings.KOCAELI_UNI_LON
        )
        total_distance += result["distance_km"]


    rental_cost = (
        settings.RENTED_VEHICLE_COST
        if vehicle.is_rented
        else 0
    )

    total_cost = total_distance * settings.KM_COST + rental_cost

    return Response({
        "vehicle": vehicle.name,
        "total_cargo": total_cargo,
        "delivered": delivered_count,
        "assigned": assigned_count,
        "total_weight": total_weight,
        "users": users,
        "distance_km": round(total_distance, 2),
        "rental_cost": rental_cost,
        "total_cost": round(total_cost, 2),
    })




from django.db.models import Sum, Count, Q, Avg


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard(request):
    """
    Sistem genel durumu ve Analitik veriler (Admin Dashboard)
    """

    
    cargo_stats = Cargo.objects.aggregate(
        total=Count('id'),
        delivered=Count('id', filter=Q(status="delivered")),
        assigned=Count('id', filter=Q(status="assigned")),
        pending=Count('id', filter=Q(status="pending")),
        total_weight=Sum("weight")
    )

    
    total_system_cost = OptimizationRun.objects.aggregate(
        all_time_cost=Sum("total_cost")
    )["all_time_cost"] or 0

  
    last_run = OptimizationRun.objects.order_by("-created_at").first()
    last_optimization = None
    vehicles_data = []

    if last_run:
        last_optimization = {
            "id": last_run.id,
            "date": last_run.created_at.strftime("%d.%m.%Y %H:%M"),
            "problem_type": last_run.get_problem_type_display(),
            "vehicles_used": last_run.vehicles_used,
            "total_distance": float(last_run.total_distance),
            "total_weight": float(last_run.total_weight),
            "total_cost": float(last_run.total_cost),
        }

       
        routes = VehicleRoute.objects.filter(optimization_run=last_run).select_related("vehicle")
        for r in routes:
            vehicles_data.append({
                "vehicle": r.vehicle.name,
                "total_cargo": CargoAssignment.objects.filter(optimization_run=last_run, vehicle=r.vehicle).count(),
                "total_weight": float(r.total_weight) if hasattr(r, 'total_weight') else 0.0,
                "distance_km": float(r.total_distance),
                "total_cost": float(r.total_cost),
            })

  

   
    history_qs = OptimizationRun.objects.order_by("-created_at")[:10]
    history_chart = [
        {
            "id": run.id,
            "date": run.created_at.strftime("%d/%m"),
            "cost": float(run.total_cost),
            "distance": float(run.total_distance)
        }
        for run in reversed(history_qs)
    ]

    # B. İstasyon (İlçe) Bazlı Yük Dağılımı (Pasta Grafiği Verisi)
    # Şartnamede belirtilen ilçelerin yoğunluğunu ölçer 
    district_distribution = Cargo.objects.values("station__name").annotate(
        weight=Sum("weight"),
        count=Count("id")
    ).order_by("-weight")

    # C. Senaryo Karşılaştırması (Sabit vs Sınırsız Araç Verimliliği)
    scenario_comparison = OptimizationRun.objects.values("problem_type").annotate(
        avg_cost=Avg("total_cost"),
        avg_distance=Avg("total_distance"),
        count=Count("id")
    )

    return Response({
        "cargo_summary": {
            "total": cargo_stats["total"] or 0,
            "delivered": cargo_stats["delivered"] or 0,
            "assigned": cargo_stats["assigned"] or 0,
            "pending": cargo_stats["pending"] or 0,
            "total_weight": float(cargo_stats["total_weight"] or 0),
        },
        "vehicles": vehicles_data,
        "system_total_cost": round(float(total_system_cost), 2),
        "last_optimization": last_optimization,
        # Frontend'de grafiklerde kullanılacak veriler
        "analytics": {
            "history_chart": history_chart,
            "districts": list(district_distribution),
            "scenarios": list(scenario_comparison)
        }
    })

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def assign_unlimited_view(request):
    result = assign_cargo_to_vehicles(
        problem_type="unlimited",
        created_by=request.user
    )
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def assign_fixed_view(request):
    objective = request.data.get("objective", "max_weight")

    result = assign_cargo_limited(
        objective=objective,
        created_by=request.user
    )
    return Response(result)



from django.utils.dateparse import parse_date

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def optimization_run_list(request):
    """
    TripsHistory ana ekranı için geçmiş seferleri listeler
    (tarih aralığı destekli)
    """

    qs = OptimizationRun.objects.all().order_by("-created_at")

    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if date_from:
        qs = qs.filter(created_at__date__gte=parse_date(date_from))

    if date_to:
        qs = qs.filter(created_at__date__lte=parse_date(date_to))

    data = [
        {
            "id": run.id,
            "date": run.created_at.strftime("%Y-%m-%d %H:%M"),
            "problem_type": run.get_problem_type_display(),
            "vehicles_used": run.vehicles_used,
            "total_weight": run.total_weight,
            "total_distance": run.total_distance,
            "total_cost": run.total_cost,
        }
        for run in qs
    ]

    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def optimization_run_detail(request, run_id):
    run = get_object_or_404(OptimizationRun, id=run_id)

    assignments = (
        CargoAssignment.objects
        .filter(optimization_run=run)
        .select_related("vehicle", "cargo__station", "cargo__user")
        .order_by("vehicle_id", "id")
    )

    routes = {
        r.vehicle_id: r
        for r in VehicleRoute.objects.filter(optimization_run=run)
    }

    vehicles_map = {}

    for a in assignments:
        v = a.vehicle

        if v.id not in vehicles_map:
            r = routes.get(v.id)

            stations = []
            if r and r.stations:
                for s in r.stations:
                    st = Station.objects.filter(name=s).first()
                    if not st:
                        continue

                    stations.append({
                        "lat": float(st.latitude),
                        "lon": float(st.longitude),
                        "name": st.name
                    })

            vehicles_map[v.id] = {
                "id": v.id,
                "name": v.name,
                "isRented": v.is_rented,
                "capacity": float(v.max_weight),

                "total_distance": float(r.total_distance) if r else 0.0,
                "total_cost": float(r.total_cost) if r else 0.0,

                "route": (r.path if r else []),      # OSRM polyline
                "stations": stations,                # ✅ sadece marker noktaları

                "cargos": []
            }

        vehicles_map[v.id]["cargos"].append({
            "id": str(a.cargo.id),
            "owner": a.cargo.user.username,
            "station": a.cargo.station.name,
           # "weight": float(getattr(a, "loaded_weight", a.cargo.weight)),
           "weight": float(a.cargo.weight if a.cargo.weight else 0),
            "cargo_weight": float(a.cargo.weight),
        })

    return Response({
        "id": str(run.id),
        "date": run.created_at.strftime("%d.%m.%Y %H:%M"),
        "problem_type": run.get_problem_type_display(),
        "total_cost": float(run.total_cost),
        "total_distance": float(run.total_distance),
        "total_weight": float(run.total_weight),
        "vehicles": list(vehicles_map.values())
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def last_optimization_run(request):
    """
    Dashboard için SON çalıştırılan optimization run
    """
    run = OptimizationRun.objects.order_by("-created_at").first()

    if not run:
        return Response(None)

    return Response({
        "id": run.id,
        "date": run.created_at.strftime("%d.%m.%Y %H:%M"),
        "problem_type": run.get_problem_type_display(),
        "vehicles_used": run.vehicles_used,
        "total_weight": run.total_weight,
        "total_distance": run.total_distance,
        "total_cost": run.total_cost,
    })
