from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Document


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'date_joined', 'last_login', 'first_name', 'last_name', 'email')


class DocumentSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Document
        fields = ('id', 'user', 'created', 'updated', 'title', 'text')
