import aiohttp
import asyncio
import json

from asgiref.sync import sync_to_async
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode
from django.conf import settings
from django.core.exceptions import ValidationError

from core.models import Car, Region


class ElementCarClient:
    """Клиент для работы с API 1С:Элемент с фильтрацией архивных автомобилей"""

    def __init__(
        self,
        base_url: str | None = None,
        auth_user: str | None = None,
        auth_password: str | None = None
    ):
        self.base_url = base_url or getattr(settings, 'ELEMENT_API_URL', '')
        self.auth_user = auth_user or getattr(settings, 'ELEMENT_API_USER', '')
        self.auth_password = auth_password or getattr(settings, 'ELEMENT_API_PASSWORD', '')
        self.last_sync = None

        if not all([self.base_url, self.auth_user, self.auth_password]):
            raise RuntimeError("Element API: не заданы URL, пользователь или пароль")

    def _is_archived_car(self, car_data: Dict) -> bool:
        """Проверяет, является ли автомобиль архивным"""
        activity = car_data.get("Activity", True)
        status = car_data.get("Status", "")
        
        is_archived = not activity or status == "АРХИВ"
        
        if is_archived:
            print(f"📦 Пропущен архивный автомобиль: {car_data.get('Number')} "
                  f"(Activity: {activity}, Status: {status})")
        
        return is_archived

    async def sync_with_database(self) -> Dict[str, int]:
        """Синхронизирует данные с базой Django с фильтрацией архивных"""
        try:
            external_cars = await self.fetch_cars()
            stats = {
                'created': 0,
                'updated': 0,
                'archived': 0,
                'errors': 0,
                'regions_created': 0,
                'regions_updated': 0,
                'total_processed': len(external_cars),
                'archived_skipped': 0
            }

            if not external_cars:
                print("⚠️ Нет данных для синхронизации")
                return stats

            # Получаем все существующие автомобили для быстрого поиска
            existing_cars = await self._get_existing_cars_map()
            external_codes = set()

            for item in external_cars:
                try:
                    # Пропускаем архивные автомобили на этапе маппинга
                    if self._is_archived_car(item):
                        stats['archived_skipped'] += 1
                        continue

                    car_data = self._map_external_to_internal(item)
                    if not car_data:
                        stats['errors'] += 1
                        continue

                    external_codes.add(car_data['code'])

                    # Обрабатываем регион
                    if car_data.get('region_name'):
                        region_stats = await self._process_region(car_data['region_name'])
                        stats['regions_created'] += region_stats['created']
                        stats['regions_updated'] += region_stats['updated']

                    if car_data['code'] in existing_cars:
                        stats['updated'] += await self._update_car(
                            existing_cars[car_data['code']], 
                            car_data
                        )
                    else:
                        stats['created'] += await self._create_car(car_data)

                except Exception as e:
                    stats['errors'] += 1
                    print(f"❌ Ошибка обработки автомобиля {item.get('Code', 'N/A')}: {e}")

            # Архивируем автомобили, которых нет в выгрузке
            stats['archived'] += await self._archive_missing_cars(external_codes)

            return stats

        except Exception as e:
            raise RuntimeError(f"Ошибка синхронизации: {e}")

    def _map_external_to_internal(self, external_data: Dict) -> Optional[Dict]:
        """Преобразует данные из внешнего API во внутренний формат"""
        try:
            code = str(external_data.get("Code", "")).strip()
            state_number = str(external_data.get("Number", "")).strip()
            vin = str(external_data.get("VIN", "")).strip()
            model = str(external_data.get("Model", "")).strip()
            
            if not code or not state_number:
                print(f"⚠️ Пропущен автомобиль без кода или госномера: {external_data}")
                return None

            return {
                'code': code,
                'state_number': state_number,
                'model': model,
                'vin': vin,
                'owner_inn': external_data.get("INN"),
                'department': external_data.get("Department", ""),
                'region_name': external_data.get("Region", ""),
                'manufacture_year': self._parse_year(external_data.get("YearCar", 2000)),
                'is_active': external_data.get("Activity", True),
                'status': external_data.get("Status", ""),
            }
        except Exception as e:
            print(f"❌ Ошибка маппинга данных для {external_data.get('Code', 'N/A')}: {e}")
            return None

    @sync_to_async
    def _get_existing_cars_map(self) -> Dict[str, Car]:
        """Возвращает словарь существующих автомобилей по коду (только активных)"""
        cars = Car.objects.available_for_sync()
        return {car.code: car for car in cars}

    @sync_to_async
    def _create_car(self, car_data: Dict) -> int:
        """Создает новый автомобиль с использованием менеджера"""
        try:
            # Сначала пытаемся найти регион по названию
            region = None
            if car_data.get('region_name'):
                region = Region.objects.filter(name=car_data['region_name']).first()

            # Используем кастомный метод менеджера для создания
            car = Car.objects.create_car(
                code=car_data['code'],
                state_number=car_data['state_number'],
                model=car_data.get('model', ''),
                vin=car_data.get('vin'),
                manufacture_year=car_data.get('manufacture_year'),
                owner_inn=car_data.get('owner_inn'),
                department=car_data.get('department'),
                region=region,
                is_active=car_data.get('is_active', True),
                status=car_data.get('status', '')
            )
            
            if car:
                print(f"✅ Создан автомобиль: {car_data['state_number']} ({car_data['code']})")
                return 1
            else:
                print(f"⚠️ Пропущено создание автомобиля: {car_data['code']}")
                return 0
                
        except ValueError as e:
            print(f"❌ Ошибка валидации при создании {car_data['code']}: {e}")
            return 0
        except Exception as e:
            print(f"❌ Неожиданная ошибка создания автомобиля {car_data['code']}: {e}")
            return 0

    @sync_to_async
    def _update_car(self, car: Car, car_data: Dict) -> int:
        """Обновляет существующий автомобиль"""
        try:
            # Если автомобиль стал архивным в 1С, архивируем его
            if not car_data.get('is_active', True) or car_data.get('status') == 'АРХИВ':
                if not car.is_archived:
                    car.archive("Стал архивным в 1С")
                return 0  # Не считаем как обновление

            updated = False
            
            # Обновляем только необходимые поля
            update_fields = []
            
            if car.state_number != car_data['state_number']:
                car.state_number = car_data['state_number']
                update_fields.append('state_number')
                updated = True
                
            if car.model != car_data.get('model', ''):
                car.model = car_data.get('model', '')
                update_fields.append('model')
                updated = True
            
            if car.manufacture_year != car_data.get('manufacture_year', ''):
                car.manufacture_year = car_data.get('manufacture_year', '')
                update_fields.append('manufacture_year')
                updated = True
                
            if car.owner_inn != car_data.get('owner_inn', ''):
                car.owner_inn = car_data.get('owner_inn', '')
                updated = True
                
            if car.department != car_data.get('department'):
                car.department = car_data.get('department')
                updated = True
                
            if car.status != car_data.get('status', ''):
                car.status = car_data.get('status', '')
                updated = True
                
            if car.vin != car_data.get('vin', ''):
                car.vin = car_data.get('vin', '')
                updated = True
                
            # Статус активности
            if car.is_active != car_data.get('is_active', True):
                car.is_active = car_data.get('is_active', True)
                updated = True
            
            # Регион
            if car_data.get('region_name', None):
                region = Region.objects.filter(name=car_data['region_name']).first()
                if car.region != region:
                    car.region = region
                    update_fields.append('region')
                    updated = True
                    
            if updated:
                car.save(update_fields=update_fields)
                print(f"🔄 Обновлен автомобиль: {car_data['state_number']}")
                return 1
            return 0
        except Exception as e:
            print(f"❌ Ошибка обновления автомобиля {car_data['code']}: {e}")
            return 0

    @sync_to_async
    def _archive_missing_cars(self, external_codes: set) -> int:
        """Архивирует активные автомобили, которых нет в выгрузке"""
        try:
            # Находим активные автомобили, которых нет в выгрузке
            missing_cars = Car.objects.active().exclude(code__in=external_codes)
            count = missing_cars.count()
            
            if count > 0:
                # Архивируем отсутствующие автомобили
                for car in missing_cars:
                    car.archive("Отсутствует в выгрузке 1С")
                
                print(f"🔴 Архивировано {count} автомобилей, отсутствующих в 1С")
                
            return count
        except Exception as e:
            print(f"❌ Ошибка архивации автомобилей: {e}")
            return 0

    async def check_availability(self) -> bool:
        """Проверка доступности API"""
        try:
            auth = aiohttp.BasicAuth(self.auth_user, self.auth_password)
            car_url = f"{self.base_url}/Car/v1/Get"
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession() as session:
                async with session.get(car_url, auth=auth, timeout=timeout) as resp:
                    return resp.status == 200
        except Exception as e:
            print(f"❌ API недоступно: {e}")
            return False

    async def get_car_by_number(self, state_number: str) -> Optional[Dict]:
        """Получает данные по конкретному автомобилю по госномеру"""
        try:
            cars = await self.fetch_cars(num=state_number)
            return cars[0] if cars else None
        except Exception as e:
            print(f"❌ Ошибка получения автомобиля {state_number}: {e}")
            return None

    async def get_sample_data(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Получение примеров данных для проверки"""
        try:
            cars = await self.fetch_cars()
            sample = cars[:limit]
            return [
                {
                    "code": car.get("Code"),
                    "vin": car.get("VIN"),
                    "state_number": car.get("Number"),
                    "model": car.get("Model"),
                    "manufacture_year": car.get("YearCar"),
                    "owner_inn": car.get("INN"),
                    "region": car.get("Region"),
                    "department": car.get("Department"),
                    "is_active": car.get("Activity"),
                    "status": car.get("Status"),
                }
                for car in sample
            ]
        except Exception as e:
            print(f"❌ Ошибка получения примеров: {e}")
            return []

    def get_last_sync_time(self) -> Optional[datetime]:
        return self.last_sync