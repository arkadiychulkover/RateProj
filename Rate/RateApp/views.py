import json

from django.http import HttpResponseNotFound, JsonResponse, HttpResponse, HttpResponseBadRequest, \
    HttpResponseNotAllowed, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from django.shortcuts import render, redirect
from abc import ABC, abstractmethod
from rest_framework import viewsets, status
from .models import *
from .models import UserSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import datetime
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import User, Message, FriendRequest, Rating


class CookieJWTAuthentication(JWTAuthentication):
    """Кастомная проверка токена из кук для DRF ViewSets"""

    def authenticate(self, request):
        raw_token = request.COOKIES.get('accessToken')
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token


def login_page(request):
    return render(request, 'login.html')


def register_page(request):
    return render(request, 'register.html')


def _get_ws_token(request):
    """Extract JWT access token from cookie to pass to WebSocket URL."""
    return request.COOKIES.get('accessToken', '')


def chat_home(request):
    if not request.user.is_authenticated:
        return redirect('/login/')
    return render(request, 'chat.html', {
        'chat_with_id': 'null',
        'ws_token': _get_ws_token(request),
    })


def chat_with(request, user_id):
    if not request.user.is_authenticated:
        return redirect('/login/')
    return render(request, 'chat.html', {
        'chat_with_id': user_id,
        'ws_token': _get_ws_token(request),
    })


# ─── Auth API ─────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def api_register(request):
    username = request.data.get('username', '').strip()
    email = request.data.get('email', '').strip()
    password = request.data.get('password', '').strip()

    if not username or not email or not password:
        return Response({'error': 'Все поля обязательны'}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({'error': 'Такой логин уже занят'}, status=400)

    if User.objects.filter(email=email).exists():
        return Response({'error': 'Такой email уже используется'}, status=400)

    # Создаем пользователя
    user = User.objects.create_user(username=username, email=email, password=password)

    # Автоматически авторизуем сессию в Django
    login(request, user)

    # Генерируем JWT токены
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    response = Response({
        'success': True,
        'user_id': user.id,
        'username': user.username,
    }, status=201)

    # Записываем токены в безопасные куки
    response.set_cookie(
        key='accessToken',
        value=access_token,
        httponly=True,  # Защита от кражи через JS (XSS уязвимости)
        samesite='Lax',  # Защита от CSRF
        secure=False,  # Поставь True, когда проект будет на продакшене с HTTPS
        max_age=86400  # Время жизни: 1 день
    )
    response.set_cookie(
        key='refreshToken',
        value=refresh_token,
        httponly=True,
        samesite='Lax',
        secure=False,
        max_age=604800  # Время жизни: 7 дней
    )
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '').strip()

    if not username or not password:
        return Response({'error': 'Заполните все поля'}, status=400)

    user = authenticate(username=username, password=password)
    if user:
        if not user.is_active:
            return Response({'error': 'Аккаунт заблокирован'}, status=403)

        # Авторизуем сессию в Django
        login(request, user)

        # Генерируем JWT токены
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        response = Response({
            'success': True,
            'user_id': user.id,
            'username': user.username,
        }, status=200)

        # Записываем токены в безопасные куки
        response.set_cookie(
            key='accessToken',
            value=access_token,
            httponly=True,
            samesite='Lax',
            secure=False,
            max_age=86400  # 1 день
        )
        response.set_cookie(
            key='refreshToken',
            value=refresh_token,
            httponly=True,
            samesite='Lax',
            secure=False,
            max_age=604800  # 7 дней
        )
        return response

    return Response({'error': 'Неверный логин или пароль'}, status=401)


@api_view(['GET'])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def api_me(request):
    return Response({'id': request.user.id, 'username': request.user.username})


# ─── Friends API ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def api_get_friends(request):
    friends = request.user.friends.all()
    data = [{'id': f.id, 'username': f.username} for f in friends]
    return Response(data)


@api_view(['GET'])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def api_search_users(request):
    query = request.query_params.get('q', '').strip()
    if len(query) < 2:
        return Response([])
    users = User.objects.filter(username__icontains=query).exclude(id=request.user.id)[:10]

    friend_ids = set(request.user.friends.values_list('id', flat=True))
    sent_ids = set(FriendRequest.objects.filter(
        from_user=request.user, is_accepted=False
    ).values_list('to_user_id', flat=True))

    data = []
    for u in users:
        data.append({
            'id': u.id,
            'username': u.username,
            'is_friend': u.id in friend_ids,
            'request_sent': u.id in sent_ids,
        })
    return Response(data)


