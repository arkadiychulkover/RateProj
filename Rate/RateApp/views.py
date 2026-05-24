import json
import uuid
import os

from django.shortcuts import get_object_or_404
from django.conf import settings
from django.http import (
    JsonResponse, HttpResponseBadRequest, HttpResponseNotFound
)
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from abc import ABC, abstractmethod
from django.core.files.storage import FileSystemStorage

from .models import (
    User, Message, FriendRequest, Rating,
    Image, LogEntry, LogType, LogFilter,
    UserSerializer, ImageSerializer, LogEntrySerializer,
    MessageModel, Rate,
)
from .forms import LoginForm, RegistrationForm
from .middleware import CookieJWTAuthentication


# ── Страницы ──────────────────────────────────────────────────────────────────

def login_page(request):
    """GET — показывает форму; редирект если уже залогинен."""
    if request.user.is_authenticated:
        return redirect('lenta')
    form = LoginForm()
    return render(request, 'login.html', {'form': form})


def register_page(request):
    """GET — показывает форму; редирект если уже залогинен."""
    if request.user.is_authenticated:
        return redirect('lenta')
    form = RegistrationForm()
    return render(request, 'register.html', {'form': form})


def cabinet_page(request):
    if not request.user.is_authenticated:
        return redirect('login_page')
    return render(request, 'cabinet.html')


def _get_ws_token(request):
    """Генерирует свежий JWT access-токен для передачи в WebSocket URL."""
    if request.user.is_authenticated:
        refresh = RefreshToken.for_user(request.user)
        return str(refresh.access_token)
    return ''


def chat_home(request):
    if not request.user.is_authenticated:
        return redirect('login_page')
    return render(request, 'chat.html', {
        'chat_with_id': 'null',
        'ws_token': _get_ws_token(request),
    })


def chat_with(request, user_id):
    if not request.user.is_authenticated:
        return redirect('login_page')
    return render(request, 'chat.html', {
        'chat_with_id': user_id,
        'ws_token': _get_ws_token(request),
    })


# ── Auth API (JWT в httpOnly-куках) ───────────────────────────────────────────

