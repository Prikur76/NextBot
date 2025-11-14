import aiohttp
import logging
import json
import re

from asgiref.sync import sync_to_async
from datetime import datetime
from typing import List, Optional, Dict, Any
from django.conf import settings

from core.models import Car, Region


logger = logging.getLogger(__name__)


class ElementCarClient:
    """Асинхронный клиент для синхронизации данных автомобилей из 1С:Элемент."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        auth_user: Optional[str] = None,
        auth_password: Optional[str] = None,
    ):
        self.base_url = base_url or getattr(settings, 'ELEMENT_API_URL', '').rstrip('/')
        self.auth_user = auth_user or getattr(settings, 'ELEMENT_API_USER', '')
        self.auth_password = auth_password or getattr(settings, 'ELEMENT_API_PASSWORD', '')
        self.last_sync: Optional[datetime] = None
        self.session: Optional[aiohttp.ClientSession] = None

        if not all([self.base_url, self.auth_user, self.auth_password]):
            raise RuntimeError("Element API: не заданы URL, пользователь или пароль")

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_cars(
        self,
        inn: Optional[str] = None,
        vin: Optional[str] = None,
        sts: Optional[str] = None,
        num: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Получает данные о всех автомобилях из 1С:Элемент с фильтрацией."""
        url = f"{self.base_url}/Car/v1/Get"
        params = {}
        if inn: params['inn'] = inn
        if vin: params['vin'] = vin
        if sts: params['sts'] = sts
        if num: params['num'] = num

        auth = aiohttp.BasicAuth(self.auth_user, self.auth_password)
        timeout = aiohttp.ClientTimeout(total=60)

        try:
            async with self.session.get(url, params=params, auth=auth, timeout=timeout) as response:
                if response.status != 200:
                    logger.error(f"Ошибка API {response.status}: {url} с params {params}")
                    return []

                text = await response.text()
                text = text.strip()

                # Пробуем стандартный JSON
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    # Если JSON обрезан, построчно пытаемся собрать объекты
                    cars = []
                    text_clean = re.sub(r'^\[|\]$', '', text).strip()
                    for line in text_clean.splitlines():
                        line = line.strip().rstrip(",")
                        if line.startswith("{") and line.endswith("}"):
                            try:
                                cars.append(json.loads(line))
                            except Exception:
                                continue
                    logger.warning(f"⚠️ JSON был некорректным, получено объектов: {len(cars)}")
                    return cars

        except Exception as e:
            logger.error(f"Ошибка запроса к API: {e}")
            return []

    # --------------------- Вспомогательные методы ---------------------
    def _is_archived_car(self, car_data: Dict) -> bool:
        activity = car_data.get("Activity", True)
        status = str(car_data.get("Status") or "")
        is_archived = not activity or status.upper() == "АРХИВ"
        if is_archived:
            logger.info(f"📦 Пропущен архивный автомобиль: {car_data.get('Number')} (Status: {status})")
        return is_archived

    @staticmethod
    def _parse_year(year_value) -> int:
        """Парсит YearCar из ISO 8601 или цифр в int. Возвращает 0, если не удалось."""
        if not year_value:
            return 0
        if isinstance(year_value, int):
            return year_value
        if isinstance(year_value, str):
            try:
                dt = datetime.fromisoformat(year_value)
                return dt.year
            except ValueError:
                digits = "".join(filter(str.isdigit, year_value))
                if len(digits) >= 4:
                    return int(digits[:4])
        return 0

    def _map_external_to_internal(self, data: Dict) -> Optional[Dict]:
        try:
            code = str(data.get("Code") or "").strip()
            number = str(data.get("Number") or "").strip()
            if not code or not number:
                logger.warning(f"⚠️ Пропущен автомобиль без кода или госномера: {data}")
                return None

            year = self._parse_year(data.get("YearCar"))
            if year == 0:
                logger.warning(f"⚠️ Некорректный год выпуска для {code}: {data.get('YearCar')}")

            return {
                'code': code,
                'state_number': number,
                'model': str(data.get("Model") or "").strip(),
                'vin': str(data.get("VIN") or "").strip(),
                'owner_inn': str(data.get("INN") or ""),
                'department': str(data.get("Department") or ""),
                'region_name': str(data.get("Region") or ""),
                'manufacture_year': year,
                'is_active': data.get("Activity", True),
                'status': str(data.get("Status") or ""),
            }
        except Exception as e:
            logger.exception(f"Ошибка маппинга данных для {data.get('Code', 'N/A')}: {e}")
            return None

    # --------------------- Работа с БД ---------------------
    async def sync_with_database(self) -> Dict[str, int]:
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
                'archived_skipped': 0,
                'restored': 0,
                'finished_at': datetime.now().isoformat(),
            }

            if not external_cars:
                logger.warning("⚠️ Нет данных для синхронизации")
                return stats

            # Получаем ВСЕ автомобили (включая архивные) для обновления
            existing_cars = await self._get_all_cars_map()
            external_codes = set()

            for item in external_cars:
                try:
                    if self._is_archived_car(item):
                        stats['archived_skipped'] += 1
                        continue

                    car_data = self._map_external_to_internal(item)
                    if not car_data:
                        stats['errors'] += 1
                        continue

                    external_codes.add(car_data['code'])

                    # Обработка региона
                    if car_data.get('region_name'):
                        region_stats = await self._process_region(car_data['region_name'])
                        stats['regions_created'] += region_stats['created']
                        stats['regions_updated'] += region_stats['updated']

                    # Обновление или создание автомобиля
                    if car_data['code'] in existing_cars:
                        update_result = await self._update_car(existing_cars[car_data['code']], car_data)
                        stats['updated'] += update_result
                        # Если автомобиль был восстановлен из архива
                        if update_result == 1 and existing_cars[car_data['code']].is_archived and car_data.get('is_active', True):
                            stats['restored'] += 1
                    else:
                        stats['created'] += await self._create_car(car_data)

                except Exception as e:
                    stats['errors'] += 1
                    logger.exception(f"Ошибка обработки автомобиля {item.get('Code', 'N/A')}: {e}")

            stats['archived'] += await self._archive_missing_cars(external_codes)
            self.last_sync = datetime.now()
            
            # Логируем итоги
            logger.info(f"📊 Синхронизация завершена: "
                       f"создано: {stats['created']}, "
                       f"обновлено: {stats['updated']}, "
                       f"восстановлено: {stats['restored']}, "
                       f"архивировано: {stats['archived']}")
            
            return stats

        except Exception as e:
            raise RuntimeError(f"Ошибка синхронизации: {e}")

    @sync_to_async
    def _get_existing_cars_map(self) -> Dict[str, Car]:
        cars = Car.objects.available_for_sync()
        return {car.code: car for car in cars}

    @sync_to_async
    def _get_all_cars_map(self) -> Dict[str, Car]:
        """Получает все автомобили (включая архивные) для обновления"""
        cars = Car.objects.all()  # Все автомобили, не только активные
        return {car.code: car for car in cars}

    @sync_to_async
    def _process_region(self, name: str) -> Dict[str, int]:
        region, created = Region.objects.get_or_create(name=name)
        return {'created': int(created), 'updated': int(not created)}

    @sync_to_async
    def _create_car(self, data: Dict) -> int:
        try:
            region = Region.objects.filter(name=data['region_name']).first() if data.get('region_name') else None
            
            # Проверяем, существует ли автомобиль с таким кодом (включая архивные)
            existing_car = Car.objects.filter(code=data['code']).first()
            if existing_car:
                logger.info(f"🔄 Автомобиль с кодом {data['code']} уже существует, обновляем...")
                # Вызываем синхронный метод обновления
                return self._update_car_sync(existing_car, data)
            
            # Подготавливаем данные
            car_data = {
                'code': data['code'],
                'state_number': data['state_number'],
                'model': data['model'],
                'vin': data.get('vin') or '',
                'manufacture_year': data['manufacture_year'],
                'owner_inn': data.get('owner_inn') or '',
                'department': data.get('department') or '',
                'region': region,
                'is_active': data.get('is_active', True),
                'status': data.get('status') or '',
            }
            
            # Создаем автомобиль
            Car.objects.create(**car_data)
            logger.info(f"✅ Создан автомобиль: {data['state_number']} ({data['code']})")
            return 1
            
        except Exception as e:
            logger.exception(f"Ошибка создания автомобиля {data.get('code', 'N/A')}: {e}")
            return 0

    def _update_car_sync(self, car: Car, data: Dict) -> int:
        """Синхронная версия метода обновления для использования в _create_car"""
        try:
            # Проверяем, нужно ли архивировать автомобиль
            if not data.get('is_active', True) or (data.get('status') or "").upper() == 'АРХИВ':
                if not car.is_archived:
                    car.archive("Стал архивным в 1С")
                    logger.info(f"📦 Автомобиль {car.code} перемещен в архив")
                return 0

            # Восстанавливаем из архива, если нужно
            if car.is_archived and data.get('is_active', True) and (data.get('status') or "").upper() != 'АРХИВ':
                car.restore_from_archive()
                logger.info(f"🔄 Автомобиль {car.code} восстановлен из архива")

            updated = False
            update_fields = []
            
            # Сравниваем и обновляем поля
            fields_to_check = ['state_number', 'model', 'vin', 'manufacture_year', 'owner_inn', 'department', 'status', 'is_active']
            
            for field in fields_to_check:
                new_value = data.get(field, getattr(car, field))
                
                # Обработка None значений для строковых полей
                if field in ['vin', 'owner_inn', 'department', 'status', 'state_number', 'model']:
                    new_value = new_value or ""
                
                current_value = getattr(car, field)
                
                if current_value != new_value:
                    setattr(car, field, new_value)
                    updated = True
                    update_fields.append(field)

            # Обновление региона
            if data.get('region_name'):
                region = Region.objects.filter(name=data['region_name']).first()
                if car.region != region:
                    car.region = region
                    updated = True
                    update_fields.append('region')

            if updated:
                car.save(update_fields=update_fields)
                logger.info(f"🔄 Обновлен автомобиль {car.state_number}: {', '.join(update_fields)}")
                return 1
            
            return 0
            
        except Exception as e:
            logger.exception(f"Ошибка обновления автомобиля {data.get('code', 'N/A')}: {e}")
            return 0
    
    @sync_to_async
    def _update_car(self, car: Car, data: Dict) -> int:
        """Асинхронная версия метода обновления"""
        return self._update_car_sync(car, data)

    @sync_to_async
    def _archive_missing_cars(self, external_codes: set) -> int:
        try:
            # Архивируем только активные автомобили, которых нет в выгрузке
            missing = Car.objects.active().exclude(code__in=external_codes)
            count = missing.count()
            
            for car in missing:
                car.archive("Отсутствует в выгрузке 1С")
                
            if count:
                logger.warning(f"🔴 Архивировано {count} автомобилей, отсутствующих в 1С")
            
            return count
        except Exception as e:
            logger.exception(f"Ошибка архивации автомобилей: {e}")
            return 0

    async def check_availability(self) -> bool:
        try:
            url = f"{self.base_url}/Car/v1/Get"
            auth = aiohttp.BasicAuth(self.auth_user, self.auth_password)
            async with self.session.get(url, auth=auth, timeout=30) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"❌ API недоступно: {e}")
            return False

    async def get_sample_data(self, limit: int = 3) -> List[Dict[str, Any]]:
        try:
            cars = await self.fetch_cars()
            return cars[:limit]
        except Exception as e:
            logger.exception(f"Ошибка получения примеров: {e}")
            return []

    def get_last_sync_time(self) -> Optional[datetime]:
        return self.last_sync