@api_view(['POST'])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def api_send_friend_request(request):
    to_id = request.data.get('to_id')
    try:
        to_user = User.objects.get(id=to_id)
    except User.DoesNotExist:
        return Response({'error': 'Пользователь не найден'}, status=404)

    if to_user == request.user:
        return Response({'error': 'Нельзя добавить себя'}, status=400)

    if request.user.friends.filter(id=to_id).exists():
        return Response({'error': 'Уже в друзьях'}, status=400)

    existing = FriendRequest.objects.filter(
        from_user=request.user, to_user=to_user, is_accepted=False
    ).first()
    if existing:
        return Response({'error': 'Запрос уже отправлен'}, status=400)

    # If the other user already sent us a request — auto-accept
    reverse = FriendRequest.objects.filter(
        from_user=to_user, to_user=request.user, is_accepted=False
    ).first()
    if reverse:
        reverse.is_accepted = True
        reverse.save()
        request.user.friends.add(to_user)
        return Response({'status': 'accepted', 'message': 'Вы теперь друзья!'})

    req = FriendRequest.objects.create(from_user=request.user, to_user=to_user)
    return Response({'status': 'sent', 'request_id': req.id})


@api_view(['GET'])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def api_get_friend_requests(request):
    reqs = FriendRequest.objects.filter(to_user=request.user, is_accepted=False)
    data = [{'id': r.id, 'from_id': r.from_user.id, 'from_username': r.from_user.username} for r in reqs]
    return Response(data)


@api_view(['POST'])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def api_accept_friend_request(request, req_id):
    try:
        req = FriendRequest.objects.get(id=req_id, to_user=request.user)
    except FriendRequest.DoesNotExist:
        return Response({'error': 'Запрос не найден'}, status=404)

    req.is_accepted = True
    req.save()
    request.user.friends.add(req.from_user)
    return Response({'status': 'ok', 'friend': {'id': req.from_user.id, 'username': req.from_user.username}})


@api_view(['POST'])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def api_reject_friend_request(request, req_id):
    try:
        req = FriendRequest.objects.get(id=req_id, to_user=request.user)
        req.delete()
        return Response({'status': 'ok'})
    except FriendRequest.DoesNotExist:
        return Response({'error': 'Запрос не найден'}, status=404)


@api_view(['POST'])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def api_remove_friend(request):
    friend_id = request.data.get('friend_id')
    try:
        friend = User.objects.get(id=friend_id)
        request.user.friends.remove(friend)
        return Response({'status': 'ok'})
    except User.DoesNotExist:
        return Response({'error': 'Пользователь не найден'}, status=404)


# ─── Chat API ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def api_get_chat(request, user_id):
    messages = Message.objects.filter(
        sender_id__in=[request.user.id, user_id],
        recipient_id__in=[request.user.id, user_id]
    ).order_by('send_time')[:100]

    data = [{
        'id': m.id,
        'sender_id': m.sender_id,
        'text': m.message_text,
        'time': m.send_time.strftime('%H:%M') if m.send_time else '',
        'is_read': m.is_read,
    } for m in messages]
    return Response(data)


class IUserRepository(ABC):
    @abstractmethod
    def create_user(self, username: str, email: str): pass

    @abstractmethod
    def get_user(self, user_id: int): pass

    @abstractmethod
    def get_random_user(self): pass

    @abstractmethod
    def get_all_users(self): pass

    @abstractmethod
    def update_user(self, user_id: int, username: str = None, email: str = None): pass

    @abstractmethod
    def delete_user(self, user_id: int): pass

    @abstractmethod
    def add_friend(self, user_id: int, friend_id: int): pass

    @abstractmethod
    def remove_friend(self, user_id: int, friend_id: int): pass

    @abstractmethod
    def get_friends(self, user_id: int): pass

    @abstractmethod
    def is_friend(self, user_id: int, friend_id: int): pass

    @abstractmethod
    def create_friend_request(self, from_id: int, to_id: int): pass

    @abstractmethod
    def accept_friend_request(self, request_id: int): pass

    @abstractmethod
    def reject_friend_request(self, request_id: int): pass

    @abstractmethod
    def get_friend_requests(self, user_id: int): pass

    @abstractmethod
    def send_message(self, sender_id: int, recipient_id: int, msg): pass

    @abstractmethod
    def get_messages(self, user_id: int): pass

    @abstractmethod
    def get_chat(self, user_id: int, other_user_id: int): pass

    @abstractmethod
    def mark_message_as_read(self, message_id: int): pass

    @abstractmethod
    def add_rating(self, user_id: int, from_user_id: int, rate): pass

    @abstractmethod
    def get_rating(self, user_id: int): pass

    @abstractmethod
    def get_ratings(self, user_id: int): pass

    @abstractmethod
    def add_image(self, user_id: int, url: str): pass

    @abstractmethod
    def remove_image(self, image_id: int): pass

    @abstractmethod
    def get_images(self, user_id: int): pass

    @abstractmethod
    def add_log(self, user_id: int, log): pass

    @abstractmethod
    def get_logs(self, user_id: int): pass

    @abstractmethod
    def delete_account(self, user_id: int): pass

    @abstractmethod
    def deactivate_account(self, user_id: int): pass

    @abstractmethod
    def add_to_rated(self, user_id: int, rated_user_id: int): pass


