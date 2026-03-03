from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import  assign_fixed_view, assign_unlimited_view, create_station, deliver_vehicle_cargos, last_optimization_run
from .views import admin_dashboard

from .views import (
    test_auth,
    station_list,
    create_cargo,
    admin_cargo_summary,
    my_cargos,
    vehicle_cargo_list,
    vehicle_report,
    delete_station,
    optimization_run_list,
    optimization_run_detail,
    
)

urlpatterns = [
        path('login/', TokenObtainPairView.as_view(), name='login'),
        path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

        path('test-auth/', test_auth),
        path('stations/', station_list),
        path("stations/<int:station_id>/", delete_station),
        path("stations/create/", create_station),
        path('cargo/', create_cargo),

        path('admin/cargo-summary/', admin_cargo_summary),
       

        path('my-cargos/', my_cargos),
        path('admin/vehicles/<int:vehicle_id>/cargos/', vehicle_cargo_list),
        path('admin/vehicles/<int:vehicle_id>/deliver/', deliver_vehicle_cargos),
        path('admin/vehicles/<int:vehicle_id>/report/', vehicle_report),
        path('admin/dashboard/', admin_dashboard),
        path("admin/trips-history/", optimization_run_list, name="trips_history"),
        path("admin/trips-history/<int:run_id>/", optimization_run_detail, name="trip_detail"),
        path("admin/last-optimization/", last_optimization_run),
        
        path("admin/assign-unlimited/", assign_unlimited_view),
        path("admin/assign-fixed/", assign_fixed_view),


]
