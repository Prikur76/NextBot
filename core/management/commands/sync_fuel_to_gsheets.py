import asyncio

from django.core.management.base import BaseCommand

from core.services.google_sheets_service import FuelRecordGoogleSheetsService


class Command(BaseCommand):
    help = 'Синхронизация записей о заправках с Google Sheets'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--full-sync',
            action='store_true',
            help='Полная синхронизация всех записей'
        )
        parser.add_argument(
            '--record-ids',
            type=str,
            help='ID записей для синхронизации (через запятую)'
        )
    
    def handle(self, *args, **options):
        asyncio.run(self.async_handle(*args, **options))
    
    async def async_handle(self, *args, **options):
        self.stdout.write("🔄 Синхронизация с Google Sheets...")
        
        service = FuelRecordGoogleSheetsService()
        
        try:
            if options['full_sync']:
                # Полная синхронизация
                result = await service.sync_all_records()
            elif options['record_ids']:
                # Синхронизация конкретных записей
                record_ids = [int(id.strip()) for id in options['record_ids'].split(',')]
                result = await service.sync_multiple_records(record_ids)
            else:
                # Только проверка подключения
                data = await service.get_synced_data()
                result = {
                    'success': True,
                    'message': f'Подключение успешно. Записей в таблице: {len(data)}'
                }
            
            if result['success']:
                self.stdout.write(self.style.SUCCESS(f"✅ {result['message']}"))
                if 'synced_count' in result:
                    self.stdout.write(f"📊 Синхронизировано записей: {result['synced_count']}")
            else:
                self.stdout.write(self.style.ERROR(f"❌ {result.get('error', 'Неизвестная ошибка')}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Ошибка синхронизации: {e}"))
