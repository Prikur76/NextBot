from datetime import datetime, timezone
from django.conf import settings
from asgiref.sync import sync_to_async
import pytz

from core.clients.google_sheets_client import GoogleSheetsClient
from core.models import FuelRecord
from core.utils.logging import log_action


class FuelRecordGoogleSheetsService:
    """Сервис для синхронизации записей о заправках с Google Sheets"""
    
    def __init__(self):
        self.sheet_name = settings.GSHEET.get("SHEET_NAME", "Заправки")
        self.client = GoogleSheetsClient()
    
    @sync_to_async
    def _get_all_fuel_records(self):
        """Асинхронное получение всех записей о заправках"""
        return list(FuelRecord.objects.select_related(
            "car", "employee", "historical_region"
        ).all())
    
    @sync_to_async
    def _get_fuel_record_by_id(self, record_id):
        """Асинхронное получение записи по ID"""
        try:
            return FuelRecord.objects.select_related(
                "car", "employee", "historical_region"
            ).get(id=record_id)
        except FuelRecord.DoesNotExist:
            return None
    
    @sync_to_async
    def _log_sync_action(self, user, action, details):
        """Асинхронное логирование"""
        return log_action(user, action, details, ip_address=None)
    
    def _prepare_fuel_record_row(self, record: FuelRecord) -> list:
        """Подготовка строки для Google Sheets из записи о заправке"""
        # Получаем читаемые значения вместо ленивых объектов
        fuel_type_display = self._get_fuel_type_display(record.fuel_type)
        source_display = self._get_source_display(record.source)
        
        return [
            self._format_datetime_msk(record.filled_at) if record.filled_at else "",
            record.car.state_number if record.car else "N/A",
            record.car.model if record.car else "N/A",
            float(record.liters) if record.liters else 0.0,
            fuel_type_display,
            source_display,
            record.employee.get_full_name() if record.employee else "Неизвестно",
            record.historical_department or "",
            record.historical_region.name if record.historical_region else "",
            "Да" if record.approved else "Нет",
            record.notes or "",
            self._format_datetime_msk(record.created_at) if record.created_at else ""
        ]
    
    def _get_fuel_type_display(self, fuel_type):
        """Получение читаемого значения типа топлива"""
        fuel_type_map = {
            "GASOLINE": "Бензин",
            "DIESEL": "Дизель",
        }
        return fuel_type_map.get(fuel_type, fuel_type)
    
    def _get_source_display(self, source):
        """Получение читаемого значения способа заправки"""
        source_map = {
            "CARD": "Топливная карта",
            "TGBOT": "Телеграм-бот",
            "TRUCK": "Топливозаправщик",
        }
        return source_map.get(source, source)
    
    def _format_datetime_msk(self, dt: datetime) -> str:
        """Форматирование даты в московское время"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_msk = dt.astimezone(pytz.timezone("Europe/Moscow"))
        return dt_msk.strftime("%d.%m.%Y %H:%M")
    
    async def sync_single_record(self, record_id: int) -> bool:
        """Синхронизация одной записи о заправке по ID"""
        try:
            # Получаем запись асинхронно
            record = await self._get_fuel_record_by_id(record_id)
            if not record:
                await self._log_sync_action(
                    None,
                    "google_sheets_error",
                    f"Запись {record_id} не найдена"
                )
                return False
            
            row = self._prepare_fuel_record_row(record)
            await self.client.append_row(self.sheet_name, row)
            
            # Логируем успешную синхронизацию
            await self._log_sync_action(
                record.employee,
                "google_sheets_sync",
                f"Запись о заправке {record.id} синхронизирована с Google Sheets"
            )
            return True
            
        except Exception as e:
            # Логируем ошибку
            await self._log_sync_action(
                None,
                "google_sheets_error",
                f"Ошибка синхронизации записи {record_id} с Google Sheets: {str(e)}"
            )
            return False
    
    async def sync_multiple_records(self, record_ids: list[int]) -> dict:
        """Синхронизация нескольких записей"""
        success_count = 0
        total_count = len(record_ids)
        
        for record_id in record_ids:
            if await self.sync_single_record(record_id):
                success_count += 1
        
        return {
            "success": True,
            "synced_count": success_count,
            "total_count": total_count,
            "message": f"Синхронизировано {success_count} из {total_count} записей"
        }
    
    async def sync_all_records(self) -> dict:
        """Синхронизация всех записей о заправках"""
        try:
            # Получаем все записи о заправках асинхронно
            records = await self._get_all_fuel_records()
            
            # Подготавливаем данные
            rows = []
            for record in records:
                rows.append(self._prepare_fuel_record_row(record))
            
            # Очищаем лист
            await self.client.clear_sheet(self.sheet_name)
            
            # Добавляем заголовки
            headers = [
                "Дата заправки",
                "Госномер",
                "Модель авто",
                "Литры",
                "Тип топлива",
                "Способ заправки",
                "Сотрудник",
                "Подразделение",
                "Регион",
                "Подтверждено",
                "Примечания",
                "Дата создания"
            ]
            
            # Добавляем заголовки и все данные одним пакетом
            all_data = [headers] + rows
            await self.client.batch_append_rows(self.sheet_name, all_data)
            
            # Логируем успешную синхронизацию
            await self._log_sync_action(
                None,
                "google_sheets_sync",
                f"Синхронизировано {len(rows)} записей о заправках с Google Sheets"
            )
            
            return {
                "success": True,
                "synced_count": len(rows),
                "message": f"Успешно синхронизировано {len(rows)} записей"
            }
            
        except Exception as e:
            # Логируем ошибку
            await self._log_sync_action(
                None,
                "google_sheets_error",
                f"Ошибка массовой синхронизации с Google Sheets: {str(e)}"
            )
            return {
                "success": False,
                "synced_count": 0,
                "error": str(e)
            }
    
    async def get_synced_data(self) -> list[dict]:
        """Получение данных из Google Sheets"""
        try:
            return await self.client.get_all_records(self.sheet_name)
        except Exception as e:
            await self._log_sync_action(
                None,
                "google_sheets_error",
                f"Ошибка получения данных из Google Sheets: {str(e)}"
            )
            return []
