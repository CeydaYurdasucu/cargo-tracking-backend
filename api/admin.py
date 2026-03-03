from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User
from .models import Station
from .models import Cargo
from .models import Vehicle
from .models import CargoAssignment

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User

    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")

    fieldsets = UserAdmin.fieldsets + (
        ("Role Information", {"fields": ("role",)}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Role Information", {"fields": ("role",)}),
    )

@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("name", "latitude", "longitude", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)



@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ("station", "user", "quantity", "weight", "status", "created_at")
    list_filter = ("status", "station")
    search_fields = ("user__username",)
    date_hierarchy = "created_at"


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "max_weight",
        "is_rented",
        "rental_cost",
        "is_active",
    )
    list_filter = ("is_rented", "is_active")
    search_fields = ("name",)



@admin.register(CargoAssignment)
class CargoAssignmentAdmin(admin.ModelAdmin):
    list_display = ("cargo", "vehicle", "assigned_at")
    list_filter = ("vehicle",)

