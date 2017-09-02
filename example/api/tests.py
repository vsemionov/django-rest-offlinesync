from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status

from .models import Document


user = User.objects.create(username='test', password='test')
document = Document.objects.create(user=user, title='test', text='test')


class TestDocuments(APITestCase):

    base_url = reverse('document-list', kwargs={'user_id': user.username})

    def test_list_success(self):
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
