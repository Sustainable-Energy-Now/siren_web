from django.urls import path
from .views import home_views, table_update_views

urlpatterns = [
    path('', home_views.main, name='main'),  # Maps the root URL to the main view
    path('tableupdate/', table_update_views.select_table, name='table_update_page'),
    path('tableupdate/process/', table_update_views.table_update_page, name='table_update_page'),
    # Add additional URL patterns here if needed
]
