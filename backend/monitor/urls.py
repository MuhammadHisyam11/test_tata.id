from django.urls import path

from . import views

urlpatterns = [
    path("projects", views.project_list),
    path("projects/<str:project_id>", views.project_detail),
]
