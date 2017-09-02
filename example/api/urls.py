from django.conf.urls import url, include
from rest_framework_nested import routers

from . import views


root_router = routers.DefaultRouter()
root_router.include_format_suffixes = False
root_router.register(r'users', views.UserViewSet)

user_router = routers.NestedSimpleRouter(root_router, r'users', lookup='user')
user_router.register(r'documents', views.DocumentViewSet)

urlpatterns = [
    url(r'^', include(root_router.urls)),
    url(r'^', include(user_router.urls)),
]
