# from django.contrib import admin
# from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
# from django.http import HttpResponseRedirect
# from django.shortcuts import redirect, render
# from django.urls import path
# from django.contrib import messages
# from django.utils.html import format_html
# from django.db.models import Q, Count, Avg, F
# from django.utils import timezone

# from .models import User, Region, Zone, Car, FuelRecord, SystemLog
# from core.admin_actions import export_action
# from core.services.car_service import CarService
# from core.services.export_service import ExportService
# from core.services.region_service import RegionService


# @admin.register(User)
# class UserAdmin(DjangoUserAdmin):
#     list_display = (
#         "username", "get_full_name", "phone", 
#         "telegram_id", "is_active", "is_staff", 
#         "zone", "region"
#     )
#     list_filter = ("is_active", "zone", "region", "groups")
#     search_fields = ("username", "telegram_id", "first_name", "last_name")
#     filter_horizontal = ("groups", "user_permissions")
#     fieldsets = (
#         (None, {"fields": ("username", "password")}),
#         ("Персональные данные", {"fields": ("first_name", "last_name", "phone", "telegram_id", "region", "zone")}),
#         ("Права доступа", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
#     )
#     list_per_page = 20
    
#     @admin.display(description="ФИО")
#     def get_full_name(self, obj):
#         if obj.first_name and obj.last_name:
#             return f"{obj.first_name} {obj.last_name}"
#         return obj.username
    

# @admin.register(Region)
# class RegionAdmin(admin.ModelAdmin):
#     list_display = (
#         "name", "short_name",  
#         "cars_count", "active_cars_count", 
#         "active", "can_archive_display"
#     )
#     list_filter = ("active",)
#     search_fields = ("name", "short_name")
#     list_per_page = 20
#     actions = ["archive_selected", "restore_selected", "archive_empty_regions"]
    
#     # Автодополнение для улучшения производительности
#     autocomplete_fields = []  # Добавьте связанные поля если есть
    
#     # Поля для быстрого редактирования
#     list_editable = ("active",)
    
#     readonly_fields = ("cars_count_display", "active_cars_count_display", "can_archive_display")
    
#     fieldsets = (
#         ("Основная информация", {
#             "fields": ("name", "short_name", "active")
#         }),
#         ("Статистика", {
#             "fields": ("cars_count_display", "active_cars_count_display", "can_archive_display"),
#             "classes": ("collapse",)
#         }),
#     )
    
#     def get_queryset(self, request):
#         return super().get_queryset(request).with_cars_count()
    
#     @admin.display(description="Всего авто", ordering="total_cars")
#     def cars_count(self, obj):
#         count = getattr(obj, 'total_cars', obj.cars_count)
#         return format_html(
#             '<a href="{}?region__id__exact={}"><strong>{}</a>',
#             f"/admin/core/car/",
#             obj.id,
#             count
#         )
    
#     @admin.display(description="Активных авто", ordering="active_cars")
#     def active_cars_count(self, obj):
#         count = getattr(obj, 'active_cars', obj.active_cars_count)
#         if count == 0:
#             return format_html('<span style="color: #999;">{}</span>', count)
#         return format_html('<span style="color: green;"><strong>{}</strong></span>', count)
    
#     @admin.display(description="Можно архивировать", boolean=True)
#     def can_archive_display(self, obj):
#         return obj.can_be_archived
    
#     # Кастомные методы для детального отображения
#     def cars_count_display(self, obj):
#         return obj.cars_count
#     cars_count_display.short_description = "Всего автомобилей"
    
#     def active_cars_count_display(self, obj):
#         return obj.active_cars_count
#     active_cars_count_display.short_description = "Активных автомобилей"
    
#     # Кастомные действия    
#     def archive_selected(self, request, queryset):
#         """Архивировать выбранные регионы"""
#         archived_count = 0
#         skipped_count = 0
        
#         for region in queryset:
#             if region.can_be_archived:
#                 region.archive("Архивация из админ-панели")
#                 archived_count += 1
#             else:
#                 skipped_count += 1
        
#         if archived_count > 0:
#             self.message_user(
#                 request, 
#                 f'Успешно архивировано {archived_count} регионов',
#                 messages.SUCCESS
#             )
        
#         if skipped_count > 0:
#             self.message_user(
#                 request,
#                 f'Пропущено {skipped_count} регионов (есть активные автомобили)',
#                 messages.WARNING
#             )
    
#     archive_selected.short_description = "📦 Архивировать выбранные регионы"
    
#     def restore_selected(self, request, queryset):
#         """Восстановить выбранные регионы из архива"""
#         restored_count = 0
        
