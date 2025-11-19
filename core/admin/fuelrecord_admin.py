from asgiref.sync import async_to_sync
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path
from django.utils.html import format_html

from core.admin.actions import export_action
from core.models import Region, Zone, FuelRecord
from core.services.export_service import ExportService
from core.services.google_sheets_service import FuelRecordGoogleSheetsService


# Кастомные фильтры для FuelRecord
class FuelRecordRegionFilter(admin.SimpleListFilter):
    title = 'Регион'
    parameter_name = 'region'
    
    def lookups(self, request, model_admin):
        regions = Region.objects.all().values_list('id', 'name')
        return regions
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(car__region_id=self.value())
        return queryset


class FuelRecordEmployeeFilter(admin.SimpleListFilter):
    title = 'Сотрудник (зона)'
    parameter_name = 'employee_zone'
    
    def lookups(self, request, model_admin):
        zones = Zone.objects.all().values_list('id', 'name')
        return zones
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(employee__zone_id=self.value())
        return queryset


@admin.register(FuelRecord)
class FuelRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id", "filled_at_formatted", 
        "car_display", "fuel_type_display", "liters", 
        "source_display",          
        "historical_department_display", "historical_region_display", 
        "employee_display", "approved_display", 
    )
    list_filter = (
        "fuel_type", "source", "approved", "filled_at", "created_at",
        FuelRecordRegionFilter, FuelRecordEmployeeFilter
    )
    search_fields = (
        "car__code", "car__state_number", "car__model",
        "employee__username", "employee__first_name", "employee__last_name",
        "notes", "historical_department", "historical_region__name"
    )
    date_hierarchy = "filled_at"
    autocomplete_fields = ("car", "employee")
    readonly_fields = (
        "created_at", "updated_at", "display_info"
    )
    list_display_links = ("id", "filled_at_formatted")
    list_per_page = 30
    
    actions = [
        "approve_selected",
        "reject_selected", 
        "export_to_csv",
        "export_to_excel",
        "mark_suspicious",
        "sync_to_google_sheets"
    ]
    
    # Настройка отображения детальной формы
    fieldsets = (
        ("Основная информация", {
            "fields": (
                "car", "employee", 
                ("liters", "fuel_type"), 
                "source", "filled_at", "approved",
                "notes", "display_info",
                ("historical_department", "historical_region"),
            )
        }),       
        ("Системная информация", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    # Оптимизация запросов
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'car', 'employee', 'car__region', 'historical_region'
        )
    
    # Кастомные методы отображения
    @admin.display(description="Автомобиль", ordering="car__state_number")
    def car_display(self, obj):
        if obj.car:
            return format_html(
                '<a href="{}?id__exact={}">{}</a>',
                f"/admin/core/car/",
                obj.car.id,
                f"{obj.car.state_number} ({obj.car.model})"
            )
        return "-"
    
    @admin.display(description="Сотрудник", ordering="employee__last_name")
    def employee_display(self, obj):
        if obj.employee:
            return format_html(
                '<a href="{}?id__exact={}">{}</a>',
                f"/admin/core/user/",
                obj.employee.id,
                obj.employee.get_full_name() or obj.employee.username
            )
        return "-"
    
    @admin.display(description="Тип топлива")
    def fuel_type_display(self, obj):
        color = "green" if obj.fuel_type == "GASOLINE" else "orange"
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_fuel_type_display()
        )
    
    @admin.display(description="Способ")
    def source_display(self, obj):
        icons = {
            "CARD": "💳",
            "TGBOT": "🤖", 
            "TRUCK": "🚛"
        }
        return format_html(
            '{} {}',
            icons.get(obj.source, "❓"),
            obj.get_source_display()
        )
    
    @admin.display(description="Дата заправки", ordering="filled_at")
    def filled_at_formatted(self, obj):
        return obj.filled_at.strftime("%d.%m.%Y %H:%M")
    
    @admin.display(description="Статус", boolean=True)
    def approved_display(self, obj):
        return obj.approved

    @admin.display(description="Регион", ordering="historical_region__name")
    def historical_region_display(self, obj):
        if obj.historical_region:
            return obj.historical_region.name
        elif obj.car and obj.car.region:
            return obj.car.region.name
        return "-"
    
    @admin.display(description="Подразделение", ordering="historical_department")
    def historical_department_display(self, obj):
        if obj.historical_department:
            return obj.historical_department
        elif obj.car and obj.car.department:
            return obj.car.department
        return "-"
    
    # Кастомные действия
    @admin.action(description="✅ Подтвердить выбранные")
    def approve_selected(self, request, queryset):
        updated = queryset.update(approved=True)
        self.message_user(
            request, 
            f"Подтверждено {updated} записей о заправках",
            messages.SUCCESS
        )
    
    @admin.action(description="❌ Отклонить выбранные")  
    def reject_selected(self, request, queryset):
        for record in queryset:
            record.reject("Массовое отклонение из админки")
        self.message_user(
            request,
            f"Отклонено {queryset.count()} записей о заправках", 
            messages.SUCCESS
        )
    
    @admin.action(description="🚨 Пометить как подозрительные")
    def mark_suspicious(self, request, queryset):
        suspicious_count = 0
        for record in queryset:
            if record.liters > 200:  # Порог для подозрительных заправок
                record.notes = f"🚨 ПОДОЗРИТЕЛЬНАЯ ЗАПРАВКА\n{record.notes}"
                record.save()
                suspicious_count += 1
        
        self.message_user(
            request,
            f"Помечено {suspicious_count} подозрительных заправок",
            messages.WARNING
        )
    
    # Кастомные views для URL
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'fuel-statistics/',
                self.admin_site.admin_view(self.fuel_statistics_view),
                name='fuel_statistics'
            ),
            path(
                'suspicious-records/',
                self.admin_site.admin_view(self.suspicious_records_view),
                name='suspicious_records'
            ),
            path(
                'export-fuel-report/',
                self.admin_site.admin_view(self.export_fuel_report),
                name='export_fuel_report'
            ),
            path(
                'sync-to-gsheets/',
                self.admin_site.admin_view(self.sync_to_gsheets_view),
                name='sync_to_gsheets'
            ),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        """Добавляем расширенную статистику в список заправок"""
        extra_context = extra_context or {}
        
        # Базовая статистика
        stats = FuelRecord.objects.fuel_statistics()
        
        # Статистика по периодам
        today_stats = FuelRecord.objects.today().fuel_statistics()
        week_stats = FuelRecord.objects.this_week().fuel_statistics()
        month_stats = FuelRecord.objects.this_month().fuel_statistics()
        
        # Статистика по статусам
        approved_stats = FuelRecord.objects.approved().fuel_statistics()
        pending_stats = FuelRecord.objects.pending().fuel_statistics()
        
        # Формируем читаемую статистику
        readable_stats = {
            'total_records': stats['total_records'],
            'total_liters': f"{stats['total_liters'] or 0:.1f} л",
            'avg_liters': f"{stats['avg_liters'] or 0:.1f} л",
            'max_liters': f"{stats['max_liters'] or 0:.1f} л",
            'min_liters': f"{stats['min_liters'] or 0:.1f} л",
            
            'today_records': today_stats['total_records'],
            'today_liters': f"{today_stats['total_liters'] or 0:.1f} л",
            
            'week_records': week_stats['total_records'],
            'week_liters': f"{week_stats['total_liters'] or 0:.1f} л",
            
            'month_records': month_stats['total_records'],
            'month_liters': f"{month_stats['total_liters'] or 0:.1f} л",
            
            'approved_records': approved_stats['total_records'],
            'approved_liters': f"{approved_stats['total_liters'] or 0:.1f} л",
            
            'pending_records': pending_stats['total_records'],
            'pending_liters': f"{pending_stats['total_liters'] or 0:.1f} л",
        }
        
        # Топ автомобилей по расходу
        top_cars = FuelRecord.objects.group_by_car()[:5]
        
        # Топ сотрудников по количеству заправок
        top_employees = FuelRecord.objects.group_by_employee()[:5]
        
        extra_context['stats'] = readable_stats
        extra_context['top_cars'] = top_cars
        extra_context['top_employees'] = top_employees
        
        return super().changelist_view(request, extra_context=extra_context)
    
    def fuel_statistics_view(self, request):
        """Расширенная статистика по заправкам"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Базовая статистика
        total_stats = FuelRecord.objects.fuel_statistics()
        
        # Статистика по источникам
        card_stats = FuelRecord.objects.by_source('CARD').fuel_statistics()
        bot_stats = FuelRecord.objects.by_source('TGBOT').fuel_statistics()
        truck_stats = FuelRecord.objects.by_source('TRUCK').fuel_statistics()
        
        # Статистика за последние 30 дней
        recent_stats = FuelRecord.objects.recent(30).fuel_statistics()
        
        message = format_html(
            """
            <strong>📊 Общая статистика заправок:</strong><br>
            • Всего записей: {}<br>
            • Всего литров: {}<br>
            • Средний объём: {}<br>
            • Максимальная заправка: {}<br>
            • Минимальная заправка: {}<br>
            <br>
            <strong>📈 По источникам:</strong><br>
            • Топливные карты: {} запр., {}<br>
            • Telegram-бот: {} запр., {}<br>
            • Топливозаправщики: {} запр., {}<br>
            <br>
            <strong>📅 За последние 30 дней:</strong><br>
            • Заправок: {}<br>
            • Литров: {}<br>
            <br>            
            """,
            total_stats['total_records'],
            f"{total_stats['total_liters'] or 0:.1f} л",
            f"{total_stats['avg_liters'] or 0:.1f} л",
            f"{total_stats['max_liters'] or 0:.1f} л",
            f"{total_stats['min_liters'] or 0:.1f} л",
            
            card_stats['total_records'],
            f"{card_stats['total_liters'] or 0:.1f} л",
            bot_stats['total_records'],
            f"{bot_stats['total_liters'] or 0:.1f} л",
            truck_stats['total_records'],
            f"{truck_stats['total_liters'] or 0:.1f} л",
            
            recent_stats['total_records'],
            f"{recent_stats['total_liters'] or 0:.1f} л"            
        )
        
        messages.info(request, message)
        return HttpResponseRedirect('../')
    
    def suspicious_records_view(self, request):
        """Поиск подозрительных записей"""
        suspicious = FuelRecord.objects.find_suspicious_records(threshold_liters=200)
        
        if suspicious.exists():
            suspicious_list = []
            for record in suspicious[:15]:  # Ограничиваем вывод
                suspicious_list.append(
                    f"• {record.car.state_number if record.car else 'N/A'}: "
                    f"{record.liters} л ({record.filled_at.strftime('%d.%m.%Y')}) - "
                    f"{record.employee.get_full_name() if record.employee else 'Неизвестно'}"
                )
            
            message = format_html(
                "<strong>🚨 Подозрительные записи (более 200 л):</strong><br>{}",
                "<br>".join(suspicious_list)
            )
            messages.warning(request, message)
        else:
            messages.info(request, "✅ Подозрительных записей не найдено")
        
        return HttpResponseRedirect('../')
    
    @export_action(
        export_method='export_fuel_records_data',
        filename_prefix='fuel_report',
        description='📊 Экспорт отчета о заправках'
    )
    def export_fuel_report(self, request):
        """Экспорт отчета по заправкам"""
        response = ExportService.export_fuel_records_data('xlsx')
        
        # Добавляем информацию об экспорте
        stats = FuelRecord.objects.fuel_statistics()
        messages.success(
            request, 
            f"✅ Успешно экспортировано {stats['total_records']} записей о заправках",
            messages.SUCCESS
        )
        
        return response
    
    @admin.action(description="📊 Синхронизировать с GSheets")
    def sync_to_google_sheets(self, request, queryset):
        """Синхронизация выбранных записей с Google Sheets"""
        try:
            service = FuelRecordGoogleSheetsService()
            record_ids = list(queryset.values_list('id', flat=True))
            
            # Используем async_to_sync для вызова асинхронного метода
            result = async_to_sync(service.sync_multiple_records)(record_ids)
            
            if result['success']:
                if result['synced_count'] == result['total_count']:
                    messages.success(
                        request, 
                        f'✅ Успешно синхронизировано {result["synced_count"]} записей с Google Sheets'
                    )
                else:
                    messages.warning(
                        request,
                        f'⚠️ Синхронизировано {result["synced_count"]} из {result["total_count"]} записей'
                    )
            else:
                messages.error(
                    request,
                    f'❌ Ошибка синхронизации: {result.get("error", "Неизвестная ошибка")}'
                )
                
        except Exception as e:
            messages.error(
                request,
                f'❌ Ошибка синхронизации с Google Sheets: {str(e)}'
            )
    
    def sync_to_gsheets_view(self, request):
        """View для полной синхронизации с Google Sheets"""
        try:
            service = FuelRecordGoogleSheetsService()
            result = async_to_sync(service.sync_all_records)()
            
            if result['success']:
                messages.success(
                    request,
                    f"✅ {result['message']}"
                )
            else:
                messages.error(
                    request,
                    f"❌ Ошибка синхронизации: {result.get('error', 'Неизвестная ошибка')}"
                )
                
        except Exception as e:
            messages.error(
                request,
                f'❌ Ошибка синхронизации: {str(e)}'
            )
        
        return HttpResponseRedirect('../')
    
