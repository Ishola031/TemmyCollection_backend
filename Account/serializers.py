from  rest_framework import serializers
from .models import Account, PendingSignup,Notification


class AdminUserSerializer(serializers.ModelSerializer):
    # code = serializers.CharField(write_only=True)

    class Meta:
        model = Account
        fields = ( 'first_name','last_name','email', 'password')
        extra_kwargs = {
            'password': {
                'write_only': True,
                'style': {'input_type': 'password'}
            },
        }
        
class UserSerializer(serializers.ModelSerializer):
    code = serializers.CharField(write_only=True)

    class Meta:
        model = Account
        fields = ( 'email', 'code', 'username', 'first_name', 'last_name','phone_number','date_joined')
        extra_kwargs = {
            'password': {
                'write_only': True,
                'style': {'input_type': 'password'}
            },
            'username': {'required': False},
            'code': {'required': False},
            'first_name': {'read_only': True},
            'last_name': {'read_only': True},
            'phone_number': {'read_only': True},
            'date_joined': {'read_only': True},
        }

    def create(self, validated_data):
        validated_data.pop('code')

        import random

        email = validated_data.get("email")
        base = email.split("@")[0]
        randomNum = random.randint(1000, 9999)

        username = f"{base}{randomNum}"

        formData = PendingSignup.objects.get(email=email)
        user = Account.objects.create(
            email=email,
            first_name=formData.first_name,
            last_name=formData.last_name,
            username=username,
            password=formData.password
        )
        
        user.save()
        formData.delete()
        return user
    
class UserInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields =('id','username', 'first_name', 'last_name')

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'notification_type', 'is_read', 'target_url', 'created_at']