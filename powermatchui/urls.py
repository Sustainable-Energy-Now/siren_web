from django.urls import path
from .views import batch_views, home_views, merit_order_views, table_update_views

urlpatterns = [
    path('', home_views.main, name='main'),  # Maps the root URL to the main view
    path('merit_order/', merit_order_views.set_merit_order, name='merit_order'),
    path('run_batch/', batch_views.run_batch, name='run_batch'),
    path('tableupdate/', table_update_views.select_table, name='table_update_page'),
    path('tableupdate/process/', table_update_views.table_update_page, name='table_update_page'),
    # Add additional URL patterns here if needed
]