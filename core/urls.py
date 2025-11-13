# web/urls.py
from django.urls import path
from core import views


urlpatterns = [
    path("", views.index, name="index"),
    path("fuel/add/", views.add_fuel_record, name="add_fuel"),
    path("fuel/reports/", views.reports, name="reports"),
]
