from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Image, Rating, LogEntry, LogType
from django.core.files.uploadedfile import SimpleUploadedFile
import json

User = get_user_model()

class RateAppTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.username = "testuser"
        self.email = "test@example.com"
        self.password = "password123"
        self.user = User.objects.create_user(
            username=self.username,
            email=self.email,
            password=self.password
        )

    def test_unauthenticated_redirects(self):
        """Unauthenticated page requests should redirect to login."""
        for url in ['/cabinet/', '/chat/']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login/', response.url)

    def test_authenticated_page_redirects(self):
        """Authenticated users visiting login/register pages should be redirected to lenta."""
        refresh = RefreshToken.for_user(self.user)
        self.client.cookies['accessToken'] = str(refresh.access_token)

        for url in ['/login/', '/register/']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/lenta/users/lenta/', response.url)

    def test_cookie_jwt_middleware_auth(self):
        """Test CookieJWTMiddleware authenticates requests with valid JWT cookie."""
        refresh = RefreshToken.for_user(self.user)
        self.client.cookies['accessToken'] = str(refresh.access_token)

        response = self.client.get('/cabinet/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'const USERNAME = "{self.username}";')

    def test_logout_clears_cookies(self):
        """Test logging out deletes simplejwt cookies."""
        refresh = RefreshToken.for_user(self.user)
        self.client.cookies['accessToken'] = str(refresh.access_token)
        self.client.cookies['refreshToken'] = str(refresh)

        response = self.client.post('/api/logout/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('accessToken', response.cookies)
        self.assertEqual(response.cookies['accessToken'].value, '')
        self.assertEqual(response.cookies['refreshToken'].value, '')

    def test_photo_upload_limit_exactly_2(self):
        """Uploading images should delete previous user images, enforcing 2-image limit."""
        refresh = RefreshToken.for_user(self.user)
        self.client.cookies['accessToken'] = str(refresh.access_token)

        # Create two pre-existing images
        Image.objects.create(user=self.user, url="/media/old1.jpg")
        Image.objects.create(user=self.user, url="/media/old2.jpg")
        self.assertEqual(Image.objects.filter(user=self.user).count(), 2)

        # Mock files for uploading
        front_file = SimpleUploadedFile("front.jpg", b"front_binary_content", content_type="image/jpeg")
        profile_file = SimpleUploadedFile("profile.jpg", b"profile_binary_content", content_type="image/jpeg")

        response = self.client.post('/api/cabinet/add_image/', {
            'user_id': self.user.id,
            'front': front_file,
            'profile': profile_file
        })
        self.assertEqual(response.status_code, 200)

        # Check that old images are deleted and only exactly 2 new images remain
        self.assertEqual(Image.objects.filter(user=self.user).count(), 2)
        images = Image.objects.filter(user=self.user)
        self.assertNotIn("/media/old1.jpg", [img.url for img in images])

    def test_feed_loop_prevention(self):
        """Test get_random_user returns 404 instead of looping infinitely if no users left."""
        refresh = RefreshToken.for_user(self.user)
        self.client.cookies['accessToken'] = str(refresh.access_token)

        response = self.client.get('/api/users/get_random_user/')
        self.assertEqual(response.status_code, 404)
        self.assertIn("No unrated users left", response.json()['error'])

    def test_rating_creation_and_stats(self):
        """Rating a user should create a Rating record, a LogEntry, and display it in stats."""
        target_user = User.objects.create_user(username="target", email="target@example.com", password="password")
        
        refresh = RefreshToken.for_user(self.user)
        self.client.cookies['accessToken'] = str(refresh.access_token)

        response = self.client.post(f'/api/users/{target_user.id}/add_rating/', {
            'rate': 12
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)

        # Verify database structures
        rating = Rating.objects.filter(user=target_user, from_user=self.user).first()
        self.assertIsNotNone(rating)
        self.assertEqual(rating.value, 12.0)

        log = LogEntry.objects.filter(user=self.user, log_type=LogType.RATE.value).first()
        self.assertIsNotNone(log)

        # Verify stats endpoint
        stats_response = self.client.get(f'/api/cabinet/{target_user.id}/ratings/')
        self.assertEqual(stats_response.status_code, 200)
        self.assertEqual(stats_response.json()[0]['value'], 12.0)