#         for region in queryset:
#             if not region.active:
#                 region.restore()
#                 restored_count += 1
        
#         if restored_count > 0:
#             self.message_user(
#                 request,
#                 f'Восстановлено {restored_count} регионов из архива',
#                 messages.SUCCESS
#             )
    
#     restore_selected.short_description = "🔄 Восстановить выбранные регионы"
    
#     def archive_empty_regions(self, request, queryset):
#         """Архивировать регионы без активных автомобилей"""
#         from core.services.region_service import RegionService
        
#         result = RegionService.archive_empty_regions()
        
#         if result['archived'] > 0:
#             self.message_user(
#                 request,
#                 f'Автоматически архивировано {result["archived"]} регионов без активных автомобилей',
#                 messages.SUCCESS
#             )
            
#             # Показываем список архивированных регионов
#             region_names = [r['name'] for r in result['regions'][:10]]  # Первые 10
#             details = ", ".join(region_names)
#             if len(result['regions']) > 10:
#                 details += f" и еще {len(result['regions']) - 10} регионов"
                
#             self.message_user(
#                 request,
#                 f"Архивированные регионы: {details}",
#                 messages.INFO
#             )
#         else:
#             self.message_user(
#                 request,
#                 "Не найдено регионов для архивации (все регионы имеют активные автомобили)",
#                 messages.INFO
#             )
    
#     archive_empty_regions.short_description = "🧹 Архивировать пустые регионы"
    
#     def archive_empty_regions_view(self, request):
#         """View для архивации пустых регионов"""
#         from core.services.region_service import RegionService
        
#         # Сначала проверяем (dry run)
#         dry_run_result = RegionService.archive_empty_regions(dry_run=True)
        
#         if dry_run_result['total_found'] == 0:
#             messages.info(request, "Не найдено регионов для архивации")
#             return HttpResponseRedirect('../')
        
#         # Если GET запрос - показываем подтверждение через отдельную страницу
#         if request.method == 'GET':
#             # Вместо встраивания формы в сообщение, делаем редирект на страницу подтверждения
#             request.session['regions_to_archive'] = dry_run_result['regions']
#             return HttpResponseRedirect('confirm-archive/')
        
#         return HttpResponseRedirect('../')
    
#     def get_urls(self):
#         urls = super().get_urls()
#         custom_urls = [
#             path(
#                 'archive-empty-regions/',
#                 self.admin_site.admin_view(self.archive_empty_regions_view),
#                 name='archive_empty_regions'
#             ),
#             path(
#                 'archive-empty-regions/confirm-archive/',
#                 self.admin_site.admin_view(self.confirm_archive_view),
#                 name='confirm_archive'
#             ),
#             path(
#                 'region-health-report/',
#                 self.admin_site.admin_view(self.region_health_report),
#                 name='region_health_report'
#             ),
#         ]
#         return custom_urls + urls
    
#     def confirm_archive_view(self, request):
#         """Страница подтверждения архивации"""
#         from core.services.region_service import RegionService
        
#         regions_to_archive = request.session.get('regions_to_archive', [])
        
#         if not regions_to_archive:
#             messages.error(request, "Нет данных для архивации")
#             return HttpResponseRedirect('../')
        
#         if request.method == 'POST':
#             # Выполняем архивацию
#             result = RegionService.archive_empty_regions(dry_run=False)
            
#             # Очищаем сессию
#             if 'regions_to_archive' in request.session:
#                 del request.session['regions_to_archive']
            
#             messages.success(
#                 request, 
#                 f'Успешно архивировано {result["archived"]} регионов без активных автомобилей'
#             )
#             return HttpResponseRedirect('../')
        
#         # Показываем страницу подтверждения с формой
#         context = {
#             'regions': regions_to_archive,
#             'total_regions': len(regions_to_archive),
#         }
        
#         return render(request, 'admin/core/region/confirm_archive.html', context)
    
#     def region_health_report(self, request):
#         """Отчет о состоянии регионов"""
#         from core.services.region_service import RegionService
        
#         report = RegionService.get_region_health_report()
        
#         message = format_html(
#             """
#             <strong>📊 Отчет о состоянии регионов:</strong><br><br>
            
#             <strong>Всего регионов: {total_regions}</strong><br>
#             • Здоровые регионы (с активными авто): {healthy_count} шт.<br>
#             • Пустые активные регионы: {empty_count} шт.<br>
#             • Архивные регионы: {archived_count} шт.<br><br>
            