def _set_jwt_cookies(response: Response, user) -> None:
    """Генерирует и записывает JWT-пару в httpOnly-куки."""
    refresh = RefreshToken.for_user(user)
    response.set_cookie(
        key='accessToken', value=str(refresh.access_token),
        httponly=True, samesite='Lax', secure=False, max_age=86400,
    )
    response.set_cookie(
        key='refreshToken', value=str(refresh),
        httponly=True, samesite='Lax', secure=False, max_age=604800,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def api_register(request):
    """
    Регистрация через API (JSON).
    Валидация через RegistrationForm — те же правила, что и на фронте.
    """
    form = RegistrationForm(request.data)
    if not form.is_valid():
        # Возвращаем первую ошибку в удобном виде
        errors = form.errors.as_data()
        first_field = next(iter(errors))
        first_msg   = errors[first_field][0].message
        return Response({'error': first_msg}, status=400)

    cd = form.cleaned_data
    user = User.objects.create_user(
        username=cd['username'],
        email=cd['email'],
        password=cd['password'],
    )
    login(request, user)
    LogEntry.objects.create(user=user, log_type=LogType.REGISTER, text="Регистрация")

    response = Response({'success': True, 'user_id': user.id, 'username': user.username}, status=201)
    _set_jwt_cookies(response, user)
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    """
    Вход через API (JSON).
    Валидация через LoginForm — проверяет заполненность полей.
    """
    form = LoginForm(request.data)
    if not form.is_valid():
        errors = form.errors.as_data()
        first_field = next(iter(errors))
        first_msg   = errors[first_field][0].message
        return Response({'error': first_msg}, status=400)

    cd = form.cleaned_data
    user = authenticate(username=cd['username'], password=cd['password'])

    if user is None:
        return Response({'error': 'Неверный логин или пароль'}, status=401)
    if not user.is_active:
        return Response({'error': 'Аккаунт заблокирован'}, status=403)

    login(request, user)
    LogEntry.objects.create(user=user, log_type=LogType.LOGIN, text="Вход в систему")

    response = Response({'success': True, 'user_id': user.id, 'username': user.username})
    _set_jwt_cookies(response, user)
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
def api_logout(request):
    response = Response({'success': True})
    response.delete_cookie('accessToken')
    response.delete_cookie('refreshToken')
    logout(request)
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_me(request):
    return Response({'id': request.user.id, 'username': request.user.username})


# ── Friends API ───────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_friends(request):
    friends = request.user.friends.all()
    return Response([{'id': f.id, 'username': f.username} for f in friends])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_search_users(request):
    query = request.query_params.get('q', '').strip()
    if len(query) < 2:
        return Response([])
    users = User.objects.filter(username__icontains=query).exclude(id=request.user.id)[:10]

    friend_ids = set(request.user.friends.values_list('id', flat=True))
    sent_ids   = set(FriendRequest.objects.filter(
        from_user=request.user, is_accepted=False
    ).values_list('to_user_id', flat=True))

    return Response([{
        'id': u.id, 'username': u.username,
        'is_friend': u.id in friend_ids,
        'request_sent': u.id in sent_ids,
    } for u in users])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_send_friend_request(request):
    to_id = request.data.get('to_id')
    to_user = get_object_or_404(User, id=to_id)

    if to_user == request.user:
        return Response({'error': 'Нельзя добавить себя'}, status=400)
    if request.user.friends.filter(id=to_id).exists():
        return Response({'error': 'Уже в друзьях'}, status=400)
    if FriendRequest.objects.filter(from_user=request.user, to_user=to_user, is_accepted=False).exists():
        return Response({'error': 'Запрос уже отправлен'}, status=400)

    # Автоматически принять, если встречный запрос уже существует
    reverse = FriendRequest.objects.filter(from_user=to_user, to_user=request.user, is_accepted=False).first()
    if reverse:
        reverse.is_accepted = True
        reverse.save()
        request.user.friends.add(to_user)
        return Response({'status': 'accepted', 'message': 'Вы теперь друзья!'})

    req = FriendRequest.objects.create(from_user=request.user, to_user=to_user)
    LogEntry.objects.create(user=request.user, log_type=LogType.FRIEND_REQUEST,
                             text=f"Отправил заявку пользователю @{to_user.username}")
    return Response({'status': 'sent', 'request_id': req.id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_friend_requests(request):
    reqs = FriendRequest.objects.filter(to_user=request.user, is_accepted=False)
    return Response([{'id': r.id, 'from_id': r.from_user.id, 'from_username': r.from_user.username} for r in reqs])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_accept_friend_request(request, req_id):
    req = get_object_or_404(FriendRequest, id=req_id, to_user=request.user)
    req.is_accepted = True
    req.save()
    request.user.friends.add(req.from_user)
    LogEntry.objects.create(user=request.user, log_type=LogType.ACCEPT_FRIEND,
                             text=f"Принял заявку от @{req.from_user.username}")
    return Response({'status': 'ok', 'friend': {'id': req.from_user.id, 'username': req.from_user.username}})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_reject_friend_request(request, req_id):
    req = get_object_or_404(FriendRequest, id=req_id, to_user=request.user)
    req.delete()
    return Response({'status': 'ok'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_remove_friend(request):
    friend = get_object_or_404(User, id=request.data.get('friend_id'))
    request.user.friends.remove(friend)
    LogEntry.objects.create(user=request.user, log_type=LogType.REMOVE_FRIEND,
                             text=f"Удалил из друзей @{friend.username}")
    return Response({'status': 'ok'})


# ── Chat API ──────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_chat(request, user_id):
    messages = Message.objects.filter(
        sender_id__in=[request.user.id, user_id],
        recipient_id__in=[request.user.id, user_id]
    ).order_by('send_time')[:100]

    return Response([{
        'id': m.id,
        'sender_id': m.sender_id,
        'text': m.message_text,
        'time': m.send_time.strftime('%H:%M') if m.send_time else '',
        'is_read': m.is_read,
    } for m in messages])


# ── Repository ────────────────────────────────────────────────────────────────

class IUserRepository(ABC):
    @abstractmethod
    def create_user(self, username, email, password, **kw): pass
    @abstractmethod
    def get_user(self, user_id): pass
    @abstractmethod
    def get_random_user(self): pass
    @abstractmethod
    def get_all_users(self): pass
    @abstractmethod
    def update_user(self, user_id, username=None, email=None): pass
    @abstractmethod
    def delete_user(self, user_id): pass
    @abstractmethod
    def add_friend(self, user_id, friend_id): pass
    @abstractmethod
    def remove_friend(self, user_id, friend_id): pass
    @abstractmethod
    def get_friends(self, user_id): pass
    @abstractmethod
    def is_friend(self, user_id, friend_id): pass
    @abstractmethod
    def create_friend_request(self, from_id, to_id): pass
    @abstractmethod
    def accept_friend_request(self, request_id): pass
    @abstractmethod
    def reject_friend_request(self, request_id): pass
    @abstractmethod
    def get_friend_requests(self, user_id): pass
    @abstractmethod
    def send_message(self, sender_id, recipient_id, msg): pass
    @abstractmethod
    def get_messages(self, user_id): pass
    @abstractmethod
    def get_chat(self, user_id, other_user_id): pass
    @abstractmethod
    def mark_message_as_read(self, message_id): pass
    @abstractmethod
    def add_rating(self, user_id, from_user_id, rate): pass
    @abstractmethod
    def get_rating(self, user_id): pass
    @abstractmethod
    def get_ratings(self, user_id): pass
    @abstractmethod
    def add_image(self, user_id, url): pass
    @abstractmethod
    def remove_image(self, image_id): pass
    @abstractmethod
    def get_images(self, user_id): pass
    @abstractmethod
    def add_log(self, user_id, log_type, text): pass
    @abstractmethod
    def get_logs(self, user_id): pass
    @abstractmethod
    def delete_account(self, user_id): pass
    @abstractmethod
    def deactivate_account(self, user_id): pass
    @abstractmethod
    def add_to_rated(self, user_id, rated_user_id): pass


class UserRepository(IUserRepository):

    def create_user(self, username, email, password, **kw):
        return User.objects.create_user(username=username, email=email, password=password)

    def get_user(self, user_id):
        return User.objects.get(id=user_id)

    def get_random_user(self):
        return User.objects.prefetch_related('images').order_by('?').first()

    def get_all_users(self):
        return User.objects.all()

    def update_user(self, user_id, username=None, email=None):
        user = User.objects.get(id=user_id)
        if username: user.username = username
        if email:    user.email    = email
        user.save()
        return user

    def delete_user(self, user_id):
        User.objects.filter(id=user_id).delete()

    def add_friend(self, user_id, friend_id):
        user   = User.objects.get(id=user_id)
        friend = User.objects.get(id=friend_id)
        user.friends.add(friend)
        return user

    def remove_friend(self, user_id, friend_id):
        user   = User.objects.get(id=user_id)
        friend = User.objects.get(id=friend_id)
        user.friends.remove(friend)
        return user

    def get_friends(self, user_id):
        return User.objects.get(id=user_id).friends.all()

    def is_friend(self, user_id, friend_id):
        return User.objects.get(id=user_id).friends.filter(id=friend_id).exists()

    def create_friend_request(self, from_id, to_id):
        from_user = User.objects.get(id=from_id)
        to_user   = User.objects.get(id=to_id)
        return FriendRequest.objects.create(from_user=from_user, to_user=to_user)

    def accept_friend_request(self, request_id):
        req = FriendRequest.objects.get(id=request_id)
        req.is_accepted = True
        req.save()
        self.add_friend(req.from_user.id, req.to_user.id)
        return req

    def reject_friend_request(self, request_id):
        FriendRequest.objects.filter(id=request_id).delete()
        return True

    def get_friend_requests(self, user_id):
        return FriendRequest.objects.filter(to_user_id=user_id, is_accepted=False)

    def send_message(self, sender_id, recipient_id, msg: MessageModel):
        return Message.objects.create(
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_text=msg.text,
            is_read=msg.is_read,
        )

    def get_messages(self, user_id):
        return Message.objects.filter(recipient_id=user_id)

    def get_chat(self, user_id, other_user_id):
        return Message.objects.filter(
            sender_id__in=[user_id, other_user_id],
            recipient_id__in=[user_id, other_user_id],
        ).order_by('send_time')

    def mark_message_as_read(self, message_id):
        Message.objects.filter(id=message_id).update(is_read=True)

    def add_rating(self, user_id, from_user_id, rate):
        user      = User.objects.get(id=user_id)
        from_user = User.objects.get(id=from_user_id)
        return Rating.objects.create(user=user, from_user=from_user, value=rate)

    def get_rating(self, user_id):
        qs = Rating.objects.filter(user_id=user_id)
        return int(qs.aggregate(avg=models.Avg('value'))['avg'] or 0)

    def get_ratings(self, user_id):
        return Rating.objects.filter(user_id=user_id)

    def add_image(self, user_id, url):
        user = User.objects.get(id=user_id)
        return Image.objects.create(user=user, url=url)

    def remove_image(self, image_id):
        Image.objects.filter(id=image_id).delete()
        return True

    def get_images(self, user_id):
        return Image.objects.filter(user_id=user_id)

    def add_log(self, user_id, log_type, text):
        user = User.objects.get(id=user_id)
        return LogEntry.objects.create(user=user, log_type=log_type, text=text)

    def get_logs(self, user_id):
        return LogEntry.objects.filter(user_id=user_id)

    def delete_account(self, user_id):
        User.objects.filter(id=user_id).delete()
        return True

    def deactivate_account(self, user_id):
        User.objects.filter(id=user_id).update(is_active=False)
        return True

    def add_to_rated(self, user_id, rated_user_id):
        user       = User.objects.get(id=user_id)
        rated_user = User.objects.get(id=rated_user_id)
        user.rated_users.add(rated_user)
        return True


# ── Нужен import models для Avg ───────────────────────────────────────────────
from django.db import models as dj_models

# patch get_rating to use correct import
def _get_rating_fixed(self, user_id):
    from django.db.models import Avg
    qs = Rating.objects.filter(user_id=user_id)
    return int(qs.aggregate(avg=Avg('value'))['avg'] or 0)

UserRepository.get_rating = _get_rating_fixed


# ── UserView (лента, оценки, сид) ─────────────────────────────────────────────

class UserView(viewsets.ViewSet):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated]
    user_repository        = UserRepository()

    def get_permissions(self):
        """
        Публичные экшены (не требуют токена):
          - lenta         — редирект на логин происходит внутри
          - get_user_rating  — возвращает 401 JSON сам, если не залогинен
          - get_random_user  — аналогично
          - seed_users    — только для dev, не трогаем
        """
        public_actions = {'lenta', 'get_user_rating', 'get_random_user', 'seed_users'}
        if self.action in public_actions:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(methods=['post'], detail=False)
    def create_user(self, request):
        username = request.data.get('username')
        email    = request.data.get('email')
        password = request.data.get('password')
        if not all([username, email, password]):
            return HttpResponseBadRequest("username, email и password обязательны")
        user = self.user_repository.create_user(username, email, password)
        return Response({'success': True, 'id': user.id}, status=201)

    @action(methods=['get'], detail=True)
    def update_user(self, request, pk=None):
        username = request.data.get('username')
        email    = request.data.get('email')
        if not username and not email:
            return HttpResponseBadRequest("Укажи хотя бы одно поле")
        user = self.user_repository.update_user(pk, username=username, email=email)
        return Response({'success': True, 'username': user.username})

    @action(methods=['delete'], detail=True)
    def delete_user(self, request, pk=None):
        self.user_repository.delete_user(pk)
        return Response({'success': True})

    @action(methods=['get'], detail=False)
    def get_logs(self, request):
        user_id = request.query_params.get('user_id')
        logs = self.user_repository.get_logs(user_id)
        return render(request, 'logs.html', {
            'logs': [{'id': l.id, 'text': l.text, 'log_type': l.log_type} for l in logs]
        })

    @action(methods=['get'], detail=False)
    def lenta(self, request):
        owner = request.user
        if not owner.is_authenticated:
            return redirect('login_page')
        rated_ids = owner.rated_users.values_list('id', flat=True)
        users = (
            User.objects
            .exclude(id=owner.id)
            .exclude(id__in=rated_ids)
            .prefetch_related('images')
            .order_by('?')[:10]
        )
        return render(request, 'lenta.html', {'users': list(users)})

    @action(methods=['post'], detail=True)
    def add_rating(self, request, pk=None):
        data  = json.loads(request.body)
        rate  = float(data.get('rate', 0))
        owner = request.user
        user  = get_object_or_404(User, id=pk)

        user.rating      += rate
        user.rated_count += 1
        user.save()
        owner.rated_users.add(user)

        Rating.objects.create(user=user, from_user=owner, value=rate)
        LogEntry.objects.create(
            user=owner, log_type=LogType.RATE,
            text=f"Поставил оценку {rate} пользователю @{user.username}"
        )
        return JsonResponse({'success': True})

    @action(methods=['get'], detail=False)
    def get_random_user(self, request):
        owner = request.user
        if not owner.is_authenticated:
            return JsonResponse({'error': 'Unauthorized'}, status=401)
        try:
            rated_ids = owner.rated_users.values_list('id', flat=True)
            candidate = (
                User.objects
                .exclude(id=owner.id)
                .exclude(id__in=rated_ids)
                .prefetch_related('images')
                .order_by('?')
                .first()
            )
            if candidate:
                return Response(UserSerializer(candidate).data)
            return Response({'error': 'Нет новых пользователей'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(methods=['get'], detail=False)
    def seed_users(self, request):
        from faker import Faker
        import random
        fake = Faker()
        for _ in range(50):
            username = fake.user_name() + str(random.randint(1, 9999))
            email    = fake.email()
            user     = User.objects.create_user(username=username, email=email, password='12345678')
            user.rating       = random.randint(0, 5000)
            user.rated_count  = random.randint(1, 1000)
            user.save()
            Image.objects.create(user=user, url=f"https://picsum.photos/500/500?random={random.randint(1,999999)}")
            Image.objects.create(user=user, url=f"https://picsum.photos/500/500?random={random.randint(1,999999)}")
        return JsonResponse({'success': True, 'message': '50 пользователей создано'})

    @action(methods=['get'], detail=False)
    def get_user_rating(self, request):
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'error': 'Unauthorized'}, status=401)
        rating = (user.rating / user.rated_count) if user.rated_count else 0
        tier_index    = max(1, min(int(rating), 15))
        display_rating = UserSerializer(user).get_display_rating(user)
        return Response({
            'tier_number':    tier_index,
            'tier_name':      Rate.get_name(tier_index),
            'display_rating': display_rating,
        })


# ── CabinetView (профиль, фото, логи) ─────────────────────────────────────────

class CabinetView(viewsets.ViewSet):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated]
    user_repository        = UserRepository()

    @action(methods=['get'], detail=False)
    def current(self, request):
        user = request.user
        if not user.is_authenticated:
            return HttpResponseBadRequest("Не авторизован")
        return Response({'viewMode': user.view_mode, 'currentZone': user.cabinet_zone})

    @action(methods=['post'], detail=False)
    def switch_zone(self, request):
        zone = request.data.get('zone')
        if not zone:
            return HttpResponseBadRequest("zone required")
        request.user.cabinet_zone = zone
        request.user.save(update_fields=['cabinet_zone'])
        return Response({'success': True})

    @action(methods=['post'], detail=False)
    def change_view_mode(self, request):
        mode = request.data.get('mode')
        if not mode:
            return HttpResponseBadRequest("mode required")
        request.user.view_mode = mode
        request.user.save(update_fields=['view_mode'])
        return Response({'success': True})

    @action(methods=['get'], detail=False)
    def images(self, request):
        user = request.user
        if not user.is_authenticated:
            return HttpResponseBadRequest("Не авторизован")
        imgs = Image.objects.filter(user=user)
        return Response(ImageSerializer(imgs, many=True).data)

    @action(methods=['post'], detail=False)
    def add_image(self, request):
        user = request.user
        if not user.is_authenticated:
            return HttpResponseBadRequest("Не авторизован")
        if 'front' not in request.FILES or 'profile' not in request.FILES:
            return HttpResponseBadRequest("Нужны оба файла: 'front' и 'profile'")

        # Удаляем старые фото (лимит 2)
        for img in Image.objects.filter(user=user):
            try:
                rel  = img.url.replace(settings.MEDIA_URL, '', 1)
                full = os.path.join(settings.MEDIA_ROOT, rel)
                if os.path.exists(full):
                    os.remove(full)
            except Exception:
                pass
            img.delete()

        fs = FileSystemStorage()

        def save_file(f):
            ext  = f.name.rsplit('.', 1)[-1] if '.' in f.name else 'jpg'
            name = fs.save(f"{uuid.uuid4()}.{ext}", f)
            return fs.url(name)

        img1 = Image.objects.create(user=user, url=save_file(request.FILES['front']))
        img2 = Image.objects.create(user=user, url=save_file(request.FILES['profile']))

        LogEntry.objects.create(user=user, log_type=LogType.ADD_IMG, text="Добавлены новые фотографии")
        return Response({'success': True, 'images': [img1.id, img2.id]})

    @action(methods=['post'], detail=False)
    def remove_image(self, request):
        user     = request.user
        image_id = request.data.get('image_id')
        img      = get_object_or_404(Image, id=image_id, user=user)

        try:
            rel  = img.url.replace(settings.MEDIA_URL, '', 1)
            full = os.path.join(settings.MEDIA_ROOT, rel)
            if os.path.exists(full):
                os.remove(full)
        except Exception:
            pass
        img.delete()
        LogEntry.objects.create(user=user, log_type=LogType.REMOVE_IMG, text="Удалена фотография")
        return Response({'success': True})

    @action(methods=['get'], detail=False)
    def logs(self, request):
        user = request.user
        if not user.is_authenticated:
            return HttpResponseBadRequest("Не авторизован")
        entries = LogEntry.objects.filter(user=user)
        return Response(LogEntrySerializer(entries, many=True).data)

    @action(methods=['get'], detail=True)
    def rating(self, request, pk=None):
        return Response({'rating': self.user_repository.get_rating(pk)})

    @action(methods=['get'], detail=True)
    def ratings(self, request, pk=None):
        ratings = self.user_repository.get_ratings(pk)
        return Response([{'from': r.from_user.id, 'value': r.value} for r in ratings])


# ── LogView (admin) ───────────────────────────────────────────────────────────

class LogView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @action(methods=['delete'], detail=True)
    def delete_log(self, request, pk=None):
        deleted, _ = LogEntry.objects.filter(id=pk).delete()
        if deleted:
            return Response({'success': True})
        return HttpResponseNotFound("Log not found")

    @action(methods=['get'], detail=True)
    def list_user_logs(self, request, pk=None):
        logs = LogEntry.objects.filter(user_id=pk)
        return Response(LogEntrySerializer(logs, many=True).data)

    @action(methods=['get'], detail=False)
    def get_all_logs(self, request):
        logs = LogEntry.objects.select_related('user').all()
        return Response([{
            'id': l.id, 'user_id': l.user.id,
            'log_type': l.log_type, 'text': l.text,
            'created_at': l.created_at,
        } for l in logs])

    @action(methods=['get'], detail=False)
    def filter_logs(self, request):
        lf = LogFilter()
        if request.query_params.get('target_user_id'):
            lf.target_user_id = int(request.query_params['target_user_id'])
        if request.query_params.getlist('log_types'):
            lf.log_types = request.query_params.getlist('log_types')
        if request.query_params.get('start_date'):
            lf.start_date = request.query_params['start_date']
        if request.query_params.get('end_date'):
            lf.end_date = request.query_params['end_date']
        logs = lf.apply_filter(LogEntry.objects.select_related('user').all())
        return Response(LogEntrySerializer(logs, many=True).data)

    @action(methods=['get'], detail=False)
    def log_page(self, request):
        return render(request, 'logs.html')