class UserRepository(IUserRepository):

    def create_user(self, username: str, email: str, password: str, **kwargs):
        user = User.objects.create_user(username=username, email=email, password=password)
        return user

    def get_user(self, user_id: int):
        return User.objects.get(id=user_id)

    def get_random_user(self):
        return User.objects.order_by('?').first()

    def get_all_users(self):
        return User.objects.all()

    def update_user(self, user_id: int, username: str = None, email: str = None):
        user = User.objects.get(id=user_id)

        if user != None:
            user.username = username if username else user.username
            user.email = email if email else user.email
            user.save()
        return user

    def delete_user(self, user_id: int):
        user = User.objects.get(id=user_id)
        if user != None:
            user.delete()

    def add_friend(self, user_id: int, friend_id: int):
        user = User.objects.get(id=user_id)
        friend = User.objects.get(id=friend_id)

        if user != None and friend != None:
            user.friends.add(friend)
            friend.friends.add(user)
            user.save()
            friend.save()
        return user

    def remove_friend(self, user_id: int, friend_id: int):
        user = User.objects.get(id=user_id)
        friend = User.objects.get(id=friend_id)

        if user != None and friend != None:
            user.friends.remove(friend)
            friend.friends.remove(user)
            user.save()
            friend.save()
        return user

    def get_friends(self, user_id: int):
        user = User.objects.get(id=user_id)
        if user != None:
            return user.friends.all()
        return []

    def is_friend(self, user_id: int, friend_id: int):
        user = User.objects.get(id=user_id)
        friend = User.objects.get(id=friend_id)

        if user != None and friend != None:
            return friend in user.friends.all()
        return False

    def create_friend_request(self, from_id: int, to_id: int):
        from_user = User.objects.get(id=from_id)
        to_user = User.objects.get(id=to_id)

        if from_user != None and to_user != None:
            request = FriendRequest.objects.create(from_user=from_user, to_user=to_user)
            return request
        return None

    def accept_friend_request(self, request_id: int):
        request = FriendRequest.objects.get(id=request_id)
        if request != None:
            request.is_accepted = True
            request.save()
            self.add_friend(request.from_user.id, request.to_user.id)
            return request
        return False

    def reject_friend_request(self, request_id: int):
        request = FriendRequest.objects.get(id=request_id)
        if request != None:
            request.delete()
            return True
        return False

    def get_friend_requests(self, user_id: int):
        return FriendRequest.objects.filter(to_user_id=user_id)

    def send_message(self, sender_id: int, recipient_id: int, msg: MessageModel):
        sender = User.objects.get(id=sender_id)
        recipient = User.objects.get(id=recipient_id)

        if sender != None and recipient != None:
            message = Message.objects.create(sender=sender, recipient=recipient, message_text=msg.text,
                                             send_time=msg.send_time, is_read=msg.is_read)
            message.save()
            return message
        return None

    def get_messages(self, user_id):
        user = User.objects.get(id=user_id)
        if user != None:
            return user.received_messages.all()
        return []

    def get_chat(self, user_id, other_user_id):
        user = User.objects.get(id=user_id)
        other_user = User.objects.get(id=other_user_id)

        if user != None and other_user != None:
            messages = Message.objects.filter(sender_id=user_id, recipient_id=other_user_id) | Message.objects.filter(
                sender_id=other_user_id, recipient_id=user_id)
            return messages.order_by('send_time')
        return []

    def mark_message_as_read(self, message_id: int):
        message = Message.objects.get(id=message_id)
        if message != None:
            message.is_read = True
            message.save()
            return message
        return None

    def add_rating(self, user_id: int, from_user_id: int, rate):
        user = User.objects.get(id=user_id)
        from_user = User.objects.get(id=from_user_id)

        if user != None and from_user != None:
            rating = Rating.objects.create(user=user, from_user=from_user, value=rate)
            rating.save()
            return rating
        return None

    def get_rating(self, user_id: int):
        ratings = Rating.objects.filter(user_id=user_id)
        if ratings.count() > 0:
            return int(sum(r.value for r in ratings) / ratings.count())
        return 0

    def get_ratings(self, user_id: int):
        return Rating.objects.filter(user_id=user_id)

    def add_image(self, user_id: int, url: str):
        user = User.objects.get(id=user_id)
        if user != None:
            image = Image.objects.create(user=user, url=url)
            image.save()
            return image
        return None

    def remove_image(self, image_id: int):
        image = Image.objects.get(id=image_id)
        if image != None:
            image.delete()
            return True
        return False

    def get_images(self, user_id: int):
        return Image.objects.filter(user_id=user_id)

    def add_log(self, user_id: int, log):
        user = User.objects.get(id=user_id)
        if user != None:
            log_entry = Log.objects.create(user=user, text=log)
            log_entry.save()
            return log_entry
        return None

    def get_logs(self, user_id: int):
        return Log.objects.filter(user_id=user_id)

    def delete_account(self, user_id: int):
        user = User.objects.get(id=user_id)
        if user != None:
            user.delete()
            return True
        return False

    def deactivate_account(self, user_id: int):
        user = User.objects.get(id=user_id)
        if user != None:
            user.is_active = False
            user.save()
            return True
        return False

    def add_to_rated(self, user_id: int, rated_user_id: int):
        user = User.objects.get(id=user_id)
        rated_user = User.objects.get(id=rated_user_id)

        if user != None and rated_user != None:
            user.rated_users.add(rated_user)
            user.save()
            return True
        return False


