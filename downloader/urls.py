from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/video-info/', views.get_video_info, name='get_video_info'),
    path('api/download/', views.download_video, name='download_video'),
]