#             <strong>🧹 Регионы для очистки ({empty_count} шт.):</strong><br>
#             {empty_list}
#             """,
#             total_regions=report['total_regions'],
#             healthy_count=report['healthy_regions']['count'],
#             empty_count=report['empty_active_regions']['count'],
#             archived_count=report['archived_regions']['count'],
#             empty_list="<br>".join([
#                 f"• {r['name']} (авто: {r['total_cars']}, активных: {r['active_cars']})" 
#                 for r in report['empty_active_regions']['list']
#             ]) if report['empty_active_regions']['list'] else "• Нет регионов для очистки"
#         )
        
#         messages.info(request, message)
#         return HttpResponseRedirect('../')
    
#     def changelist_view(self, request, extra_context=None):
#         """Добавляем статистику в список регионов"""
#         extra_context = extra_context or {}
                
#         stats = RegionService.get_regions_statistics()
#         health_report = RegionService.get_region_health_report()
        
#         # Вычисляем количество автомобилей без региона
#         cars_without_region = stats['total_cars'] - stats['cars_with_region']
        
#         extra_context['stats'] = {
#             'total_regions': stats['total_regions'],
#             'active_regions': stats['active_regions'],
#             'archived_regions': stats['archived_regions'],
#             'empty_regions': health_report['empty_active_regions']['count'],
#             'total_cars': stats['total_cars'],
#             'cars_with_region': stats['cars_with_region'],
#             'cars_without_region': cars_without_region,
#         }
        
#         return super().changelist_view(request, extra_context=extra_context)


# @admin.register(Zone)
# class ZoneAdmin(admin.ModelAdmin):
#     list_display = ("name", "code", "regions_count", "cars_count", "active")
#     list_filter = ("active",)
#     search_fields = ("name", "code")
#     filter_horizontal = ("regions",)
#     list_per_page = 25
        
#     @admin.display(description="Регионов")
#     def regions_count(self, obj):
#         return obj.regions.count()
    
#     @admin.display(description="Автомобилей")
#     def cars_count(self, obj):
#         count = Car.objects.active().filter(region__zones=obj).count()
#         return format_html(
#             '<a href="{}?region__zones__id__exact={}"><strong>{}</a>',
#             f"/admin/core/car/",
#             obj.id,
#             count
#         )
       

# @admin.register(Car)
# class CarAdmin(admin.ModelAdmin):
#     list_display = (
#         "code", "model", "vin", "state_number", 
#         "manufacture_year", "department_short", "region_link", 
#         "car_age", "is_active_display", "status_display", "created_at"
#     )
#     list_filter = (
#         "is_active", "region", "department", 
#         "manufacture_year", "created_at"
#     )
#     search_fields = (
#         "code", "state_number", "model", "vin", 
#         "owner_inn", "region__name", "department"
#     )
    
#     readonly_fields = ("created_at", "updated_at", "display_name")
#     list_per_page = 25
    
#     actions = [
#         "export_selected_cars", 
#         "archive_selected", 
#         "activate_selected", 
#         "find_duplicates_action"
#     ]
    
#     # Автодополнение для улучшения производительности
#     autocomplete_fields = ["region"]
   
#     # Настройка отображения детальной формы
#     fieldsets = (
#         ("Основная информация", {
#             "fields": (
#                 "code", "state_number", "vin", "model", 
#                 "manufacture_year", "display_name"
#             )
#         }),
#         ("Владелец и подразделение", {
#             "fields": ("owner_inn", "department", "region")
#         }),
#         ("Статус и активность", {
#             "fields": ("is_active", "status")
#         }),
#         ("Системная информация", {
#             "fields": ("created_at", "updated_at"),
#             "classes": ("collapse",)
#         }),
#     )
    
#     def get_urls(self):
#         urls = super().get_urls()
#         custom_urls = [
#             path(
#                 'archive-old-cars/',
#                 self.admin_site.admin_view(self.archive_old_cars),
#                 name='archive_old_cars'
#             ),
#             path(
#                 'find-duplicates/',
#                 self.admin_site.admin_view(self.find_duplicates),
#                 name='find_duplicates'
#             ),
#             path(
#                 'cars-statistics/',
#                 self.admin_site.admin_view(self.cars_statistics),
#                 name='cars_statistics'
#             ),
#             path(
#                 'export-all-cars/',
#                 self.admin_site.admin_view(self.export_all_cars),
#                 name='export_cars'
#             ),
#         ]
#         return custom_urls + urls
    
#     def changelist_view(self, request, extra_context=None):
#         """Добавляем расширенную статистику в список автомобилей"""
#         extra_context = extra_context or {}
        
#         # Базовая статистика
#         stats = Car.objects.statistics_summary()
        
#         # Статистика по возрасту
#         age_stats = CarService.get_age_statistics()
        
