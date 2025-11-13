from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()


class SystemLog(models.Model):
    ACTION_CHOICES = [
        ("login", "Вход в систему"),
        ("logout", "Выход из системы"),
        ("add_refuel", "Добавление заправки"),
        ("view_report", "Просмотр отчёта"),
        ("access_denied", "Отказ в доступе"),
        ("error", "Ошибка"),
        ("info", "Информация"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Пользователь"
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name="Действие")
    details = models.TextField(blank=True, verbose_name="Подробности")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP-адрес")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время")

    class Meta:
        verbose_name = "Системный лог"
        verbose_name_plural = "Системные логи"
        ordering = ["-created_at"]

    def __str__(self):
        if self.user:
            return f"[{self.created_at:%d.%m %H:%M}] {self.user.username} — {self.get_action_display()}"
        return f"[{self.created_at:%d.%m %H:%M}] {self.get_action_display()}"
