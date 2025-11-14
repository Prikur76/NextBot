from django.contrib import admin, messages
from django.utils.html import format_html

from core.models import Zone


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = (
        "name", "code",
        "regions_count",
        "cars_count", "active_cars_count",
        "active", "can_archive_display",
    )
    list_filter = ("active",)
    search_fields = ("name", "code")
    list_per_page = 25

    actions = ["archive_selected", "restore_selected"]

    readonly_fields = (
        "regions_count_display",
        "cars_count_display",
        "active_cars_count_display",
        "can_archive_display",
    )

    fieldsets = (
        ("Основная информация", {
            "fields": ("name", "code", "active")
        }),
        ("Статистика", {
            "fields": (
                "regions_count_display",
                "cars_count_display",
                "active_cars_count_display",
                "can_archive_display",
            ),
            "classes": ("collapse",),
        }),
        ("Состав", {
            "fields": ("regions",),
        }),
    )

    filter_horizontal = ("regions",)

    # Оптимизация запросов
    def get_queryset(self, request):
        return super().get_queryset(request).with_stats()

    # --- list_display fields ---
    @admin.display(description="Регионов", ordering="total_regions")
    def regions_count(self, obj):
        return obj.total_regions

    @admin.display(description="Всего авто", ordering="total_cars")
    def cars_count(self, obj):
        return format_html(
            '<a href="/admin/core/zone/?region__zones__id__exact={}"><strong>{}</strong></a>',
            obj.id,
            obj.total_cars
        )

    @admin.display(description="Активных авто", ordering="active_cars")
    def active_cars_count(self, obj):
        if obj.active_cars == 0:
            return format_html('<span style="color:#888;">0</span>')
        return format_html('<span style="color:green;"><strong>{}</strong></span>', obj.active_cars)

    @admin.display(description="Можно архивировать", boolean=True)
    def can_archive_display(self, obj):
        return obj.active_cars == 0

    # --- readonly fields for detail page ---
    def regions_count_display(self, obj):
        return obj.regions_count

    def cars_count_display(self, obj):
        return obj.cars_count

    def active_cars_count_display(self, obj):
        return obj.active_cars_count

    # --- Actions ---
    def archive_selected(self, request, queryset):
        archived = 0
        blocked = 0

        for zone in queryset:
            if zone.can_be_archived:
                zone.archive("Архивировано администратором")
                archived += 1
            else:
                blocked += 1

        if archived:
            self.message_user(request, f"Архивировано {archived} зон.", messages.SUCCESS)
        if blocked:
            self.message_user(request, f"{blocked} зон не могут быть архивированы (есть активные авто).", messages.WARNING)

    def restore_selected(self, request, queryset):
        restored = queryset.update(active=True)
        self.message_user(request, f"Восстановлено {restored} зон.", messages.SUCCESS)
