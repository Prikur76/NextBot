from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path
from django.utils.html import format_html

from core.models import Region
from core.services.region_service import RegionService


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = (
        "name", "short_name",  
        "cars_count", "active_cars_count", 
        "active", "can_archive_display"
    )
    list_filter = ("active",)
    search_fields = ("name", "short_name")
    list_per_page = 30
    
    actions = [
        "archive_selected",
        "restore_selected",
        "archive_empty_regions"
    ]
    
    # Автодополнение для улучшения производительности
    autocomplete_fields = []  # Добавьте связанные поля если есть
    
    # Поля для быстрого редактирования
    list_editable = ("active",)
    
    readonly_fields = ("cars_count_display", "active_cars_count_display", "can_archive_display")
    
    fieldsets = (
        ("Основная информация", {
            "fields": (
                ("active", "can_archive_display"), 
                ("name", "short_name")
            )
        }),
        ("Статистика", {
            "fields": ("cars_count_display", "active_cars_count_display"),
            "classes": ("collapse",)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).with_cars_count()
    
    @admin.display(description="Всего авто", ordering="total_cars")
    def cars_count(self, obj):
        count = getattr(obj, 'total_cars', obj.cars_count)
        return format_html(
            '<a href="{}?region__id__exact={}"><strong>{}</a>',
            f"/admin/core/car/",
            obj.id,
            count
        )
    
    @admin.display(description="Активных авто", ordering="active_cars")
    def active_cars_count(self, obj):
        count = getattr(obj, 'active_cars', obj.active_cars_count)
        if count == 0:
            return format_html('<span style="color: #999;">{}</span>', count)
        return format_html('<span style="color: green;"><strong>{}</strong></span>', count)
    
    @admin.display(description="Можно архивировать", boolean=True)
    def can_archive_display(self, obj):
        return obj.can_be_archived
    
    # Кастомные методы для детального отображения
    def cars_count_display(self, obj):
        return obj.cars_count
    cars_count_display.short_description = "Всего автомобилей"
    
    def active_cars_count_display(self, obj):
        return obj.active_cars_count
    active_cars_count_display.short_description = "Активных автомобилей"
    
    # Кастомные действия
    @admin.action(description="📦 В архив")
    def archive_selected(self, request, queryset):
        """Архивировать выбранные регионы"""
        archived_count = 0
        skipped_count = 0
        
        for region in queryset:
            if region.can_be_archived:
                region.archive("Архивация из админ-панели")
                archived_count += 1
            else:
                skipped_count += 1
        
        if archived_count > 0:
            self.message_user(
                request, 
                f'Успешно архивировано {archived_count} регионов',
                messages.SUCCESS
            )
        
        if skipped_count > 0:
            self.message_user(
                request,
                f'Пропущено {skipped_count} регионов (есть активные автомобили)',
                messages.WARNING
            )
    
    @admin.action(description="🔄 Восстановить")  
    def restore_selected(self, request, queryset):
        """Восстановить выбранные регионы из архива"""
        restored_count = 0
        
        for region in queryset:
            if not region.active:
                region.restore()
                restored_count += 1
        
        if restored_count > 0:
            self.message_user(
                request,
                f'Восстановлено {restored_count} регионов из архива',
                messages.SUCCESS
            )
    
    def archive_empty_regions_view(self, request):
        """View для архивации пустых регионов"""
        from core.services.region_service import RegionService
        
        # Сначала проверяем (dry run)
        dry_run_result = RegionService.archive_empty_regions(dry_run=True)
        
        if dry_run_result['total_found'] == 0:
            messages.info(request, "Не найдено регионов для архивации")
            return HttpResponseRedirect('../')
        
        # Если GET запрос - показываем подтверждение через отдельную страницу
        if request.method == 'GET':
            # Вместо встраивания формы в сообщение, делаем редирект на страницу подтверждения
            request.session['regions_to_archive'] = dry_run_result['regions']
            return HttpResponseRedirect('confirm-archive/')
        
        return HttpResponseRedirect('../')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'archive-empty-regions/',
                self.admin_site.admin_view(self.archive_empty_regions_view),
                name='archive_empty_regions'
            ),
            path(
                'archive-empty-regions/confirm-archive/',
                self.admin_site.admin_view(self.confirm_archive_view),
                name='confirm_archive'
            ),
            path(
                'region-health-report/',
                self.admin_site.admin_view(self.region_health_report),
                name='region_health_report'
            ),
        ]
        return custom_urls + urls
    
    def confirm_archive_view(self, request):
        """Страница подтверждения архивации"""
        from core.services.region_service import RegionService
        
        regions_to_archive = request.session.get('regions_to_archive', [])
        
        if not regions_to_archive:
            messages.error(request, "Нет данных для архивации")
            return HttpResponseRedirect('../')
        
        if request.method == 'POST':
            # Выполняем архивацию
            result = RegionService.archive_empty_regions(dry_run=False)
            
            # Очищаем сессию
            if 'regions_to_archive' in request.session:
                del request.session['regions_to_archive']
            
            messages.success(
                request, 
                f'Успешно архивировано {result["archived"]} регионов без активных автомобилей'
            )
            return HttpResponseRedirect('../')
        
        # Показываем страницу подтверждения с формой
        context = {
            'regions': regions_to_archive,
            'total_regions': len(regions_to_archive),
        }
        
        return render(request, 'admin/core/region/confirm_archive.html', context)
    
    def region_health_report(self, request):
        """Отчет о состоянии регионов"""
        from core.services.region_service import RegionService
        
        report = RegionService.get_region_health_report()
        
        message = format_html(
            """
            <strong>📊 Отчет о состоянии регионов:</strong><br><br>
            
            <strong>Всего регионов: {total_regions}</strong><br>
            • Здоровые регионы (с активными авто): {healthy_count} шт.<br>
            • Пустые активные регионы: {empty_count} шт.<br>
            • Архивные регионы: {archived_count} шт.<br><br>
            
            <strong>🧹 Регионы для очистки ({empty_count} шт.):</strong><br>
            {empty_list}
            """,
            total_regions=report['total_regions'],
            healthy_count=report['healthy_regions']['count'],
            empty_count=report['empty_active_regions']['count'],
            archived_count=report['archived_regions']['count'],
            empty_list="<br>".join([
                f"• {r['name']} (авто: {r['total_cars']}, активных: {r['active_cars']})" 
                for r in report['empty_active_regions']['list']
            ]) if report['empty_active_regions']['list'] else "• Нет регионов для очистки"
        )
        
        messages.info(request, message)
        return HttpResponseRedirect('../')
    
    def changelist_view(self, request, extra_context=None):
        """Добавляем статистику в список регионов"""
        extra_context = extra_context or {}
                
        stats = RegionService.get_regions_statistics()
        health_report = RegionService.get_region_health_report()
        
        # Вычисляем количество автомобилей без региона
        cars_without_region = stats['total_cars'] - stats['cars_with_region']
        
        extra_context['stats'] = {
            'total_regions': stats['total_regions'],
            'active_regions': stats['active_regions'],
            'archived_regions': stats['archived_regions'],
            'empty_regions': health_report['empty_active_regions']['count'],
            'total_cars': stats['total_cars'],
            'cars_with_region': stats['cars_with_region'],
            'cars_without_region': cars_without_region,
        }
        
        return super().changelist_view(request, extra_context=extra_context)
