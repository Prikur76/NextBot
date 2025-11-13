import asyncio

from django.core.management.base import BaseCommand

from core.clients.element_car_client import ElementCarClient
from core.utils.logging import log_sync_failure, log_sync_success


class Command(BaseCommand):
    help = "Синхронизация автомобилей с 1С:Элемент"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительная синхронизация независимо от расписания',
        )
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Только проверка доступности API',
        )
        parser.add_argument(
            '--sample',
            action='store_true',
            help='Показать пример данных без синхронизации',
        )

    def handle(self, *args, **options):
        asyncio.run(self.async_handle(*args, **options))

    async def async_handle(self, *args, **options):
        self.stdout.write("🚗 Начинаю синхронизацию с 1С:Элемент...")

        try:
            client = ElementCarClient()

            if options['check_only']:
                is_available = await client.check_availability()
                if is_available:
                    self.stdout.write(self.style.SUCCESS("✅ API 1С:Элемент доступен"))
                    
                    # Показываем пример данных
                    sample = await client.get_sample_data(2)
                    if sample:
                        self.stdout.write("📋 Пример данных:")
                        for car in sample:
                            self.stdout.write(f"   - {car.get('state_number', 'N/A')} | {car.get('model', 'N/A')} | {car.get('region', 'N/A')} | Активен: {car.get('is_active', 'N/A')} | Статус: {car.get('status', 'N/A')}")
                else:
                    self.stdout.write(self.style.ERROR("❌ API 1С:Элемент недоступен"))
                return

            if options['sample']:
                sample = await client.get_sample_data(5)
                if sample:
                    self.stdout.write("📋 Пример данных из 1С:")
                    for i, car in enumerate(sample, 1):
                        self.stdout.write(f"{i}. {car.get('state_number', 'N/A')} | {car.get('model', 'N/A')} | {car.get('region', 'N/A')} | Активен: {car.get('is_active', 'N/A')} | Статус: {car.get('status', 'N/A')}")
                else:
                    self.stdout.write(self.style.WARNING("⚠️ Нет данных для отображения"))
                return

            # Проверяем доступность API
            if not await client.check_availability():
                self.stdout.write(self.style.ERROR("❌ API 1С:Элемент недоступен, пропускаю синхронизацию"))
                await log_sync_failure("API недоступен")
                return

            # Выполняем синхронизацию
            stats = await client.sync_with_database()

            # Формируем подробный отчет
            message = self._format_stats_message(stats)
            
            self.stdout.write(self.style.SUCCESS(f"✅ {message}"))
            await log_sync_success(message, stats)

        except Exception as e:
            error_msg = f"Ошибка синхронизации: {str(e)}"
            self.stdout.write(self.style.ERROR(f"❌ {error_msg}"))
            await log_sync_failure(error_msg)

    def _format_stats_message(self, stats: dict) -> str:
        """Форматирует статистику в читаемое сообщение"""
        parts = []
        
        if stats.get('created', 0) > 0:
            parts.append(f"создано: {stats['created']}")
        if stats.get('updated', 0) > 0:
            parts.append(f"обновлено: {stats['updated']}")
        if stats.get('deactivated', 0) > 0:
            parts.append(f"деактивировано: {stats['deactivated']}")
        if stats.get('regions_created', 0) > 0:
            parts.append(f"регионов создано: {stats['regions_created']}")
        if stats.get('regions_updated', 0) > 0:
            parts.append(f"регионов обновлено: {stats['regions_updated']}")
        if stats.get('errors', 0) > 0:
            parts.append(f"ошибок: {stats['errors']}")
            
        parts.append(f"всего обработано: {stats['total_processed']}")
        
        return "Синхронизация завершена: " + ", ".join(parts)
