from django.db import models
from rest_offlinesync.models import TrackedModel


class Document(TrackedModel):
    user = models.ForeignKey('auth.User', to_field='username')

    title = models.CharField(max_length=128)
    text = models.TextField(max_length=2048)
