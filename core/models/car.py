from datetime import timedelta
from django.db import models
from django.db.models import Q, Count, Avg, Sum, QuerySet, ExpressionWrapper, FloatField, Max, Min
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class CarQuerySet(QuerySet):
    """Кастомный QuerySet для модели Car"""
    
    def active(self):
        """Только активные автомобили (не архивные и Activity=True)"""
        return self.filter(is_active=True).exclude(status="АРХИВ")
    
    def archived(self):
        """Архивные автомобили"""
        return self.filter(Q(status="АРХИВ") | Q(is_active=False))
    
    def available_for_sync(self):
        """Автомобили, которые должны синхронизироваться с 1С"""
        return self.active()
    
    def by_region(self, region):
        """Автомобили по региону"""
        if isinstance(region, models.Model):
            return self.filter(region=region)
        elif isinstance(region, int):
            return self.filter(region_id=region)
        else:
            return self.filter(region__name=region)
    
    def by_regions(self, regions):
        """Автомобили по списку регионов"""
        return self.filter(region__in=regions)
    
    def by_department(self, department):
        """Автомобили по подразделению"""
        return self.filter(department__icontains=department)
    
    def by_owner_inn(self, inn):
        """Автомобили по ИНН владельца"""
        return self.filter(owner_inn=inn)
    
    def by_status(self, status):
        """Автомобили по статусу"""
        return self.filter(status=status)
    
    def by_state_number(self, state_number):
        """Поиск по госномеру (точное совпадение)"""
        return self.filter(state_number=state_number)
    
    def search_by_state_number(self, state_number_part):
        """Поиск по части госномера"""
        return self.filter(state_number__icontains=state_number_part)
    
    def by_vin(self, vin):
        """Поиск по VIN"""
        return self.filter(vin=vin)
    
    def by_model(self, model):
        """Поиск по модели (частичное совпадение)"""
        return self.filter(model__icontains=model)
    
    def by_manufacture_year(self, year):
        """Автомобили определенного года выпуска"""
        return self.filter(manufacture_year=year)
    
    def newer_than(self, year):
        """Автомобили новее указанного года"""
        return self.filter(manufacture_year__gte=year)
    
    def older_than(self, year):
        """Автомобили старше указанного года"""
        return self.filter(manufacture_year__lte=year)
    
    def young_cars(self, max_age=5):
        """Молодые автомобили (до N лет)"""
        current_year = timezone.now().year
        min_year = current_year - max_age
        return self.filter(manufacture_year__gte=min_year)
    
    def old_cars(self, min_age=10):
        """Старые автомобили (старше N лет)"""
        current_year = timezone.now().year
        max_year = current_year - min_age
        return self.filter(manufacture_year__lte=max_year)    
    
    def with_region(self):
        """Автомобили с указанным регионом"""
        return self.filter(region__isnull=False)
    
    def without_region(self):
        """Автомобили без региона"""
        return self.filter(region__isnull=True)
    
    def with_fuel_records(self):
        """Автомобили, у которых есть записи о заправках"""
        return self.filter(fuel_records__isnull=False).distinct()
    
    def without_fuel_records(self):
        """Автомобили без записей о заправках"""
        return self.filter(fuel_records__isnull=True)
    
    def recently_updated(self, days=7):
        """Автомобили, обновленные за последние N дней"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(updated_at__gte=cutoff_date)
    
    def recently_created(self, days=7):
        """Автомобили, созданные за последние N дней"""
        cutdown_date= timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutdown_date)
    
    def by_zone(self, zone):
        """Автомобили, принадлежащие зоне"""
        return self.filter(region__zones=zone)
    
    def with_fuel_statistics(self):
        """Автомобили со статистикой по заправкам"""
        return self.annotate(
            total_fuel_records=Count('fuel_records'),
            total_liters=Sum('fuel_records__liters'),
            avg_liters=Avg('fuel_records__liters'),
            last_refuel_date=models.Max('fuel_records__filled_at')
        )
    
    def top_fuel_consumers(self, limit=10):
        """Топ автомобилей по расходу топлива"""
        return self.with_fuel_statistics().filter(
            total_liters__isnull=False
        ).order_by('-total_liters')[:limit]
    
    def never_refueled(self):
        """Автомобили, которые никогда не заправлялись"""
        return self.without_fuel_records()
    
    def with_recent_refuels(self, days=30):
        """Автомобили с заправками за последние N дней"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(
            fuel_records__filled_at__gte=cutoff_date
        ).distinct()
    
    def available_for_refuel(self):
        """Автомобили, доступные для заправки (активные и с регионом)"""
        return self.active().with_region()
    
    def with_age(self):
        """Добавляет вычисляемое поле возраста автомобиля"""
        current_year = timezone.now().year
        return self.annotate(
            age=ExpressionWrapper(
                current_year - models.F('manufacture_year'),
                output_field=FloatField()
            )
        )
        
    def age_distribution(self):
        """Распределение автомобилей по возрастным группам"""
        current_year = timezone.now().year
        
        return self.filter(manufacture_year__isnull=False).annotate(
            age=current_year - models.F('manufacture_year')
        ).values('age').annotate(
            count=Count('id')
        ).order_by('age')

    
    def search(self, query):
        """Универсальный поиск по различным полям"""
        if not query:
            return self.all()
        
        return self.filter(
            Q(code__icontains=query) |
            Q(state_number__icontains=query) |
            Q(vin__icontains=query) |
            Q(model__icontains=query) |
            Q(department__icontains=query) |
            Q(region__name__icontains=query) |
            Q(status__icontains=query)
        ).distinct()
    
    def statistics_summary(self):
        """Сводная статистика по автомобилям с возрастом"""
        current_year = timezone.now().year
        
        # Базовая статистика
        stats = self.aggregate(
            total_cars=Count('id'),
            active_cars=Count('id', filter=Q(is_active=True)),
            cars_with_region=Count('id', filter=Q(region__isnull=False)),
            avg_manufacture_year=Avg('manufacture_year'),
            unique_departments=Count('department', distinct=True),
            unique_regions=Count('region', distinct=True)
        )
        
        # Добавляем статистику по возрасту
        age_stats = self.filter(manufacture_year__isnull=False).aggregate(
            avg_age=Avg(current_year - models.F('manufacture_year')),
            min_age=Min(current_year - models.F('manufacture_year')),
            max_age=Max(current_year - models.F('manufacture_year')),
            newest_car_year=Max('manufacture_year'),
            oldest_car_year=Min('manufacture_year')
        )
        
        # Объединяем статистики
        stats.update(age_stats)
        
        return stats
    
    def find_duplicates(self):
        """Находит потенциальные конфликты идентификаторов среди активных"""
        state_number_duplicates = self.active().values('state_number').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        vin_duplicates = self.active().exclude(vin='').values('vin').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        return {
            'state_number_duplicates': list(state_number_duplicates),
            'vin_duplicates': list(vin_duplicates)
        }
    
    def create_car(self, code, state_number, model, **extra_fields):
        """
        Создание автомобиля с проверкой на архивность и дубликаты.
        Должен вызываться через Car.objects.create_car()
        """
        # Проверяем, не пытаемся ли создать архивный автомобиль
        if extra_fields.get('status') == 'АРХИВ' or not extra_fields.get('is_active', True):
            print(f"⚠️ Пропущено создание архивного автомобиля: {code}")
            return None
            
        if not code or not state_number:
            raise ValueError("Код и госномер обязательны")
        
        # Проверяем дубликаты только среди активных автомобилей
        if self.active().filter(code=code).exists():
            raise ValueError(f"Активный автомобиль с кодом {code} уже существует")
        
        if self.active().filter(state_number=state_number).exists():
            raise ValueError(f"Активный автомобиль с госномером {state_number} уже существует")
        
        # Проверяем уникальность VIN среди активных
        vin = extra_fields.get('vin')
        if vin and vin.strip():
            if self.active().filter(vin=vin).exists():
                raise ValueError(f"Активный автомобиль с VIN {vin} уже существует")
        
        return self.create(
            code=code,
            state_number=state_number,
            model=model,
            **extra_fields
        )


