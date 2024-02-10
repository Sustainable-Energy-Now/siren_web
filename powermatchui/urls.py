from django.urls import path
from . import views

urlpatterns = [
    path('', views.main, name='main'),  # Maps the root URL to the main view
    path('tableupdate/', views.select_table, name='table_update_page'),
    path('tableupdate/process/', views.table_update_page, name='table_update_page'),
    # Add additional URL patterns here if needed
]
