"""
URL configuration for siren_web project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from .views import home_views, config_views, help_views, reference_views

urlpatterns = [
    path('', home_views.home_view, name='home'),
    path('release-notes/', home_views.release_notes, name='release_notes'),
    path("", include("powermapui.urls")),
    path("", include("powermatchui.urls")),
    path("", include("powerplotui.urls")),
    path('references', reference_views.reference_list, name='reference_list'),
    path('references/add/', reference_views.reference_create, name='reference_create'),
    path('references/<int:pk>/', reference_views.reference_detail, name='reference_detail'),
    path('references/<int:pk>/edit/', reference_views.reference_update, name='reference_update'),
    path('references/<int:pk>/delete/', reference_views.reference_delete, name='reference_delete'),
    path('references/api/search/', reference_views.reference_search_api, name='reference_search_api'),
    path('gendocs/', include('gendocs.urls')),
    path('config_views/', config_views.edit_config, name='edit_config'),
    path('generate-help/', help_views.generate_help_html, name='generate_help_html'),
    path('help/', help_views.display_help_html, name='display_help_html'),
    path('help/edit/', help_views.edit_help_markdown, name='edit_help_markdown'),
    path('download/', help_views.download_help_html, name='download_help_html'),
    path("admin/", admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
]
urlpatterns += staticfiles_urlpatterns()