class Car(models.Model):
    """
    Автомобиль компании.
    """
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Код автомобиля")
    vin = models.CharField(
        max_length=17,
        blank=True,
        default="",
        verbose_name="VIN")
    state_number = models.CharField(
        max_length=20,
        verbose_name="Гос. номер")
    model = models.CharField(
        max_length=100,
        verbose_name="Марка, модель")
    manufacture_year = models.PositiveSmallIntegerField(
        default=2000,
        verbose_name="Год выпуска")    
    owner_inn = models.CharField(
        max_length=17,
        default="",
        verbose_name="ИНН владельца")
    department = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="подразделение")
    region = models.ForeignKey(
        "core.Region",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cars",
        verbose_name="Регион")
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен")
    status = models.CharField(
        max_length=50,
        default="",
        verbose_name="Статус"        
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания")
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления")
    
    objects = CarQuerySet.as_manager()

    class Meta:
        db_table = "cars"
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["state_number"]),
            models.Index(fields=["is_active", "status"])                        
        ]
        verbose_name = "Автомобиль"
        verbose_name_plural = "Автомобили"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} ({self.state_number})"

    @property
    def is_archived(self):
        """Является ли автомобиль архивным"""
        return self.status == "АРХИВ" or not self.is_active
    
    @property
    def display_name(self):
        """Отображаемое имя с указанием архивности"""
        base_name = f"{self.state_number} - {self.model}"
        if self.is_archived:
            return f"{base_name} [АРХИВ]"
        return base_name
    
    def archive(self, reason="Архивация через систему"):
        """Перевод автомобиля в архив"""
        self.status = "АРХИВ"
        self.is_active = False
        self.save(update_fields=['status', 'is_active', 'updated_at'])
        
    def restore_from_archive(self):
        """Восстановление автомобиля из архива"""
        self.status = "АКТИВЕН"
        self.is_active = True
        self.save(update_fields=['status', 'is_active', 'updated_at'])
            
    def safe_delete(self):
        """Безопасное удаление - перевод в архив вместо физического удаления"""
        self.archive("Безопасное удаление")