#         # Формируем читаемую статистику с правильными ключами
#         readable_stats = {
#             'total_cars': stats['total_cars'],
#             'active_cars': stats['active_cars'],
#             'cars_with_region': stats['cars_with_region'],
#             'avg_age': f"{stats.get('avg_age', 0):.1f} лет",
#             'age_range': f"{stats.get('min_age', 0)}-{stats.get('max_age', 0)} лет",
#             'year_range': f"{stats.get('oldest_car_year', 0)}-{stats.get('newest_car_year', 0)}",
#         }
        
#         # Создаем словарь с читаемыми названиями групп для шаблона
#         age_distribution_display = {
#             '0_3_years': age_stats['age_ranges']['0_3_years'],
#             '4_7_years': age_stats['age_ranges']['4_7_years'],
#             '8_12_years': age_stats['age_ranges']['8_12_years'],
#             '13_plus_years': age_stats['age_ranges']['13_plus_years'],
#         }
        
#         extra_context['stats'] = readable_stats
#         extra_context['age_distribution'] = age_distribution_display
        
#         return super().changelist_view(request, extra_context=extra_context)
    
#     # Кастомные методы отображения
#     @admin.display(description="Регион")
#     def region_link(self, obj):
#         if obj.region:
#             return format_html(
#                 '<a href="{}?id__exact={}"><strong>{}</a>',
#                 f"/admin/core/region/",
#                 obj.region.id,
#                 obj.region.name
#             )
#         return "-"
    
#     @admin.display(description="Подразделение")
#     def department_short(self, obj):
#         if obj.department:
#             return obj.department[:20] + "..." if len(obj.department) > 20 else obj.department
#         return "-"
    
#     @admin.display(description="Возраст", ordering="manufacture_year")
#     def car_age(self, obj):
#         if not obj.manufacture_year:
#             return "-"
        
#         current_year = timezone.now().year
#         age = current_year - obj.manufacture_year
        
#         # Цветовое кодирование по возрасту
#         if age <= 3:
#             color = "green"
#             badge = "🟢"
#         elif age <= 7:
#             color = "orange"
#             badge = "🟡"
#         else:
#             color = "red"
#             badge = "🔴"
        
#         return format_html(
#             '<span style="color: {};">{}{} {}</span>',
#             color,
#             badge,
#             age,
#             "лет" if age >= 5 else "года" if age >= 2 else "год"
#         )
    
#     @admin.display(description="Активен", boolean=True)
#     def is_active_display(self, obj):
#         return obj.is_active and obj.status != "АРХИВ"
    
#     @admin.display(description="Статус")
#     def status_display(self, obj):
#         if obj.status == "АРХИВ" or not obj.is_active:
#             return format_html('<span style="color: #999;">{}</span>', "АРХИВ")
#         elif obj.status:
#             return obj.status
#         else:
#             return "АКТИВЕН"
        
#     # Кастомные действия
#     @admin.action(description="Архивировать")
#     def archive_selected(self, request, queryset):
#         """Архивировать выбранные автомобили"""
#         car_ids = list(queryset.values_list('id', flat=True))
        
#         archived_count = CarService.bulk_archive_cars(
#             car_ids,
#             reason=f"Архивация из админ-панели пользователем {request.user.username}"
#         )
        
#         self.message_user(
#             request, 
#             f'Успешно архивировано {archived_count} автомобилей',
#             messages.SUCCESS
#         )
    
#     @admin.action(description="Восстановить")    
#     def activate_selected(self, request, queryset):
#         """Активировать выбранные автомобили"""
#         activated_count = 0
#         for car in queryset:
#             if car.is_archived:
#                 car.restore_from_archive()
#                 activated_count += 1
        
#         self.message_user(
#             request,
#             f'Активировано {activated_count} автомобилей',
#             messages.SUCCESS
#         )
        
#     @admin.action(description="Поиск дубликатов")
#     def find_duplicates_action(self, request, queryset):
#         """Найти дубликаты среди выбранных автомобилей"""
#         car_ids = list(queryset.values_list('id', flat=True))
#         duplicates_info = []
        
#         # Проверяем дубликаты госномеров
#         state_duplicates = Car.objects.filter(
#             id__in=car_ids
#         ).values('state_number').annotate(
#             count=Count('id')
#         ).filter(count__gt=1)
        
#         for dup in state_duplicates:
#             duplicates_info.append(f"Госномер {dup['state_number']}: {dup['count']} шт.")
        
#         # Проверяем дубликаты VIN
#         vin_duplicates = Car.objects.filter(
#             id__in=car_ids
#         ).exclude(vin='').values('vin').annotate(
#             count=Count('id')
#         ).filter(count__gt=1)
        
