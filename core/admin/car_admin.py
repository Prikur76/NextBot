from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.contrib import messages
from django.utils.html import format_html
from django.db.models import Count
from django.utils import timezone

from core.models import Car
from core.admin.actions import export_action
from core.services.car_service import CarService
from core.services.export_service import ExportService


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = (
        "code", "model", "vin", "state_number", 
        "manufacture_year", "owner_inn","department_short", "region_link", 
        "car_age", "status_display", "is_active_display",  "created_at"
    )
    list_filter = (
        "is_active", "region", "department", 
        "manufacture_year", "created_at"
    )
    search_fields = (
        "code", "state_number", "model", "vin", 
        "owner_inn", "region__name", "department"
    )
    
    readonly_fields = ("created_at", "updated_at", "display_name")
    list_per_page = 25
    
    actions = [
        "export_selected_cars", 
        "archive_selected", 
        "activate_selected", 
        "find_duplicates_action"
    ]
    
    # Автодополнение для улучшения производительности
    autocomplete_fields = ["region"]
   
    # Настройка отображения детальной формы
    fieldsets = (
        ("Основная информация", {
            "fields": (
                "code", "state_number", "vin", "model", 
                "manufacture_year", "display_name"
            )
        }),
        ("Владелец и подразделение", {
            "fields": ("owner_inn", "department", "region")
        }),
        ("Статус и активность", {
            "fields": ("is_active", "status")
        }),
        ("Системная информация", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'archive-old-cars/',
                self.admin_site.admin_view(self.archive_old_cars),
                name='archive_old_cars'
            ),
            path(
                'find-duplicates/',
                self.admin_site.admin_view(self.find_duplicates),
                name='find_duplicates'
            ),
            path(
                'cars-statistics/',
                self.admin_site.admin_view(self.cars_statistics),
                name='cars_statistics'
            ),
            path(
                'export-all-cars/',
                self.admin_site.admin_view(self.export_all_cars),
                name='export_cars'
            ),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        """Добавляем расширенную статистику в список автомобилей"""
        extra_context = extra_context or {}
        
        # Базовая статистика
        stats = Car.objects.statistics_summary()
        
        # Статистика по возрасту
        age_stats = CarService.get_age_statistics()
        
        # Формируем читаемую статистику с правильными ключами
        readable_stats = {
            'total_cars': stats['total_cars'],
            'active_cars': stats['active_cars'],
            'cars_with_region': stats['cars_with_region'],
            'avg_age': f"{stats.get('avg_age', 0):.1f} лет",
            'age_range': f"{stats.get('min_age', 0)}-{stats.get('max_age', 0)} лет",
            'year_range': f"{stats.get('oldest_car_year', 0)}-{stats.get('newest_car_year', 0)}",
        }
        
        # Создаем словарь с читаемыми названиями групп для шаблона
        age_distribution_display = {
            '0_3_years': age_stats['age_ranges']['0_3_years'],
            '4_7_years': age_stats['age_ranges']['4_7_years'],
            '8_12_years': age_stats['age_ranges']['8_12_years'],
            '13_plus_years': age_stats['age_ranges']['13_plus_years'],
        }
        
        extra_context['stats'] = readable_stats
        extra_context['age_distribution'] = age_distribution_display
        
        return super().changelist_view(request, extra_context=extra_context)
    
    # Кастомные методы отображения
    @admin.display(description="Регион")
    def region_link(self, obj):
        if obj.region:
            return format_html(
                '<a href="{}?id__exact={}"><strong>{}</a>',
                f"/admin/core/region/",
                obj.region.id,
                obj.region.name
            )
        return "-"
    
    @admin.display(description="Подразделение")
    def department_short(self, obj):
        if obj.department:
            return obj.department[:20] + "..." if len(obj.department) > 20 else obj.department
        return "-"
    
    @admin.display(description="Возраст", ordering="manufacture_year")
    def car_age(self, obj):
        if not obj.manufacture_year:
            return "-"
        
        current_year = timezone.now().year
        age = current_year - obj.manufacture_year
        
        # Цветовое кодирование по возрасту
        if age <= 3:
            color = "green"
            badge = "🟢"
        elif age <= 7:
            color = "orange"
            badge = "🟡"
        else:
            color = "red"
            badge = "🔴"
        
        return format_html(
            '<span style="color: {};">{}{} {}</span>',
            color,
            badge,
            age,
            "лет" if age >= 5 else "года" if age >= 2 else "год"
        )
    
    @admin.display(description="Активен", boolean=True)
    def is_active_display(self, obj):
        return obj.is_active and obj.status != "АРХИВ"
    
    @admin.display(description="Статус")
    def status_display(self, obj):
        if obj.status == "АРХИВ" or not obj.is_active:
            return format_html('<span style="color: #999;">{}</span>', "АРХИВ")
        elif obj.status:
            return obj.status
        else:
            return "АКТИВЕН"
        
    # Кастомные действия
    @admin.action(description="Архивировать")
    def archive_selected(self, request, queryset):
        """Архивировать выбранные автомобили"""
        car_ids = list(queryset.values_list('id', flat=True))
        
        archived_count = CarService.bulk_archive_cars(
            car_ids,
            reason=f"Архивация из админ-панели пользователем {request.user.username}"
        )
        
        self.message_user(
            request, 
            f'Успешно архивировано {archived_count} автомобилей',
            messages.SUCCESS
        )
    
    @admin.action(description="Восстановить")    
    def activate_selected(self, request, queryset):
        """Активировать выбранные автомобили"""
        activated_count = 0
        for car in queryset:
            if car.is_archived:
                car.restore_from_archive()
                activated_count += 1
        
        self.message_user(
            request,
            f'Активировано {activated_count} автомобилей',
            messages.SUCCESS
        )
        
    @admin.action(description="Поиск дубликатов")
    def find_duplicates_action(self, request, queryset):
        """Найти дубликаты среди выбранных автомобилей"""
        car_ids = list(queryset.values_list('id', flat=True))
        duplicates_info = []
        
        # Проверяем дубликаты госномеров
        state_duplicates = Car.objects.filter(
            id__in=car_ids
        ).values('state_number').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        for dup in state_duplicates:
            duplicates_info.append(f"Госномер {dup['state_number']}: {dup['count']} шт.")
        
        # Проверяем дубликаты VIN
        vin_duplicates = Car.objects.filter(
            id__in=car_ids
        ).exclude(vin='').values('vin').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        for dup in vin_duplicates:
            duplicates_info.append(f"VIN {dup['vin']}: {dup['count']} шт.")
        
        if duplicates_info:
            message = "Найдены дубликаты:\n" + "\n".join(duplicates_info)
            self.message_user(request, message, messages.WARNING)
        else:
            self.message_user(request, "Дубликатов не найдено", messages.INFO)
     
    @export_action(
        export_method='export_selected_cars',
        filename_prefix='selected_cars',
        description='Экспорт выбранных (Excel)'
    )
    def export_selected_cars(self, request, queryset):
        """Экспорт выбранных автомобилей"""
        pass  # Тело функции не нужно, вся логика в декораторе
                       
    # Кастомные views для URL
    def archive_old_cars(self, request):
        """Архивация старых автомобилей"""
        if not request.user.has_perm('core.change_car'):
            messages.error(request, 'Недостаточно прав')
            return HttpResponseRedirect('../../')
        
        try:
            # Автомобили старше 15 лет
            from datetime import datetime
            current_year = datetime.now().year
            old_year = current_year - 15
            
            old_cars = Car.objects.active().filter(manufacture_year__lte=old_year)
            car_ids = list(old_cars.values_list('id', flat=True))
            
            archived_count = CarService.bulk_archive_cars(
                car_ids,
                reason="Автоматическая архивация старых автомобилей"
            )
            
            messages.success(
                request, 
                f'Архивировано {archived_count} автомобилей старше {old_year} года'
            )
            
        except Exception as e:
            messages.error(request, f'Ошибка архивации: {str(e)}')
        
        return HttpResponseRedirect('../../')
    
    def find_duplicates(self, request):
        """Поиск дубликатов во всей базе"""
        duplicates = Car.objects.find_duplicates()
        
        state_duplicates = duplicates['state_number_duplicates']
        vin_duplicates = duplicates['vin_duplicates']
        
        if state_duplicates or vin_duplicates:
            message = "Найдены дубликаты:\n"
            
            if state_duplicates:
                message += "\nГосномера:\n"
                for dup in state_duplicates:
                    message += f"- {dup['state_number']}: {dup['count']} автомобилей\n"
            
            if vin_duplicates:
                message += "\nVIN:\n"
                for dup in vin_duplicates:
                    message += f"- {dup['vin']}: {dup['count']} автомобилей\n"
            
            messages.warning(request, message)
        else:
            messages.info(request, "Дубликатов не найдено")
        
        return HttpResponseRedirect('../../')
    
    def cars_statistics(self, request):
        """Расширенная статистика по автомобилям"""
        age_report = CarService.get_fleet_age_report()
        
        # Используем читаемые названия для сообщения
        message = format_html(
            """
            <strong>📊 Статистика автопарка:</strong><br>
            • Всего автомобилей: {}<br>
            • Активных: {}<br>
            • Средний возраст: {}<br>
            • Диапазон возрастов: {}<br>
            • Диапазон годов выпуска: {}<br>
            <br>
            <strong>📈 Распределение по возрастам:</strong><br>
            • 0-3 года: {} шт.<br>
            • 4-7 лет: {} шт.<br>
            • 8-12 лет: {} шт.<br>
            • 13+ лет: {} шт.
            """,
            age_report['total_cars'],
            age_report['active_cars'],
            age_report['avg_age'],
            age_report['age_range'],
            age_report['year_range'],
            age_report['age_distribution']['0_3_years'],
            age_report['age_distribution']['4_7_years'],
            age_report['age_distribution']['8_12_years'],
            age_report['age_distribution']['13_plus_years']
        )
        
        messages.info(request, message)
        return HttpResponseRedirect('../../')

    def export_all_cars(self, request):
        """Экспорт всех автомобилей"""
        return ExportService.export_cars_data('xlsx')    

    # Переопределяем queryset для исключения архивных по умолчанию
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Показываем архивные только если явно отфильтровано
        if 'is_active' not in request.GET and 'status' not in request.GET:
            qs = qs.active()
        return qs.select_related('region')
    
    # Настройка прав для действий
    def get_actions(self, request):
        """Права на действия"""

        actions = super().get_actions(request)

        if not request.user.has_perm('core.change_car'):
            if 'archive_selected' in actions:
                del actions['archive_selected']
            if 'activate_selected' in actions:
                del actions['activate_selected']
            del actions['delete_selected']
        return actions
