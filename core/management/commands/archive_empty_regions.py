from django.core.management.base import BaseCommand
from core.services.region_service import RegionService


class Command(BaseCommand):
    help = 'Архивация регионов без активных автомобилей'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать какие регионы будут архивированы'
        )
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Автоматическая архивация без подтверждения'
        )
    
    def handle(self, *args, **options):
        if options['dry_run']:
            self.dry_run()
        elif options['auto']:
            self.auto_archive()
        else:
            self.interactive_archive()
    
    def dry_run(self):
        """Только показ регионов для архивации"""
        self.stdout.write("🔍 Поиск регионов для архивации...")
        
        result = RegionService.archive_empty_regions(dry_run=True)
        
        if result['total_found'] == 0:
            self.stdout.write(self.style.SUCCESS("✅ Нет регионов для архивации"))
            return
        
        self.stdout.write(self.style.WARNING(f"📦 Найдено регионов для архивации: {result['total_found']}"))
        
        for region in result['regions']:
            self.stdout.write(f"   • {region['name']} ({region['short_name']})")
        
        self.stdout.write(self.style.NOTICE("\nДля архивации выполните команду без --dry-run"))
    
    def auto_archive(self):
        """Автоматическая архивация без подтверждения"""
        self.stdout.write("🔄 Автоматическая архивация регионов...")
        
        result = RegionService.archive_empty_regions(dry_run=False)
        
        if result['archived'] > 0:
            self.stdout.write(self.style.SUCCESS(f"✅ Успешно архивировано {result['archived']} регионов"))
            
            for region in result['regions']:
                self.stdout.write(f"   • {region['name']}")
        else:
            self.stdout.write(self.style.SUCCESS("✅ Нет регионов для архивации"))
    
    def interactive_archive(self):
        """Интерактивная архивация с подтверждением"""
        self.stdout.write("🔍 Поиск регионов для архивации...")
        
        result = RegionService.archive_empty_regions(dry_run=True)
        
        if result['total_found'] == 0:
            self.stdout.write(self.style.SUCCESS("✅ Нет регионов для архивации"))
            return
        
        self.stdout.write(self.style.WARNING(f"📦 Найдено регионов для архивации: {result['total_found']}"))
        
        for region in result['regions']:
            self.stdout.write(f"   • {region['name']} ({region['short_name']})")
        
        confirm = input("\n❓ Продолжить с архивацией? (y/N): ")
        if confirm.lower() == 'y':
            result = RegionService.archive_empty_regions(dry_run=False)
            self.stdout.write(self.style.SUCCESS(f"✅ Успешно архивировано {result['archived']} регионов"))
        else:
            self.stdout.write("❌ Архивация отменена")
