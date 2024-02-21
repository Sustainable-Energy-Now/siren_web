# urls.py
from django.urls import path
from .views import batch_views, home_views, optimisation_views, merit_order_views, table_update_views, technologies_views
from django.views.generic import TemplateView

urlpatterns = [
    path('', home_views.home, name='home'),  # Maps the root URL to the main view
    path('merit_order/', merit_order_views.set_merit_order, name='merit_order'),
    path('batch/', batch_views.setup_batch, name='setup_batch'),
    path('optimisation/', optimisation_views.run_optimisation, name='run_optimisation'),
    path('technologies/', technologies_views.run_technologies, name='run_technologies'),
    path('tableupdate/', table_update_views.select_table, name='table_update'),
    path('tableupdate/process/', table_update_views.update_table, name='table_update_process'),
    # Add additional URL patterns here if needed
]