from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Кастомная модель пользователя.
    Использует стандартные группы Django для ролей и прав.
    """
    telegram_id = models.BigIntegerField(
        unique=True,
        db_index=True,
        verbose_name="Telegram ID",
        null=True,
        blank=True)
    first_name = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Имя")
    last_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Фамилия")
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Телефон")
    zone = models.ForeignKey(
        "core.Zone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="Зона")
    region = models.ForeignKey(
        "core.Region",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="Регион")
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен")

    class Meta:
        db_table = "users"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        indexes = [
            models.Index(fields=["telegram_id"]),
        ]

    def __str__(self):
        if self.first_name and self.last_name:
            return f"{self.get_full_name()} ({self.telegram_id})"
        return f"{self.username} ({self.telegram_id})" 
    
    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