#         for dup in vin_duplicates:
#             duplicates_info.append(f"VIN {dup['vin']}: {dup['count']} шт.")
        
#         if duplicates_info:
#             message = "Найдены дубликаты:\n" + "\n".join(duplicates_info)
#             self.message_user(request, message, messages.WARNING)
#         else:
#             self.message_user(request, "Дубликатов не найдено", messages.INFO)
     
#     @export_action(
#         export_method='export_selected_cars',
#         filename_prefix='selected_cars',
#         description='Экспорт выбранных (Excel)'
#     )
#     def export_selected_cars(self, request, queryset):
#         """Экспорт выбранных автомобилей"""
#         pass  # Тело функции не нужно, вся логика в декораторе
                       
#     # Кастомные views для URL
#     def archive_old_cars(self, request):
#         """Архивация старых автомобилей"""
#         if not request.user.has_perm('core.change_car'):
#             messages.error(request, 'Недостаточно прав')
#             return HttpResponseRedirect('../../')
        
#         try:
#             # Автомобили старше 15 лет
#             from datetime import datetime
#             current_year = datetime.now().year
#             old_year = current_year - 15
            
#             old_cars = Car.objects.active().filter(manufacture_year__lte=old_year)
#             car_ids = list(old_cars.values_list('id', flat=True))
            
#             archived_count = CarService.bulk_archive_cars(
#                 car_ids,
#                 reason="Автоматическая архивация старых автомобилей"
#             )
            
#             messages.success(
#                 request, 
#                 f'Архивировано {archived_count} автомобилей старше {old_year} года'
#             )
            
#         except Exception as e:
#             messages.error(request, f'Ошибка архивации: {str(e)}')
        
#         return HttpResponseRedirect('../../')
    
#     def find_duplicates(self, request):
#         """Поиск дубликатов во всей базе"""
#         duplicates = Car.objects.find_duplicates()
        
#         state_duplicates = duplicates['state_number_duplicates']
#         vin_duplicates = duplicates['vin_duplicates']
        
#         if state_duplicates or vin_duplicates:
#             message = "Найдены дубликаты:\n"
            
#             if state_duplicates:
#                 message += "\nГосномера:\n"
#                 for dup in state_duplicates:
#                     message += f"- {dup['state_number']}: {dup['count']} автомобилей\n"
            
#             if vin_duplicates:
#                 message += "\nVIN:\n"
#                 for dup in vin_duplicates:
#                     message += f"- {dup['vin']}: {dup['count']} автомобилей\n"
            
#             messages.warning(request, message)
#         else:
#             messages.info(request, "Дубликатов не найдено")
        
#         return HttpResponseRedirect('../../')
    
#     def cars_statistics(self, request):
#         """Расширенная статистика по автомобилям"""
#         age_report = CarService.get_fleet_age_report()
        
#         # Используем читаемые названия для сообщения
#         message = format_html(
#             """
#             <strong>📊 Статистика автопарка:</strong><br>
#             • Всего автомобилей: {}<br>
#             • Активных: {}<br>
#             • Средний возраст: {}<br>
#             • Диапазон возрастов: {}<br>
#             • Диапазон годов выпуска: {}<br>
#             <br>
#             <strong>📈 Распределение по возрастам:</strong><br>
#             • 0-3 года: {} шт.<br>
#             • 4-7 лет: {} шт.<br>
#             • 8-12 лет: {} шт.<br>
#             • 13+ лет: {} шт.
#             """,
#             age_report['total_cars'],
#             age_report['active_cars'],
#             age_report['avg_age'],
#             age_report['age_range'],
#             age_report['year_range'],
#             age_report['age_distribution']['0_3_years'],
#             age_report['age_distribution']['4_7_years'],
#             age_report['age_distribution']['8_12_years'],
#             age_report['age_distribution']['13_plus_years']
#         )
        
#         messages.info(request, message)
#         return HttpResponseRedirect('../../')

#     def export_all_cars(self, request):
#         """Экспорт всех автомобилей"""
#         return ExportService.export_cars_data('xlsx')    

#     # Переопределяем queryset для исключения архивных по умолчанию
#     def get_queryset(self, request):
#         qs = super().get_queryset(request)
#         # Показываем архивные только если явно отфильтровано
#         if 'is_active' not in request.GET and 'status' not in request.GET:
#             qs = qs.active()
#         return qs.select_related('region')
    
#     # Настройка прав для действий
#     def get_actions(self, request):
#         """Права на действия"""

#         actions = super().get_actions(request)

#         if not request.user.has_perm('core.change_car'):
#             if 'archive_selected' in actions:
#                 del actions['archive_selected']
#             if 'activate_selected' in actions:
#                 del actions['activate_selected']
#             del actions['delete_selected']
#         return actions


