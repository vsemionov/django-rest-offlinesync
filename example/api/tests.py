from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status

from .models import Document


class TestDocuments(APITestCase):

    def test_list_success(self):
        user = User.objects.create(username='test', password='test')
        Document.objects.create(user=user, title='test', text='test')

        base_url = reverse('document-list', kwargs={'user_username': user.username})

        response = self.client.get(base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
