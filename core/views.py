from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from django.http import JsonResponse

from core.models import Car, FuelRecord
from core.utils.logging import log_action
from core.utils.network import get_client_ip


def in_group(user, group_names):
    """Проверка принадлежности пользователя хотя бы к одной группе."""
    return user.is_authenticated and user.groups.filter(name__in=group_names).exists()


@login_required
def index(request):
    user = request.user    
    context = {
        "user": user,
        "is_refueler": in_group(user, ["Заправщик", "Менеджер", "Администратор"]),
        "is_manager": in_group(user, ["Менеджер", "Администратор"]),
        "is_admin": in_group(user, ["Администратор"]),
    }
    return render(request, "web/index.html", context)


@login_required
def add_fuel_record(request):
    user = request.user
    ip = get_client_ip(request)
    
    if not in_group(user, ["Заправщик", "Менеджер", "Администратор"]):
        log_action(user, "access_denied", "Попытка добавить заправку без прав", ip)
        raise PermissionDenied("У вас нет прав для добавления заправок")

    if request.method == "POST":
        car_id = request.POST.get("car")
        liters = request.POST.get("liters")
        source = request.POST.get("source")

        if not car_id or not liters:
            messages.error(request, "Все поля обязательны.")
            return redirect("add_fuel")

        try:
            car = Car.objects.get(id=car_id)
            liters = float(liters)
        except (Car.DoesNotExist, ValueError):
            messages.error(request, "Ошибка в данных.")
            return redirect("add_fuel")

        FuelRecord.objects.create(
            car=car,
            employee=user,
            liters=liters,
            fuel_type="GASOLINE",
            source=source,
            filled_at=timezone.now(),
            approved=False,
        )
        messages.success(request, f"✅ Заправка {liters:.1f} л для {car.state_number} добавлена.")
        log_action(user, "add_refuel", f"Заправка {liters:.1f} л для {car.state_number} добавлена", ip)
        return redirect("index")

    cars = Car.objects.filter(is_active=True).order_by("state_number")
    return render(request, "web/add_fuel.html", {"cars": cars})


@login_required
def reports(request):
    user = request.user
    ip = get_client_ip(request)
    
    if not in_group(user, ["Менеджер", "Администратор"]):
        log_action(user, "access_denied", "Попытка открыть отчёты без прав", ip)
        raise PermissionDenied("У вас нет прав для просмотра отчётов")

    log_action(user, "view_report", "Просмотр отчёта по заправкам", ip)
    records = FuelRecord.objects.select_related("car", "employee").order_by("-filled_at")[:30]
    context = []
    for record in records:
        state_number = record.car.state_number
        liters = record.liters
        fuel_type = FuelRecord.FuelType[record.fuel_type.upper()].label
        filled_at = record.filled_at
        employee = record.employee
        source = FuelRecord.SourceFuel[f"{record.source.upper()}"].label

        context.append({
            "state_number": state_number,
            "liters": liters,
            "fuel_type": fuel_type,
            "filled_at": filled_at,
            "employee": employee,
            "source": source,
        })       
        
    return render(request, "web/reports.html", {"records": context})


def health_check(request):
    return JsonResponse({"status": "healthy", "timestamp": timezone.now()})