# # Кастомные фильтры для FuelRecord
# class FuelRecordRegionFilter(admin.SimpleListFilter):
#     title = 'Регион'
#     parameter_name = 'region'
    
#     def lookups(self, request, model_admin):
#         regions = Region.objects.all().values_list('id', 'name')
#         return regions
    
#     def queryset(self, request, queryset):
#         if self.value():
#             return queryset.filter(car__region_id=self.value())
#         return queryset


# class FuelRecordEmployeeFilter(admin.SimpleListFilter):
#     title = 'Сотрудник (зона)'
#     parameter_name = 'employee_zone'
    
#     def lookups(self, request, model_admin):
#         zones = Zone.objects.all().values_list('id', 'name')
#         return zones
    
#     def queryset(self, request, queryset):
#         if self.value():
#             return queryset.filter(employee__zone_id=self.value())
#         return queryset


# @admin.register(FuelRecord)
# class FuelRecordAdmin(admin.ModelAdmin):
#     list_display = (
#         "id", "filled_at_formatted", 
#         "car_display", "fuel_type_display", "liters", 
#         "source_display",          
#         "historical_department_display", "historical_region_display", 
#         "employee_display", "approved_display", 
#     )
#     list_filter = (
#         "fuel_type", "source", "approved", "filled_at", "created_at",
#         FuelRecordRegionFilter, FuelRecordEmployeeFilter
#     )
#     search_fields = (
#         "car__code", "car__state_number", "car__model",
#         "employee__username", "employee__first_name", "employee__last_name",
#         "notes", "historical_department", "historical_region__name"
#     )
#     date_hierarchy = "filled_at"
#     autocomplete_fields = ("car", "employee")
#     readonly_fields = (
#         "created_at", "updated_at", "display_info"
#     )
#     list_display_links = ("id", "filled_at_formatted")
#     list_per_page = 25
    
#     actions = [
#         "approve_selected",
#         "reject_selected", 
#         "export_to_csv",
#         "export_to_excel",
#         "mark_suspicious"
#     ]
    
#     # Настройка отображения детальной формы
#     fieldsets = (
#         ("Основная информация", {
#             "fields": (
#                 "car", "employee", "liters", "fuel_type", 
#                 "source", "filled_at", "approved"
#             )
#         }),
#         ("Данные об авто", {
#             "fields": ("historical_region", "historical_department"),
#             "classes": ("collapse",)
#         }),
#         ("Дополнительная информация", {
#             "fields": ("notes", "display_info"),  #  "efficiency_badge"
#             "classes": ("collapse",)
#         }),
#         ("Системная информация", {
#             "fields": ("created_at", "updated_at"),
#             "classes": ("collapse",)
#         }),
#     )

#     # Оптимизация запросов
#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related(
#             'car', 'employee', 'car__region', 'historical_region'
#         )
    
#     # Кастомные методы отображения
#     @admin.display(description="Автомобиль", ordering="car__state_number")
#     def car_display(self, obj):
#         if obj.car:
#             return format_html(
#                 '<a href="{}?id__exact={}">{}</a>',
#                 f"/admin/core/car/",
#                 obj.car.id,
#                 f"{obj.car.state_number} ({obj.car.model})"
#             )
#         return "-"
    
#     @admin.display(description="Сотрудник", ordering="employee__last_name")
#     def employee_display(self, obj):
#         if obj.employee:
#             return format_html(
#                 '<a href="{}?id__exact={}">{}</a>',
#                 f"/admin/core/user/",
#                 obj.employee.id,
#                 obj.employee.get_full_name() or obj.employee.username
#             )
#         return "-"
    
#     @admin.display(description="Тип топлива")
#     def fuel_type_display(self, obj):
#         color = "green" if obj.fuel_type == "GASOLINE" else "orange"
#         return format_html(
#             '<span style="color: {};">{}</span>',
#             color,
#             obj.get_fuel_type_display()
#         )
    
#     @admin.display(description="Способ")
#     def source_display(self, obj):
#         icons = {
#             "CARD": "💳",
#             "TGBOT": "🤖", 
#             "TRUCK": "🚛"
#         }
#         return format_html(
#             '{} {}',
#             icons.get(obj.source, "❓"),
#             obj.get_source_display()
#         )
    
#     @admin.display(description="Дата заправки", ordering="filled_at")
#     def filled_at_formatted(self, obj):
#         return obj.filled_at.strftime("%d.%m.%Y %H:%M")
    
#     @admin.display(description="Статус", boolean=True)
#     def approved_display(self, obj):
#         return obj.approved

