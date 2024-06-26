""" Tests for the users API """
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

CREATE_USER_URL = reverse('users:register')
TOKEN_URL = reverse('users:token')
ME_URL = reverse('users:me')
CHANGE_PASSWORD_URL = reverse('users:change_password')
DELETE_ME_URL = reverse('users:delete_me')


def create_user(**params):
    """ Create and return a new user """
    return get_user_model().objects.create_user(**params)


class PublicUsersAPITests(TestCase):
    """ Test the public features of the users API """

    def setUp(self):
        self.client = APIClient()

    def test_create_user_success(self):
        """ Test creating a user is successful """
        payload = {
            'email': 'testuser@example.com',
            'password': 'Test1234',
            'password_confirm': 'Test1234',
            'name': 'Test Name'
        }

        res = self.client.post(CREATE_USER_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        user = get_user_model().objects.get(email=payload['email'])
        self.assertTrue(user.check_password(payload['password']))
        self.assertNotIn('password', res.data)
        self.assertNotIn('password_confirm', res.data)

    def test_user_with_email_exists_error(self):
        """ Test an error returned if user with email exists """
        payload = {
            'email': 'test@example.com',
            'password': 'Test1234',
            'name': 'Test Name'
        }
        create_user(**payload)

        res = self.client.post(CREATE_USER_URL, **payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_password_doesnt_meet_requiremenets(self):
        """ Test an error is returned when password haven't met requirements """
        passwords = [
            'testtest',
            'Testtest',
            'test1234',
        ]
        payload = {
            'email': 'test@example.com',
            'name': 'Test User'
        }

        for password in passwords:
            payload.update({'password': password})
            res = self.client.post(CREATE_USER_URL, payload)
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            user_exists = get_user_model().objects.filter(email=payload['email']).exists()
            self.assertFalse(user_exists)

    def test_create_token_for_user(self):
        """ Test generating token for valid credentials """
        user_details = {
            'email': 'test@example.com',
            'password': 'Test1234'
        }
        create_user(**user_details)

        res = self.client.post(TOKEN_URL, {'email': user_details['email'], 'password': user_details['password']})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('token', res.data)

    def test_create_token_bad_credentials(self):
        """ Test API returns error if credential are invalid """
        create_user(email='test@example.com', password='Test1234')

        res = self.client.post(TOKEN_URL, {'email': 'different@example.com', 'password': 'Badpass1'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('token', res.data)

    def test_create_token_blank_password(self):
        """ Test posting a blank password returns an error """
        payload = {'email': 'test@example.com', 'password': ''}
        res = self.client.post(TOKEN_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('token', res.data)

    def test_retrieve_user_unauthorized(self):
        """ Test authentication is required for users """
        res = self.client.get(ME_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_user_unauthorized(self):
        """ Test deleting the user is allowed only to authenticated users """
        res = self.client.delete(DELETE_ME_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateUsersAPITests(TestCase):
    """ Test API requests that require authentication """

    def setUp(self):
        # Sprawdzić czy działa bez hasła w sumie, skoro password=None
        self.user = create_user(email='test@example.com', password='Test1234', name='Test Name')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_profile_success(self):
        """ Test retrieving profile for logged in user """
        res = self.client.get(ME_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['name'], self.user.name)
        self.assertEqual(res.data['email'], self.user.email)

    def test_post_me_not_allowed(self):
        """ POST requests are not allowed to ME endpoint """
        res = self.client.post(ME_URL, {})
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_me_not_allowed(self):
        """ POST requests are not allowed to ME endpoint """
        res = self.client.delete(ME_URL, {})
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_update_user(self):
        """ Test updating safe fields in user profile for the authenticated user """
        payload = {'name': 'New Test Name'}
        res = self.client.patch(ME_URL, payload)
        self.user.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(payload['name'], self.user.name)
        self.assertNotIn('password', res.data)

    def test_change_password(self):
        """ Test changing passwords works and no password in response """
        newpass = 'NewPassTest12345'
        payload = {
            'password': newpass,
            'password_confirm': newpass
        }
        res = self.client.patch(CHANGE_PASSWORD_URL, payload)
        self.user.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(self.user.check_password(payload['password']))
        self.assertNotIn('password', res.data)

    def test_delete_me(self):
        """ Test deleting the user for the authenticated user """
        new_user = create_user(email='new_test_user@example.com', password='Password1234')
        self.client.force_authenticate(user=new_user)
        res = self.client.delete(DELETE_ME_URL, data={'password': 'Password1234'})

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        with self.assertRaises(ObjectDoesNotExist):
            get_user_model().objects.get(id=new_user.id)

    def test_delete_me_requires_password(self):
        """ Test deleting an authenticated user requires password is provided """
        res = self.client.delete(DELETE_ME_URL, data={'password': ''})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_delete_me_wrong_password(self):
        """ Test providing wrong password raises an error """
        new_user = create_user(email='new_test_user@example.com', password='GoodPassword1234')
        self.client.force_authenticate(user=new_user)
        res = self.client.delete(DELETE_ME_URL, data={'password': 'WrongPassword1234'})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(get_user_model().objects.filter(id=new_user.id).exists())
