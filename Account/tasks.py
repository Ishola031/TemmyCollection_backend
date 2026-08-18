from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


# @shared_task
# def send_verify_email_code(user_email, code):
#     print(user_email, code)
    