#     @admin.display(description="Регион", ordering="historical_region__name")
#     def historical_region_display(self, obj):
#         if obj.historical_region:
#             return obj.historical_region.name
#         elif obj.car and obj.car.region:
#             return obj.car.region.name
#         return "-"
    
#     @admin.display(description="Подразделение", ordering="historical_department")
#     def historical_department_display(self, obj):
#         if obj.historical_department:
#             return obj.historical_department
#         elif obj.car and obj.car.department:
#             return obj.car.department
#         return "-"
    
#     # Кастомные действия
#     @admin.action(description="✅ Подтвердить выбранные")
#     def approve_selected(self, request, queryset):
#         updated = queryset.update(approved=True)
#         self.message_user(
#             request, 
#             f"Подтверждено {updated} записей о заправках",
#             messages.SUCCESS
#         )
    
#     @admin.action(description="❌ Отклонить выбранные")  
#     def reject_selected(self, request, queryset):
#         for record in queryset:
#             record.reject("Массовое отклонение из админки")
#         self.message_user(
#             request,
#             f"Отклонено {queryset.count()} записей о заправках", 
#             messages.SUCCESS
#         )
    
#     @admin.action(description="🚨 Пометить как подозрительные")
#     def mark_suspicious(self, request, queryset):
#         suspicious_count = 0
#         for record in queryset:
#             if record.liters > 200:  # Порог для подозрительных заправок
#                 record.notes = f"🚨 ПОДОЗРИТЕЛЬНАЯ ЗАПРАВКА\n{record.notes}"
#                 record.save()
#                 suspicious_count += 1
        
#         self.message_user(
#             request,
#             f"Помечено {suspicious_count} подозрительных заправок",
#             messages.WARNING
#         )
    
#     # Кастомные views для URL
#     def get_urls(self):
#         urls = super().get_urls()
#         custom_urls = [
#             path(
#                 'fuel-statistics/',
#                 self.admin_site.admin_view(self.fuel_statistics_view),
#                 name='fuel_statistics'
#             ),
#             path(
#                 'suspicious-records/',
#                 self.admin_site.admin_view(self.suspicious_records_view),
#                 name='suspicious_records'
#             ),
#             path(
#                 'export-fuel-report/',
#                 self.admin_site.admin_view(self.export_fuel_report),
#                 name='export_fuel_report'
#             ),
#         ]
#         return custom_urls + urls
    
#     def changelist_view(self, request, extra_context=None):
#         """Добавляем расширенную статистику в список заправок"""
#         extra_context = extra_context or {}
        
#         # Базовая статистика
#         stats = FuelRecord.objects.fuel_statistics()
        
#         # Статистика по периодам
#         today_stats = FuelRecord.objects.today().fuel_statistics()
#         week_stats = FuelRecord.objects.this_week().fuel_statistics()
#         month_stats = FuelRecord.objects.this_month().fuel_statistics()
        
#         # Статистика по статусам
#         approved_stats = FuelRecord.objects.approved().fuel_statistics()
#         pending_stats = FuelRecord.objects.pending().fuel_statistics()
        
#         # Формируем читаемую статистику
#         readable_stats = {
#             'total_records': stats['total_records'],
#             'total_liters': f"{stats['total_liters'] or 0:.1f} л",
#             'avg_liters': f"{stats['avg_liters'] or 0:.1f} л",
#             'max_liters': f"{stats['max_liters'] or 0:.1f} л",
#             'min_liters': f"{stats['min_liters'] or 0:.1f} л",
            
#             'today_records': today_stats['total_records'],
#             'today_liters': f"{today_stats['total_liters'] or 0:.1f} л",
            
#             'week_records': week_stats['total_records'],
#             'week_liters': f"{week_stats['total_liters'] or 0:.1f} л",
            
#             'month_records': month_stats['total_records'],
#             'month_liters': f"{month_stats['total_liters'] or 0:.1f} л",
            
#             'approved_records': approved_stats['total_records'],
#             'approved_liters': f"{approved_stats['total_liters'] or 0:.1f} л",
            
#             'pending_records': pending_stats['total_records'],
#             'pending_liters': f"{pending_stats['total_liters'] or 0:.1f} л",
#         }
        
#         # Топ автомобилей по расходу
#         top_cars = FuelRecord.objects.group_by_car()[:5]
        
#         # Топ сотрудников по количеству заправок
#         top_employees = FuelRecord.objects.group_by_employee()[:5]
        
#         extra_context['stats'] = readable_stats
#         extra_context['top_cars'] = top_cars
#         extra_context['top_employees'] = top_employees
        
