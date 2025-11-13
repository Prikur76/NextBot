from django.db import models


class Zone(models.Model):
    """
    Зона объединяет один или несколько регионов.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Зона")
    code = models.CharField(max_length=50, unique=True, verbose_name="Код")
    regions = models.ManyToManyField("core.Region", related_name="zones", verbose_name="Регионы")
    active = models.BooleanField(default=True, verbose_name="Активна")

    class Meta:
        db_table = "zones"
        verbose_name = "Зона"
        verbose_name_plural = "Зоны"
        ordering = ["name"]

    def __str__(self):
        return self.name

