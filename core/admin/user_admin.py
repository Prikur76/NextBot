from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from core.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username", "get_full_name", 
        "phone", "telegram_id", 
        "region", "zone", "get_groups",
        "is_active", "is_staff",
        
    )
    list_filter = ("is_active", "zone", "region", "groups")
    search_fields = ("username", "telegram_id", "first_name", "last_name")
    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Персональные данные", {"fields": ("first_name", "last_name", "phone", "telegram_id", "region", "zone")}),
        ("Права доступа", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    list_per_page = 30
    ordering = ("region", "get_groups", "username", )
    
    @admin.display(description="ФИО")
    def get_full_name(self, obj):
        if obj.first_name and obj.last_name:
            return f"{obj.first_name} {obj.last_name}"
        return obj.username
    
    @admin.display(description="Группы")
    def get_groups(self, obj):
        return ", ".join(obj.groups.values_list("name", flat=True)) or "—"

    