class UserView(viewsets.ViewSet):
    authentication_classes = [CookieJWTAuthentication]

    def __init__(self, **kwargs):
        self.user_repository = UserRepository()
        super().__init__(**kwargs)

    @action(methods=['post'], detail=False)
    def create_user(self, request):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        returnUrl = request.query_params.get('returnUrl', '/')

        if not username or not email or not password:
            return HttpResponseBadRequest("Username, email and password are required.")

        user = self.user_repository.create_user(username, email, password)
        if user:
            return redirect(returnUrl)

        return HttpResponseBadRequest("Failed to create user.")

    @action(methods=['get'], detail=True)
    def update_user(self, request, pk=None):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        returnUrl = request.query_params.get('returnUrl', '/')

        if not username and not email and not password:
            return HttpResponseBadRequest("At least one field (username, email or password) is required.")

        User.objects.filter(id=pk).update(username=username, email=email, password=password)
        return redirect(returnUrl)

    @action(methods=['delete'], detail=True)
    def delete_user(self, request, pk=None):
        returnUrl = request.query_params.get('returnUrl', '/')
        self.user_repository.delete_user(pk)
        return redirect(returnUrl)

    @action(methods=['get'], detail=False)
    def get_logs(self, request):
        user_id = request.query_params.get('user_id')
        logs = self.user_repository.get_logs(user_id)
        logs_data = [{"id": log.id, "text": log.text} for log in logs]
        return render(request, 'logs.html', {'logs': logs_data})

    @action(methods=['delete'], detail=True)
    def delete_log(self, request, pk=None):
        returnUrl = request.query_params.get('returnUrl', '/')
        self.user_repository.delete_log(pk)
        return redirect(returnUrl)

    @action(methods=['get'], detail=False)
    def lenta(self, request):
        users = []
        owner = request.user

        if not owner.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        while len(users) < 10:
            user = self.user_repository.get_random_user()
            if user not in owner.rated_users.all() and user != owner:
                users.append(user)

        return render(request, 'lenta.html', {'users': users})

    @action(methods=['post'], detail=True)
    def add_rating(self, request, pk=None):

        data = json.loads(request.body)
        rate = data.get('rate')
        owner = request.user
        user = User.objects.get(id=pk)

        user.rating += float(rate)
        user.rated_count += 1
        user.save()
        owner.rated_users.add(user)

        return JsonResponse({
            "success": True
        })

    @action(methods=['get'], detail=False)
    def get_random_user(self, request):
        try:
            owner = request.user
            if not owner.is_authenticated:
                return JsonResponse({"error": "Unauthorized"}, status=401)

            while True:
                user = self.user_repository.get_random_user()
                if owner and user:
                    if user == owner or user in owner.rated_users.all():
                        continue

                    serializer = UserSerializer(user)
                    # serializer = UserSerializer(self.user_repository.get_user(owner.id))
                    return Response(serializer.data)
                else:
                    return Response({"error": "No users found"}, status=404)
        except Exception as e:
            print(e)
            return Response({"error": str(e)}, status=500)

    @action(methods=['get'], detail=False)
    def seed_users(self, request):

        from faker import Faker
        import random

        fake = Faker()

        for i in range(50):
            username = fake.user_name() + str(random.randint(1, 9999))
            email = fake.email()

            user = User.objects.create_user(
                username=username,
                email=email,
                password="12345678"
            )

            user.rating = random.randint(0, 5000)
            user.rated_count = random.randint(0, 1000)

            user.url_paths = [
                f"https://picsum.photos/500/500?random={random.randint(1, 999999)}"
            ]

            user.save()

        return JsonResponse({
            "success": True,
            "message": "Users created"
        })

    @action(methods=['get'], detail=False)
    def get_user_rating(self, request):
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        print(f"User {user.username} has rating {user.rating} and rated_count {user.rated_count}")
        if user.rated_count == 0:
            rating = 0
        else:
            rating = int(user.rating) / user.rated_count

        tier_index = max(1, min(int(rating), 15))
        display_rating = UserSerializer(user).get_display_rating(user)

        return Response({
            "display_rating": display_rating,
            "rating_value": rating
        })

    @action(methods=['post'], detail=False)
    def send_message(self, request):
        sender_id = request.data.get('sender_id')
        recipient_id = request.data.get('recipient_id')
        text = request.data.get('text')

        if not all([sender_id, recipient_id, text]):
            return Response({"error": "Missing fields"}, status=status.HTTP_400_BAD_REQUEST)

        from datetime import datetime
        class MessageData:
            def __init__(self, text):
                self.text = text
                self.send_time = datetime.now()
                self.is_read = False

        msg_data = MessageData(text)
        message = self.user_repository.send_message(sender_id, recipient_id, msg_data)

        if message:
            return Response({"status": "Message sent", "id": message.id}, status=status.HTTP_201_CREATED)
        return Response({"error": "Failed to send"}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['get'], detail=False)
    def get_chat(self, request):

        user_id = request.query_params.get('user_id')
        other_id = request.query_params.get('other_id')

        if not user_id or not other_id:
            return Response({"error": "user_id and other_id required"}, status=status.HTTP_400_BAD_REQUEST)

        messages = self.user_repository.get_chat(user_id, other_id)
        data = [{
            "id": m.id,
            "sender": m.sender.id,
            "text": m.message_text,
            "time": m.send_time,
            "is_read": m.is_read
        } for m in messages]

        return Response(data)

    @action(methods=['post'], detail=False)
    def create_friend_request(self, request):
        from_id = request.data.get('from_id')
        to_id = request.data.get('to_id')

        req = self.user_repository.create_friend_request(from_id, to_id)
        if req:
            return Response({"status": "Request sent", "id": req.id})
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(methods=['get'], detail=False)
    def get_friend_requests(self, request):
        user_id = request.query_params.get('user_id')
        requests = self.user_repository.get_friend_requests(user_id)
        data = [{"id": r.id, "from_user": r.from_user.username} for r in requests]
        return Response(data)

    @action(methods=['post'], detail=True)
    def accept_friend_request(self, request, pk=None):
        result = self.user_repository.accept_friend_request(pk)
        if result:
            return Response({"status": "Friend added"})
        return Response({"error": "Request not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(methods=['post'], detail=True)
    def reject_friend_request(self, request, pk=None):
        result = self.user_repository.reject_friend_request(pk)
        return Response({"status": "Rejected" if result else "Failed"})

    @action(methods=['get'], detail=False)
    def get_friends(self, request):
        user_id = request.query_params.get('user_id')
        friends = self.user_repository.get_friends(user_id)
        data = [{"id": f.id, "username": f.username} for f in friends]
        return Response(data)

    @action(methods=['post'], detail=False)
    def remove_friend(self, request):

        user_id = request.data.get('user_id')
        friend_id = request.data.get('friend_id')
        self.user_repository.remove_friend(user_id, friend_id)
        return Response({"status": "Removed"})