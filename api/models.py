from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('user', 'User'),
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='user'
    )

    def __str__(self):
        return f"{self.username} ({self.role})"

class Station(models.Model):
    name = models.CharField(max_length=100, unique=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name



class Cargo(models.Model):
    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name="cargoes"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cargoes"
    )

    quantity = models.PositiveIntegerField()
    weight = models.FloatField(help_text="Toplam ağırlık (kg)")

    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("assigned", "Assigned"),
            ("delivered", "Delivered"),
        ],
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.station.name} - {self.weight}kg"


class Vehicle(models.Model):
    name = models.CharField(max_length=50, unique=True)

    max_weight = models.FloatField(
        help_text="Araç başına maksimum taşıma kapasitesi (kg)"
    )

    is_rented = models.BooleanField(
        default=False,
        help_text="Kiralık mı?"
    )

    rental_cost = models.FloatField(
        default=0,
        help_text="Araç kiralama maliyeti"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.max_weight} kg)" 
    
    

class CargoAssignment(models.Model):
    cargo = models.ForeignKey(
        Cargo,
        on_delete=models.CASCADE,
        related_name="assignments"
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="assignments"
    )

    optimization_run = models.ForeignKey(
    "OptimizationRun",
    on_delete=models.CASCADE,
    related_name="assignments",
    null=True,   # <-- Veritabanında hata almamak için şimdilik null=True ekle
    blank=True   # <-- Formlarda zorunlu olmaması için
)
    loaded_weight = models.FloatField(
        default=0   # 🔥 BUNU EKLE
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True) 

    def __str__(self):
        return f"Run {self.optimization_run_id} | Cargo {self.cargo_id} → {self.vehicle.name}"
    




class OptimizationRun(models.Model):
    # Bu satırdan itibaren her şey tam olarak 1 TAB (veya 4 boşluk) içeride olmalı!
    PROBLEM_TYPES = (
        ("fixed", "Sabit Araç"),
        ("unlimited", "Sınırsız Araç"),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    problem_type = models.CharField(
        max_length=20,
        choices=PROBLEM_TYPES
    )

    vehicles_used = models.PositiveIntegerField()
    total_distance = models.FloatField(help_text="Toplam mesafe (km)")
    total_weight = models.FloatField(help_text="Toplam taşınan ağırlık (kg)")
    total_cost = models.FloatField(help_text="Toplam maliyet")

    route = models.JSONField(null=True, blank=True)


    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="optimizations"
    )

    def __str__(self):
        # Fonksiyonun içindeki bu satır da fonksiyon ismine göre 1 TAB içeride olmalı
        return f"Optimization #{self.id} ({self.get_problem_type_display()})"


    # api/models.py

class VehicleRoute(models.Model):
    optimization_run = models.ForeignKey(
        "OptimizationRun",
        on_delete=models.CASCADE,
        related_name="vehicle_routes"
    )

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="routes"
    )

    # İstasyon sırası (mantıksal)
    stations = models.JSONField()
    # Yol çizimi (haritada polyline)
    path = models.JSONField()

    total_distance = models.FloatField()
    total_cost = models.FloatField()

    def __str__(self):
        return f"Run {self.optimization_run_id} | {self.vehicle.name}"
