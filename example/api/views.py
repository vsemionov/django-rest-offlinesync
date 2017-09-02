from django.contrib.auth.models import User
from rest_framework import viewsets
from rest_offlinesync import limit

from .models import Document
from .serializers import UserSerializer, DocumentSerializer


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'username'
    lookup_value_regex = '[^/]+'
    queryset = User.objects.all()
    serializer_class = UserSerializer


class DocumentViewSet(limit.LimitedNestedSyncedModelMixin,
                      viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

    parent_model = User
    parent_path_model = User
    safe_parent_path = False
    object_filters = {'user_id': 'user_username'}
    parent_filters = {'username': 'user_username'}
    parent_key_filter = 'user_id'