#         return super().changelist_view(request, extra_context=extra_context)
    
#     def fuel_statistics_view(self, request):
#         """Расширенная статистика по заправкам"""
#         from django.utils import timezone
#         from datetime import timedelta
        
#         # Базовая статистика
#         total_stats = FuelRecord.objects.fuel_statistics()
        
#         # Статистика по источникам
#         card_stats = FuelRecord.objects.by_source('CARD').fuel_statistics()
#         bot_stats = FuelRecord.objects.by_source('TGBOT').fuel_statistics()
#         truck_stats = FuelRecord.objects.by_source('TRUCK').fuel_statistics()
        
#         # Статистика за последние 30 дней
#         recent_stats = FuelRecord.objects.recent(30).fuel_statistics()
        
#         message = format_html(
#             """
#             <strong>📊 Общая статистика заправок:</strong><br>
#             • Всего записей: {}<br>
#             • Всего литров: {}<br>
#             • Средний объём: {}<br>
#             • Максимальная заправка: {}<br>
#             • Минимальная заправка: {}<br>
#             <br>
#             <strong>📈 По источникам:</strong><br>
#             • Топливные карты: {} запр., {}<br>
#             • Telegram-бот: {} запр., {}<br>
#             • Топливозаправщики: {} запр., {}<br>
#             <br>
#             <strong>📅 За последние 30 дней:</strong><br>
#             • Заправок: {}<br>
#             • Литров: {}<br>
#             <br>            
#             """,
#             total_stats['total_records'],
#             f"{total_stats['total_liters'] or 0:.1f} л",
#             f"{total_stats['avg_liters'] or 0:.1f} л",
#             f"{total_stats['max_liters'] or 0:.1f} л",
#             f"{total_stats['min_liters'] or 0:.1f} л",
            
#             card_stats['total_records'],
#             f"{card_stats['total_liters'] or 0:.1f} л",
#             bot_stats['total_records'],
#             f"{bot_stats['total_liters'] or 0:.1f} л",
#             truck_stats['total_records'],
#             f"{truck_stats['total_liters'] or 0:.1f} л",
            
#             recent_stats['total_records'],
#             f"{recent_stats['total_liters'] or 0:.1f} л"            
#         )
        
#         messages.info(request, message)
#         return HttpResponseRedirect('../')
    
#     def suspicious_records_view(self, request):
#         """Поиск подозрительных записей"""
#         suspicious = FuelRecord.objects.find_suspicious_records(threshold_liters=200)
        
#         if suspicious.exists():
#             suspicious_list = []
#             for record in suspicious[:15]:  # Ограничиваем вывод
#                 suspicious_list.append(
#                     f"• {record.car.state_number if record.car else 'N/A'}: "
#                     f"{record.liters} л ({record.filled_at.strftime('%d.%m.%Y')}) - "
#                     f"{record.employee.get_full_name() if record.employee else 'Неизвестно'}"
#                 )
            
#             message = format_html(
#                 "<strong>🚨 Подозрительные записи (более 200 л):</strong><br>{}",
#                 "<br>".join(suspicious_list)
#             )
#             messages.warning(request, message)
#         else:
#             messages.info(request, "✅ Подозрительных записей не найдено")
        
#         return HttpResponseRedirect('../')
    
#     @export_action(
#         export_method='export_fuel_records_data',
#         filename_prefix='fuel_report',
#         description='📊 Экспорт отчета о заправках'
#     )
#     def export_fuel_report(self, request):
#         """Экспорт отчета по заправкам"""
#         response = ExportService.export_fuel_records_data('xlsx')
        
#         # Добавляем информацию об экспорте
#         stats = FuelRecord.objects.fuel_statistics()
#         messages.success(
#             request, 
#             f"✅ Успешно экспортировано {stats['total_records']} записей о заправках",
#             messages.SUCCESS
#         )
        
#         return response


# @admin.register(SystemLog)
# class SystemLogAdmin(admin.ModelAdmin):
#     list_display = ("created_at", "user", "action", "ip_address", "short_details")
#     list_filter = ("action", "created_at")
#     search_fields = ("user__username", "details", "ip_address")
#     readonly_fields = ("created_at", "user", "action", "details", "ip_address")
#     list_per_page = 50
#     date_hierarchy = "created_at"

#     @admin.display(description="Подробности")
#     def short_details(self, obj):
#         return (obj.details[:70] + "...") if len(obj.details) > 70 else obj.details
    
#     # Запрещаем создание/редактирование логов через админку
#     def has_add_permission(self, request):
#         return False
    
#     def has_change_permission(self, request, obj=None):
#         return False
    
#     # Оптимизация запросов
#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related('user')
    