from .models import CustomerActivity


def create_customer_activity(user,activity_type,title,description='',order=None):
    if not user:
        return None

    return CustomerActivity.objects.create(
        user=user,
        activity_type=activity_type,
        title=title,
        description=description,
        order=order
    )