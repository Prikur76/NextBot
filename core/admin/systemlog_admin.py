from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import path
from django.contrib import messages
from django.utils.html import format_html
from django.db.models import Q, Count, Avg, F
from django.utils import timezone

from core.models import User, Region, Zone, Car, FuelRecord, SystemLog
from core.admin_actions import export_action
from core.services.car_service import CarService
from core.services.export_service import ExportService
from core.services.region_service import RegionService



@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "ip_address", "short_details")
    list_filter = ("action", "created_at")
    search_fields = ("user__username", "details", "ip_address")
    readonly_fields = ("created_at", "user", "action", "details", "ip_address")
    list_per_page = 50
    date_hierarchy = "created_at"

    @admin.display(description="Подробности")
    def short_details(self, obj):
        return (obj.details[:70] + "...") if len(obj.details) > 70 else obj.details
    
    # Запрещаем создание/редактирование логов через админку
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    # Оптимизация запросов
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    