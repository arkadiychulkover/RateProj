import json

from django.http import HttpResponseNotFound, JsonResponse, HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators import action
from django.shortcuts import render, redirect
from abc import ABC, abstractmethod
from rest_framework import viewsets
from .models import *

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
    def  add_to_rated(self, user_id: int, rated_user_id: int): pass

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
            message = Message.objects.create(sender=sender, recipient=recipient, message_text=msg.text, send_time=msg.send_time, is_read=msg.is_read)
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
            messages = Message.objects.filter(sender_id=user_id, recipient_id=other_user_id) | Message.objects.filter(sender_id=other_user_id, recipient_id=user_id)
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
    def __init__(self, **kwargs):
        self.user_repository = UserRepository()
        self.__super().__init__(**kwargs),

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
    def update_user(self, request, pk = None):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        returnUrl = request.query_params.get('returnUrl', '/')

        if not username and not email and not password:
            return HttpResponseBadRequest("At least one field (username, email or password) is required.")
        
        User.objects.filter(id=pk).update(username=username, email=email, password=password)
        return redirect(returnUrl)
    
    @action(methods=['delete'], detail=True)
    def delete_user(self, request, pk = None):
        returnUrl = request.query_params.get('returnUrl', '/')
        self.user_repository.delete_user(pk)
        return redirect(returnUrl)
    
    @action(methods=['get'], detail=false)
    def get_logs(self, request):
        user_id = request.query_params.get('user_id')
        logs = self.user_repository.get_logs(user_id)
        logs_data = [{"id": log.id, "text": log.text} for log in logs]
        return TemplateResponse(request, 'logs.html', {'logs': logs_data})
    
    @action(methods=['delete'], detail=True)
    def delete_log(self, request, pk = None):
        returnUrl = request.query_params.get('returnUrl', '/')
        self.user_repository.delete_log(pk)
        return redirect(returnUrl)

    @action(methods=['get'], detail=False)
    def lenta(self, request):
        users = []
        owner = User.objects.get(id=request.user.id)
        while len(users) < 10:
            user = self.user_repository.get_random_user()
            if user not in owner.rated_users.all() and user != owner:
                users.append(user)

        return TemplateResponse(request, 'lenta.html', {'users': users})

    @action(methods=['get'], detail=False)
    def get_random_user(self, request):
        owner = User.objects.get(id=request.user.id)

        while True:
            user = self.user_repository.get_random_user()
            if owner and user:
                has_rated = user in owner.rated_users.all()
                if not has_rated:
                    return JsonResponse(json.dumps(user), safe=False)
                    break;
                else:
                    continue
