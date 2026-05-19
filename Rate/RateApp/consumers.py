import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from datetime import datetime


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.me = self.scope['user']
        if self.me.is_anonymous:
            await self.close()
            return

        self.other_id = int(self.scope['url_route']['kwargs']['recipient_id'])
        ids = sorted([self.me.id, self.other_id])
        self.room_group_name = f'chat_{ids[0]}_{ids[1]}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Send chat history on connect
        messages = await self.get_chat_history()
        for msg in messages:
            await self.send(text_data=json.dumps(msg))

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_text = data.get('message', '').strip()
        if not message_text:
            return

        msg = await self.save_message(message_text)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_text,
                'sender_id': self.me.id,
                'msg_id': msg.id if msg else None,
                'time': datetime.now().strftime('%H:%M'),
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id'],
            'msg_id': event.get('msg_id'),
            'time': event.get('time', ''),
        }))

    @database_sync_to_async
    def save_message(self, text):
        from .models import Message, User
        try:
            sender = User.objects.get(id=self.me.id)
            recipient = User.objects.get(id=self.other_id)
            return Message.objects.create(
                sender=sender,
                recipient=recipient,
                message_text=text
            )
        except Exception as e:
            print(f"Error saving message: {e}")
            return None

    @database_sync_to_async
    def get_chat_history(self):
        from .models import Message
        try:
            messages = Message.objects.filter(
                sender_id__in=[self.me.id, self.other_id],
                recipient_id__in=[self.me.id, self.other_id]
            ).order_by('send_time')[:50]
            return [
                {
                    'message': m.message_text,
                    'sender_id': m.sender_id,
                    'msg_id': m.id,
                    'time': m.send_time.strftime('%H:%M') if m.send_time else '',
                    'history': True,
                }
                for m in messages
            ]
        except Exception:
            return []
