from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from core.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):

    list_display = (
        "username",
        "get_full_name",
        "phone",
        "telegram_id",
        "region",
        "zone",
        "get_groups",
        "is_active",
        "is_staff",
    )

    # --- главное: переопределяем queryset ---
    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # сортируем по первой найденной группе (если несколько — берём минимальную по алфавиту)
        from django.db.models import Subquery, OuterRef

        # подзапрос для выборки имени первой группы пользователя
        first_group = (
            User.groups.through.objects
            .filter(user_id=OuterRef("pk"))
            .order_by("group__name")
            .values("group__name")[:1]
        )

        # добавляем аннотированное поле group_name
        qs = qs.annotate(first_group_name=Subquery(first_group))
        return qs

    # --- метод для отображения групп в таблице ---
    @admin.display(description="Роль", admin_order_field="first_group_name")
    def get_groups(self, obj):
        return ", ".join(obj.groups.values_list("name", flat=True)) or "—"
    