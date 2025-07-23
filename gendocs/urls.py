from django.urls import path
from . import views

app_name = 'gendocs'

urlpatterns = [
    path('', views.index, name='index'),
    path('generate/', views.generate_report, name='generate_report'),
    path('download/<str:doc_type>/', views.download_document, name='download_document'),
    path('api/template-fields/<str:template_name>/', views.get_template_fields, name='template_fields'),
    path('preview/<int:template_id>/', views.template_preview, name='template_preview'),
]