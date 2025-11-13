from django.contrib import admin
from django.utils.html import format_html

from core.models import Zone, Car


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "regions_count", "cars_count", "active")
    list_filter = ("active",)
    search_fields = ("name", "code")
    filter_horizontal = ("regions",)
    list_per_page = 25
        
    @admin.display(description="Регионов")
    def regions_count(self, obj):
        return obj.regions.count()
    
    @admin.display(description="Автомобилей")
    def cars_count(self, obj):
        count = Car.objects.active().filter(region__zones=obj).count()
        return format_html(
            '<a href="{}?region__zones__id__exact={}"><strong>{}</a>',
            f"/admin/core/car/",
            obj.id,
            count
        )
       
