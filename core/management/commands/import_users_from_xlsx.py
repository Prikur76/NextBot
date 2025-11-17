import logging
import polars as pl

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.db import transaction

from core.models import User


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Импорт пользователей из Excel файла'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Путь к Excel файлу с данными пользователей'
        )
        parser.add_argument(
            '--default-password',
            type=str,
            default='TempPassword123!',
            help='Пароль по умолчанию для новых пользователей'
        )
        parser.add_argument(
            '--group',
            type=str,
            default=None,
            help='Группа для новых пользователей (опционально)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет импортировано без сохранения в БД'
        )
        parser.add_argument(
            '--sheet-name',
            type=str,
            default=None,
            help='Название листа в Excel файле (по умолчанию первый лист)'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        default_password = options['default_password']
        group_name = options['group']
        dry_run = options['dry_run']
        sheet_name = options['sheet_name']

        try:
            df = pl.read_excel(
                file_path,
                sheet_name=sheet_name,
                engine="openpyxl"  # Альтернативный движок
            )
                
            # Проверка обязательных колонок
            required_columns = ['ID пользователя', 'Имя пользователя']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                self.stdout.write(
                    self.style.ERROR(f"❌ Отсутствуют обязательные колонки: {', '.join(missing_columns)}")
                )
                self.stdout.write(f"📋 Найденные колонки: {', '.join(df.columns)}")
                return

            # Получаем группу если указана
            group = None
            if group_name:
                try:
                    group = Group.objects.get(name=group_name)
                    self.stdout.write(f"📋 Группа для импорта: {group_name}")
                except Group.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"⚠️ Группа '{group_name}' не найдена. Пользователи будут созданы без группы.")
                    )

            # Получаем существующие telegram_id для проверки
            existing_telegram_ids = set(
                User.objects.exclude(telegram_id__isnull=True)
                .values_list('telegram_id', flat=True)
            )

            # Статистика
            stats = {
                'total': len(df),
                'created': 0,
                'skipped_existing': 0,
                'skipped_invalid': 0,
                'errors': 0
            }

            if dry_run:
                self.stdout.write("🔍 РЕЖИМ ПРЕДПРОСМОТРА (данные не будут сохранены)")
                self.stdout.write("=" * 60)

            # Обработка каждой строки с помощью iter_rows()
            for row in df.iter_rows(named=True):
                try:
                    result = self.process_user_row(
                        row, default_password, group, dry_run, existing_telegram_ids
                    )
                    
                    if result == 'created':
                        stats['created'] += 1
                    elif result == 'skipped_existing':
                        stats['skipped_existing'] += 1
                    elif result == 'skipped_invalid':
                        stats['skipped_invalid'] += 1
                    else:
                        stats['errors'] += 1

                except Exception as e:
                    stats['errors'] += 1
                    username = row.get('Имя пользователя', 'N/A')
                    self.stdout.write(
                        self.style.ERROR(f"❌ Ошибка обработки пользователя {username}: {str(e)}")
                    )

            # Вывод статистики
            self.print_statistics(stats, dry_run, group_name)

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"❌ Файл не найден: {file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Ошибка чтения файла: {str(e)}"))

    def process_user_row(self, row, default_password, group, dry_run, existing_telegram_ids):
        """Обработка одной строки с данными пользователя"""
        
        # Извлекаем данные
        telegram_id_str = str(row['ID пользователя']).strip()
        display_name = str(row['Имя пользователя']).strip()
        
        # Сохраняем оригинальный ID пользователя как username
        username = telegram_id_str  # user257088784
        
        # Обработка telegram_id (убираем 'user' префикс если есть)
        if telegram_id_str.startswith('user'):
            telegram_id = telegram_id_str[4:]  # убираем 'user'
        else:
            telegram_id = telegram_id_str
        
        # Проверяем что telegram_id является числом
        try:
            telegram_id_int = int(telegram_id)
        except (ValueError, TypeError):
            self.stdout.write(
                self.style.WARNING(f"⚠️ Пропущен некорректный Telegram ID: {telegram_id_str}")
            )
            return 'skipped_invalid'

        # Проверяем существует ли пользователь с таким telegram_id
        if telegram_id_int in existing_telegram_ids:
            user_info = f"{display_name} (Telegram ID: {telegram_id_int}, Username: {username})"
            if dry_run:
                self.stdout.write(f"⏭️  [DRY RUN] ПРОПУЩЕН (существует): {user_info}")
            else:
                self.stdout.write(
                    self.style.WARNING(f"⏭️  Пропущен (существует): {user_info}")
                )
            return 'skipped_existing'

        # Извлекаем имя и фамилию из display_name
        first_name = self.extract_first_name(display_name)
        last_name = self.extract_last_name(display_name)

        # Подготовка данных для логирования
        user_info = f"{display_name} (Username: {username}, Telegram ID: {telegram_id_int})"
        group_info = f" в группу '{group.name}'" if group else ""

        if dry_run:
            self.stdout.write(f"✅ [DRY RUN] БУДЕТ СОЗДАН: {user_info}{group_info}")
            if first_name or last_name:
                self.stdout.write(f"   👤 Имя: {first_name}, Фамилия: {last_name}")
            return 'created'

        # Создание нового пользователя в базе данных
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,  # Сохраняем user257088784 как username
                password=default_password,
                telegram_id=telegram_id_int,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            
            # Добавляем в группу если указана
            if group:
                user.groups.add(group)
            
            self.stdout.write(
                self.style.SUCCESS(f"✅ Создан: {user_info}{group_info}")
            )

        return 'created'

    def extract_first_name(self, display_name):
        """Извлекает имя из display_name"""
        if not display_name:
            return ""
        
        # Если display_name содержит пробелы, берем первое слово как имя
        parts = display_name.split()
        if len(parts) > 1:
            return parts[0]
        
        # Иначе возвращаем весь display_name как имя
        return display_name

    def extract_last_name(self, display_name):
        """Извлекает фамилию из display_name"""
        if not display_name:
            return ""
        
        parts = display_name.split()
        
        if len(parts) > 1:
            return parts[-1]
        
        return ""
            

    def print_statistics(self, stats, dry_run, group_name):
        """Вывод статистики импорта"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("📊 СТАТИСТИКА ИМПОРТА")
        self.stdout.write("=" * 60)
        
        mode = " (РЕЖИМ ПРЕДПРОСМОТРА)" if dry_run else ""
        group_info = f" (группа: {group_name})" if group_name else " (без группы)"
        
        self.stdout.write(f"Всего записей в файле: {stats['total']}{mode}")
        self.stdout.write(f"✅ Будет создано: {stats['created']}{group_info}")
        self.stdout.write(f"⏭️  Пропущено существующих: {stats['skipped_existing']}")
        self.stdout.write(f"⚠️  Пропущено некорректных: {stats['skipped_invalid']}")
        self.stdout.write(f"❌ Ошибок: {stats['errors']}")
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"🎉 Успешно создано новых пользователей: {stats['created']}{group_info}")
            )


# Example usage:
"""
# Базовый импорт (без группы)
python manage.py import_users_from_xlsx --file "users.xlsx"

# Импорт с группой
python manage.py import_users_from_xlsx --file "users.xlsx" --group "Заправщик"

# Импорт с группой Менеджер
python manage.py import_users_from_xlsx --file "users.xlsx" --group "Менеджер"

# Предпросмотр
python manage.py import_users_from_xlsx --file "users.xlsx" --group "Заправщик" --dry-run
"""
