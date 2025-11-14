import pytz
import gspread

from collections.abc import Sequence
from datetime import datetime, timezone
from django.conf import settings
from google.oauth2.service_account import Credentials
from gspread import Worksheet
from gspread.exceptions import APIError


class GoogleSheetsClient:
    """Клиент для работы с Google Sheets"""

    def __init__(self, spreadsheet_id: str | None = None):
        self._creds_path = getattr(settings, 'GSHEET_CREDENTIALS_JSON_PATH', None)
        self.spreadsheet_id = spreadsheet_id or getattr(settings, 'GSHEET_SPREADSHEET_ID', None)
        self._client = None
        print(f"Google Sheets credentials path: {self._creds_path}")
        print(f"Google Sheets spreadsheet id: {self.spreadsheet_id}")
        
        # Московское время
        self.MOSCOW_TZ = pytz.timezone("Europe/Moscow")

        if not self._creds_path:
            raise RuntimeError("Google Sheets credentials not configured")
        if not self.spreadsheet_id:
            raise RuntimeError("Google Sheets spreadsheet id not configured")

    def _authorize(self) -> None:
        """Авторизация в Google Sheets"""
        if self._client:
            return

        try:
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_file(self._creds_path, scopes=scopes)
            self._client = gspread.authorize(creds)
        except Exception as e:
            raise RuntimeError(f"Ошибка авторизации Google Sheets: {e}")

    def _get_worksheet(self, sheet_name: str) -> Worksheet:
        """Получение рабочего листа"""
        self._authorize()
        try:
            spreadsheet = self._client.open_by_key(self.spreadsheet_id)
            return spreadsheet.worksheet(sheet_name)
        except APIError as e:
            raise RuntimeError(f"Ошибка доступа к таблице: {e}")

    def _format_datetime_msk(self, dt: datetime) -> str:
        """
        Конвертирует любую datetime в московское время и форматирует как 'ДД.ММ.ГГГГ ЧЧ:ММ'
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_msk = dt.astimezone(self.MOSCOW_TZ)
        return dt_msk.strftime("%d.%m.%Y %H:%M")

    async def append_row(self, sheet_name: str, row: Sequence, **kwargs) -> None:
        """
        Добавление строки в указанный лист.
        Если первый элемент — datetime, он автоматически преобразуется в МСК и форматируется.
        """
        try:
            # Преобразуем дату, если она есть (предполагаем, что первая колонка — дата)
            processed_row = list(row)
            if len(processed_row) > 0 and isinstance(processed_row[0], datetime):
                processed_row[0] = self._format_datetime_msk(processed_row[0])

            worksheet = self._get_worksheet(sheet_name)
            worksheet.append_row(processed_row, **kwargs)

        except Exception as e:
            raise RuntimeError(f"Ошибка добавления строки: {e}")

    async def batch_append_rows(self, sheet_name: str, rows: list[Sequence]) -> None:
        """Пакетное добавление строк с форматированием дат"""
        try:
            worksheet = self._get_worksheet(sheet_name)
            for row in rows:
                processed_row = list(row)
                if len(processed_row) > 0 and isinstance(processed_row[0], datetime):
                    processed_row[0] = self._format_datetime_msk(processed_row[0])
                worksheet.append_row(processed_row)
        except Exception as e:
            raise RuntimeError(f"Ошибка пакетного добавления строк: {e}")

    async def clear_sheet(self, sheet_name: str) -> None:
        """Очистка листа"""
        try:
            worksheet = self._get_worksheet(sheet_name)
            worksheet.clear()
        except Exception as e:
            raise RuntimeError(f"Ошибка очистки листа: {e}")

    async def get_all_records(self, sheet_name: str) -> list[dict]:
        """Получение всех записей с листа"""
        try:
            worksheet = self._get_worksheet(sheet_name)
            return worksheet.get_all_records()
        except Exception as e:
            raise RuntimeError(f"Ошибка получения записей: {e}")
