from django.db import models
from django.db.models import Count, Q


class ZoneQuerySet(models.QuerySet):
    """Расширенный QuerySet для зон со статистикой"""

    def with_stats(self):
        return self.annotate(
            total_regions=Count("regions", distinct=True),
            total_cars=Count("regions__cars", distinct=True),
            active_cars=Count(
                "regions__cars",
                filter=Q(regions__cars__is_active=True),
                distinct=True,
            ),
        )

    def active(self):
        return self.filter(active=True)


class Zone(models.Model):
    """
    Зона объединяет один или несколько регионов.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Зона")
    code = models.CharField(max_length=50, unique=True, verbose_name="Код")
    regions = models.ManyToManyField("core.Region", related_name="zones", verbose_name="Регионы")
    active = models.BooleanField(default=True, verbose_name="Активна")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлена")

    objects = ZoneQuerySet.as_manager()

    class Meta:
        db_table = "zones"
        verbose_name = "Зона"
        verbose_name_plural = "Зоны"
        ordering = ["name"]

    def __str__(self):
        return self.name

    # --- Методы статистики ---
    @property
    def regions_count(self):
        return self.regions.count()

    @property
    def cars_count(self):
        return sum(r.cars_count for r in self.regions.all())

    @property
    def active_cars_count(self):
        return sum(r.active_cars_count for r in self.regions.all())

    # --- Логика архивирования ---
    @property
    def can_be_archived(self):
        return self.active_cars_count == 0

    def archive(self, reason=""):
        if not self.can_be_archived:
            raise ValueError("Нельзя архивировать зону, пока в ней есть активные автомобили")
        self.active = False
        self.save(update_fields=["active", "updated_at"])

    def restore(self):
        self.active = True
        self.save(update_fields=["active", "updated_at"])
