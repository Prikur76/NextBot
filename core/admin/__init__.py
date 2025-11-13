from .car_admin import CarAdmin     
from .fuelrecord_admin import FuelRecordAdmin  
from .user_admin import UserAdmin
from .region_admin import RegionAdmin
from .zone_admin import ZoneAdmin
from .systemlog_admin import SystemLogAdmin


__all__ = [
    'CarAdmin',
    'RegionAdmin',
    'FuelRecordAdmin',
    'UserAdmin',
    'SystemLogAdmin',
    'ZoneAdmin'
]