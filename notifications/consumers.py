from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
import json
User = get_user_model()




class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = None

        # 1. Check Query String for ?token=
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        token_list = query_params.get("token", [])

        if token_list:
            try:
                access_token = AccessToken(token_list[0])
                user_id = access_token.get("user_id")
                user = await User.objects.aget(id=user_id)
            except Exception as e:
                print("❌ Query Token Parse Error:", e)

        # 2. If no query token, parse HTTP Cookies
        if not user:
            headers = dict(self.scope.get("headers", []))
            cookie_header = headers.get(b"cookie", b"").decode("utf-8")

            cookies = {}
            for item in cookie_header.split("; "):
                if "=" in item:
                    k, v = item.split("=", 1)
                    cookies[k.strip()] = v.strip()

            token = (
                    cookies.get("access_token")
                    or cookies.get("access")
                    or cookies.get("accessToken")
                    or cookies.get("jwt")
                )
            if token:
                try:
                    access_token = AccessToken(token)
                    user_id = access_token.get("user_id")
                    user = await User.objects.aget(id=user_id)
                except Exception as e:
                    print("❌ Cookie Token Parse Error:", e)

        # 3. Accept or reject connection
        if user and not user.is_anonymous:
            self.user = user
            self.group_name = f"user_{self.user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            print(f"✅ Real-time WebSocket connected for user_{self.user.id} ({self.user.email})")
        else:
            print("❌ Anonymous WS attempt rejected")
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_notification(self, event):
            print("🔥 EVENT FROM CHANNEL LAYER:", event)
    
            response = {
                "action": event.get("action", "create"),
                "content": event.get("content", {}),
            }
    
            print("📤 SENDING TO REACT:", response)
    
            await self.send(
                text_data=json.dumps(response)
            )



