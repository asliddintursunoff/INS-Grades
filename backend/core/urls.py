from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def root_status(request):
    return JsonResponse({
        "service": "INS Grades University Timetable API (Django REST Framework)",
        "status": "online",
        "docs": "/api/",
        "health": "/api/health/"
    })

urlpatterns = [
    path('', root_status),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]
