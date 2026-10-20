from django.shortcuts import render, redirect
from .models import Account, EmailVerification, PendingSignup
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .serializers import UserSerializer, AdminUserSerializer
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
import random
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.http import HttpResponseRedirect

# Create your views here.
@api_view(['GET'])
@permission_classes([AllowAny])
def CheckEmail(request):
    email = request.GET.get('email')
    print(email)
    try:
        email= Account.objects.get(email=email)
    except Account.DoesNotExist:
        return Response({ "unregistered":'email is not registered to an account yet'},status=404)
    return Response({"registered":'email found'},status=200)

@api_view(['POST'])
@permission_classes([AllowAny])
def sendVerifyEmailCode(request):
    try:
        email = request.data.get("email")
        first_Name = request.data.get("first_Name")
        last_Name = request.data.get("last_Name")
        email = request.data.get("email") 
        password = request.data.get("password")

        if not email:
            return Response({"error": "email is required"})

        if Account.objects.filter(email=email).exists():
            return Response({"error": "email is already used"})

        otp = str(random.randint(100000, 999999))
        hashed_otp = make_password(otp)


        PendingSignup.objects.update_or_create(
            email=email,
            defaults={
                "first_name": first_Name,
                "last_name": last_Name,
                "password": make_password(password),
            }
        )
        print("OTP:", otp)
        # send_verify_email_code.delay(email ,otp)
        user_html_content = render_to_string(
            "email/verifyemail.html",
            {
                "code": otp
            }
        )
        user_email_message = EmailMultiAlternatives(
            subject="Email verification",
            body="Email verification.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )

        user_email_message.attach_alternative(user_html_content, "text/html")
        user_email_message.send(fail_silently=False)

        EmailVerification.objects.update_or_create(
            email=email,
            defaults={"code": hashed_otp}
        )
        return Response({"success": "Verification code sent!"})

    except Exception as e:
        print("Send verification error:", str(e))
        return Response({"error": "couldn't send code"})

class CreateUser(generics.CreateAPIView):
    serializer_class = UserSerializer
    queryset = Account.objects.all()
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        code = serializer.validated_data['code']
        email = serializer.validated_data['email']

        try:
            Account.objects.get(email=email)
            return Response({"error": "email is already used"}, status=400)
        except Account.DoesNotExist:
            pass

        try:
            record = EmailVerification.objects.get(email=email)
        except EmailVerification.DoesNotExist:
            return Response({"error": "Resend code and verify your email"}, status=400)

        if not check_password(code, record.code):
            return Response({"error": "Invalid code"}, status=400)

        if record.is_expired():
            return Response({"error": "Code expired"}, status=400)

        record.delete()
        serializer.save()

        return Response({"success": "Account Created"}, status=201)

class UserDetailView(generics.RetrieveUpdateAPIView):
    queryset = Account.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


@api_view(['POST'])
@permission_classes([AllowAny])
def ResendVerifyEmailCode(request):
    try:
        email = request.data.get("email")

        if not email:
            return Response({"error": "email is required"})

        if Account.objects.filter(email=email).exists():
            return Response({"error": "email is already used"})

        otp = str(random.randint(100000, 999999))
        hashed_otp = make_password(otp)

        print("OTP:", otp)

        # send_verify_email_code.delay(email ,otp)
        user_html_content = render_to_string(
            "email/verifyemail.html",
            {
                "code": otp
            }
        )

        user_email_message = EmailMultiAlternatives(
            subject="Email verification",
            body="Email verification.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )

        user_email_message.attach_alternative(user_html_content, "text/html")
        user_email_message.send(fail_silently=False)

        EmailVerification.objects.update_or_create(
            email=email,
            defaults={"code": hashed_otp}
        )
        obj = EmailVerification.objects.get(email=email)

        cooldown = 60 
        elapsed = (timezone.now() - obj.created_at).total_seconds()
        remaining = cooldown - elapsed

        return Response({"success": "Verification code sent!", "remaining": int(remaining)})

    except Exception as e:
        print("Send verification error:", str(e))
        return Response({"error": "couldn't send code"})


@api_view(['GET'])
@permission_classes([AllowAny])
def resend_status(request):
    email = request.GET.get("email")
    formData = PendingSignup.objects.filter(email=email).first()

    if not formData:
        return Response(
            {"error": "Registration Error"},
            status=400
        )
    
    if formData.is_expired():
        return Response({"error": "Registration Error"},status=400)
    
    try:
        obj = EmailVerification.objects.filter(email=email).latest("created_at")
        created = obj.created_at
    except EmailVerification.DoesNotExist:
        return Response({"can_resend": True, "remaining": 0})
    
    cooldown = 60 
    elapsed = (timezone.now() - created).total_seconds()

    remaining = cooldown - elapsed

    if remaining > 0:
        return Response({
            "can_resend": False,
            "remaining": int(remaining),
        })

    return Response({
        "can_resend": True,
        "remaining": 0,
    })
        
class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *items, **kwargs):
        # 1. Let SimpleJWT authenticate the user and generate tokens
        response = super().post(request, *items, **kwargs)
        
        if response.status_code == status.HTTP_200_OK:
            tokens = response.data
            access_token = tokens['access']
            refresh_token = tokens['refresh']
            
            # 2. Clear tokens from the JSON response body so JavaScript can't read them
            response.data = {'success': True}

            # 3. Set the Access Token Cookie
            response.set_cookie(
                key='access_token',
                value=access_token,
                max_age=15 * 60,
                httponly=True,     
                samesite='Lax',    
                secure=False,      
                path='/'
            )
            
            # 4. Set the Refresh Token Cookie (Optional, but recommended for persisting sessions)
            if refresh_token:
                response.set_cookie(
                    key='refresh_token',
                    value=refresh_token,
                    max_age=7 * 24 * 60 * 60, 
                    httponly=True,
                    samesite='Lax',
                    secure=False,
                    path='/'
                )
                
            return response
        else:
            return Response({'success': False})
        
class CustomRefreshTokenView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        try:
            refresh_token = request.COOKIES.get('refresh_token')
            request.data['refresh'] = refresh_token
            response = super().post(request, *args, **kwargs)
            tokens = response.data
            access_token = tokens['access']

            res = Response()
            res.data = {'refreshed': True}

            res.set_cookie(
                key='access_token',
                value=access_token,
                httponly=True,     # Keeps token safe from XSS attacks
                max_age= 15 * 60,    
                samesite='Lax',    # CSRF protection
                secure=False,      # Set to True in production (HTTPS)
                path='/'
            )
            return res
        except:
            return Response()


@api_view(['POST'])    
@permission_classes([IsAuthenticated]) 
def LogoutView(request):
    try:
        res = Response()
        res.data = {'success': True}
        res.delete_cookie('access_token', path='/', samesite='None')
        res.delete_cookie('refresh_token', path='/', samesite='None')

        return res
    except:
        return Response({'success': False})


@api_view(['POST', 'GET'])
@permission_classes([AllowAny]) 
def is_authenticated(request):
    if request.user and request.user.is_authenticated:
        return Response({'isAuthenticated': True, 'user': UserSerializer(request.user).data})
    return Response({'isAuthenticated': False, 'user': None}, status=401)


@login_required
def google_login_callback(request):
    user = request.user
    
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    response = HttpResponseRedirect("http://localhost:3000/login/callback")

    response.set_cookie(
        key='access_token',
        value=access_token,
        max_age=30,
        httponly=True,   
        secure=False,    
        samesite='Lax'
    )

    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        max_age=7 * 24 * 60 * 60, 
        httponly=True,
        secure=False,    
        samesite='Lax'
    )

    return response

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_login(request):
    email = request.data.get('email')
    password = request.data.get('password')
    print(request.data)

    user = authenticate(email=email, password=password)

    if user is None:
        return Response({'message': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    
    if not user.is_staff:
        return Response({'message': 'You are not authorized to access the admin site.'}, status=status.HTTP_403_FORBIDDEN)
    

    refresh = RefreshToken.for_user(user)
    refresh_token = str(refresh)
    access_token = str(refresh.access_token)
    res = Response()
    res.data = {'success': 'login successful'}

    res.set_cookie(
        key='access_token',
        value=access_token,
        max_age= 15 * 60,
        httponly=True,     
        samesite='Lax',    
        secure=False,      
        path='/'
    )
            
    
    if refresh_token:
        res.set_cookie(
            key='refresh_token',
            value=refresh_token,
            max_age=7 * 24 * 60 * 60, 
            httponly=True,
            samesite='Lax',
            secure=False,
            path='/'
        )
                
    return res

@api_view(['POST'])
@permission_classes([AllowAny])
def admin_signup(request):
    data = request.data
    password = data.get('')
    password2 = data.get('')
    print(data)
    if password != password2:
        return Response()
    
    serializer = AdminUserSerializer(data={**data}, partial = True)
    if serializer.is_valid():
        serializer.save(password=make_password(data.get('password')), is_not_user=True)
        return Response({'success': 'Account Created successfully'}, status=200)
    return Response({'s': serializer.errors,'error': 'Error, Please try again later.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def IsAdminAuthenticated(request):
    user = request.user
    if user.is_staff:
        return Response({'isAuthorized': True}, status=status.HTTP_200_OK)
    return Response({'isAuthorized': False}, status=status.HTTP_401_UNAUTHORIZED)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def userDetails(request):
    user = request.user
    serializer = UserSerializer(user)
    return Response(serializer.data)



