from django.shortcuts import render
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from product.models import Product
from .models import Cart,  CartItem, Variation, Order, ShippingAddress, State, Payment,OrderItem
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from .serializers import CartSerializer, CartItemSerializer, OrderSerializer, ShippingAddressSerializer, StateSerializer, OrderItemSerializer
from django.db.models import Q
import requests
import uuid
from django.conf import settings
from decimal import Decimal
from .tasks import release_unpaid_order_reservation



@api_view(['GET'])
@permission_classes([AllowAny])
def CartApi(request):
    user = request.user
    cart_id = request.GET.get('cart_id', None)
    refresh_token = request.COOKIES.get('refresh_token')
    cart = None
    
    # 1. Fetch the Cart efficiently, prefetching cart items to avoid N+1 query problems
    if user.is_authenticated:
        cart = Cart.objects.filter(user=user, is_active=True).first()
    elif cart_id:
        cart = Cart.objects.filter(cart_id=cart_id, user__isnull=True).first()
        

    if not cart:
        if refresh_token:
            return Response({"error": "Token expire"}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            return Response({"error": "Cart not found"}, status=status.HTTP_200_OK)
    
    # 2. Process stock adjustments cleanly in place
    updated_items = []
    for item in cart.cartitems.all():
        has_variation = bool(item.variations)
        stock_pool = item.variations.stock if has_variation else item.product.stock
        
        # Check if anything actually needs to change to avoid unnecessary database hits
        changes_made = False

        if stock_pool > 0:
            if item.quantity > stock_pool:
                # Stock exists but requested quantity is too high -> cap quantity and deactivate
                item.quantity = stock_pool
                item.is_active = True
                changes_made = True
            elif not item.is_active:
                # Stock exists and quantity is fine, but it was previously deactivated -> reactivate
                item.is_active = True
                changes_made = True
        else:
            # Completely out of stock -> deactivate
            if item.is_active:
                item.is_active = False
                changes_made = True

        if changes_made:
            item.save()
            
    serializer = CartSerializer(cart)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
@transaction.atomic
def add_to_cartApi(request):
    user = request.user
    product_id = request.data.get("product_id")
    quantity = int(request.data.get("quantity", 1))
    print(request.data)
    
    # CHECK PRODUCT
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return Response({"error": "Product not found"}, status=404)
    
    # CHECk IF USER IS AUTHENTICATED
    if user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=user, is_active=True)
    else:
        if not user.is_authenticated and request.COOKIES.get('refresh_token'):
            return Response(
                {"error": "Access token expired", "code": "token_not_valid"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        cart_id = request.data.get("cart_id")
        if cart_id:
            try:
                cart = Cart.objects.get(cart_id=cart_id, user__isnull= True, is_active=True)
            except Cart.DoesNotExist:
                cart =  Cart.objects.create(user=None, is_active=True)
        else:
            cart =  Cart.objects.create(user=None, is_active=True)
    

    variations_id = request.data.get('variations')
    product_variations = product.variations.all().first()

    if product_variations:
        if not variations_id:
        #     cart_item, item_created = CartItem.objects.get_or_create(
        #     cart=cart,
        #     product=product,
        #     # defaults={"quantity": quantity}
        # )
            return Response({"error": "Please select a product variation"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            variations = Variation.objects.get(id=variations_id)
            cart_item, item_created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                variations= variations,
                defaults={"quantity": quantity}
            )

    else:
        cart_item, item_created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={"quantity": quantity}
        )
    
    if not item_created:
        new_quantity = cart_item.quantity + quantity
    else:
        new_quantity = quantity

    # Check stock properly
    if product_variations:
        if new_quantity > cart_item.variations.stock:
            return Response({"insufficient": "No more item"})
    else:
        if new_quantity > product.stock :
            return Response({"insufficient": "No more item"})

    # Save new quantity
    cart_item.quantity = new_quantity
    cart_item.save()

    return Response({
        "message": "Item added to cart",
        "cart_id": cart.cart_id,
        "cartitem": CartItemSerializer(cart_item).data,
        "quantity": cart_item.quantity,
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
@transaction.atomic
def RemoveCart(request):
    remove = request.GET.get('f', None)
    user = request.user
    cartitem_id = request.data.get('cartitemID')
    cartId = request.data.get('cartID')
    print(request)
    if user.is_authenticated:
        try:
            cart = Cart.objects.get(user=user, is_active=True)
        except Cart.DoesNotExist:
            return Response({'error': 'cart does not exist'})    
    else:
        if not user.is_authenticated and request.COOKIES.get('refresh_token'):
            return Response(
                {"error": "Access token expired", "code": "token_not_valid"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if cartId:
            try:
                cart = Cart.objects.get(cart_id=cartId, user__isnull = True, is_active= True)
            except Cart.DoesNotExist:
                return Response({'error': 'cart has being deleted'})
        else:
            return Response({'error': 'cart does not exist'}, status=404)
    
    try:
        cartitem = cart.cartitems.get(id=cartitem_id, cart=cart)
    except CartItem.DoesNotExist:
        return Response({'error': 'cart item does not exist'})
    
    if remove:
        cartitem.delete()
        return  Response({"delete": 'cart item deleted'})
    else:
        if cartitem.quantity > 1:
            cartitem.quantity -= 1
            cartitem.save()
            return  Response({"increment": 'cart item has been incremented'})
        else:
            cartitem.delete()
            return Response({"delete": 'cart item deleted'})

@api_view(['GET'])
@permission_classes([AllowAny])
def CartCountApi(request):
    user = request.user
    cart_id = request.GET.get('cart_id', None)
    print('data',request.GET)
    if user.is_authenticated:
        cart = user.carts.filter(is_active=True).first()
    elif cart_id:
        cart = Cart.objects.filter(cart_id=cart_id,is_active=True).order_by('-date_added').first()
    
    if cart:
        # cartItems = cart.cartitems.all()
        serializer = CartSerializer(cart, many=True)
        # cartcount = 0
        # cartitems = cart.cartitems.all()
        # for item in cartitems:
        #     if item.is_active == True:
        #         cartcount += item.quantity

        return Response({'cart': serializer.data}, status=200)
    else:
        return Response({'message', 'No cart.'}, status=200)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def CheckoutViewApi(request):
    user = request.user
    if user.is_authenticated:
        order = user.orders.filter(Q(status='Pending') | Q(status='Cancelled')).order_by('-created_at').first()
    
    if order:
        serializer = OrderSerializer(order)
        return Response({'success': True, 'order': serializer.data}, status=status.HTTP_200_OK)
    return Response({'Not Found': 'No order found'}, status=404)

@api_view(['GET'])
@permission_classes([AllowAny])
def StateViewApi(request):
    states = State.objects.all()
    serializer = StateSerializer(states, many=True)
    return Response(serializer.data, status=200)

@api_view(['POST'])
@transaction.atomic
@permission_classes([IsAuthenticated])
def mergeCartApi(request):
    cart_id = request.data.get('cart_id')
    user = request.user
    if cart_id:
        if user.is_authenticated:
            try:
                cart = Cart.objects.get(cart_id=cart_id, is_active=True)
            except Cart.DoesNotExist:
                return Response({'nocart': 'No Cart'})
            
            usercart = Cart.objects.filter(user=user, is_active=True).order_by('-date_added').first()
            if not usercart:
                cart.user = user
                cart.save()
                return Response({'merge': 'successfully'})
            else:
                cartitems = cart.cartitems.all()
                for item in cartitems:
                    try:
                        checkitem = usercart.cartitems.get(variations=item.variations, product=item.product)
                        checkitem.quantity = item.quantity
                        checkitem.save()
                    except CartItem.DoesNotExist:
                        item.pk = None 
                        item.cart = usercart
                        item.save()
                cart.delete()
        else:
            return Response({'unauthenticated': 'User is not login'})
            
        return Response({'merge': 'Successfully'})
    else:
        return Response({'no_merge': 'No Cart Id'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    user = request.user
    tx_ref = str(uuid.uuid4())
    
    with transaction.atomic():
        # 1. Fetch active cart & pending order
        cart = Cart.objects.filter(user=user, is_active=True).order_by('-date_added').first()
        if not cart:
            return Response({"error": "No active cart found"}, status=status.HTTP_400_BAD_REQUEST)
            
        order = user.orders.filter(Q(status='Pending') | Q(status='Cancelled')).first()
        if not order:
            return Response({"error": "No active order found"}, status=status.HTTP_400_BAD_REQUEST)

        cart_items = cart.cartitems.filter(is_active=True)
        if not cart_items.exists():
            return Response({"error": "Your cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

        messages_list = []
        has_stock_issues = False

        # ==========================================
        # PASS 1: VALIDATE ALL ITEMS FIRST (NO DEDUCTIONS)
        # ==========================================
        for item in cart_items:
            has_variation = bool(item.variations)
            stock_pool = item.variations.stock if has_variation else item.product.stock

            if stock_pool <= 0:
                messages_list.append({"message": f"{item.product.name} is completely out of stock."})
                item.is_active = False
                item.save()
                has_stock_issues = True
                
            elif item.quantity > stock_pool:
                messages_list.append({
                    "message": f"{item.product.name} stock ({stock_pool}) is less than your requested quantity ({item.quantity}). Adjusted in your cart."
                })
                item.quantity = stock_pool
                item.save()
                has_stock_issues = True

        # If ANY item had stock issues, STOP HERE without deducting anything
        if has_stock_issues:
            return Response({
                "error": "Some items in your cart had stock changes. Please review your cart before completing payment.",
                "notifications": messages_list
            }, status=status.HTTP_400_BAD_REQUEST)


        # ==========================================
        # PASS 2: RESERVE STOCK & BUILD ORDER
        # ==========================================
        running_total = Decimal('0.00')

        for item in cart_items:
            has_variation = bool(item.variations)
            
            # Row-level locking to prevent race conditions during concurrent checkouts
            if has_variation:
                variation = type(item.variations).objects.select_for_update().get(pk=item.variations.pk)
                price = variation.price
                # Deduct variation stock
                variation.stock -= item.quantity
                variation.save()
            else:
                product = type(item.product).objects.select_for_update().get(pk=item.product.pk)
                price = product.price
                # Deduct main product stock
                product.stock -= item.quantity
                product.save()

            # Calculate Price after discount
            discount = Decimal(item.product.discount or 0)
            final_price = price
            if discount > 0:
                final_price = price * (Decimal('100') - discount) / Decimal('100')
            
            running_total += final_price * item.quantity

            # Sync with OrderItem
            lookup_kwargs = {"order": order, "product": item.product}
            if has_variation:
                lookup_kwargs["variation"] = item.variations

            OrderItem.objects.update_or_create(
                **lookup_kwargs,
                defaults={
                    "quantity": item.quantity,
                    "discount": discount,
                    "price": price
                }
            )

        print('hii')
        if running_total <= 0:
            return Response({"error": "Invalid cart total."}, status=status.HTTP_400_BAD_REQUEST)
        print('hi')
        running_total += order.shipping_price
        order.sub_total = running_total
        order.status = 'Pending'
        order.save()

        currency = "NGN"
        redirect_url = f"{settings.BASE_URL}/payment-status"
        
        # Create Payment Record
        payment_transaction, created = Payment.objects.update_or_create(
            ref=tx_ref,
            defaults={
                "gateway": 'Flutterwave',
                "amount": running_total,
                "currency": currency,
                "user": user,
                "status": 'pending'
            }
        )
        order.payment = payment_transaction
        order.save()

    # Schedule background release task (Runs in 15 minutes if unpaid)
    transaction.on_commit(
        lambda: release_unpaid_order_reservation.apply_async(args=[order.order_number], countdown=30)
    )

    # 3. Flutterwave Integration
    flutterwave_payload = {
        "tx_ref": tx_ref,
        "amount": str(running_total),
        "currency": currency,
        "redirect_url": redirect_url,
        "customer": {
            "email": user.email,
            "name": f"{order.shipping_address.first_name} {order.shipping_address.last_name}" if getattr(order, 'shipping_address', None) else user.get_full_name(),
            "phonenumber": getattr(order.shipping_address, 'phone1', '') if getattr(order, 'shipping_address', None) else "",
        },
        "customizations": {
            "title": "TemmyCollection Payment"
        }
    }
    
    headers = {
        "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            'https://api.flutterwave.com/v3/payments',
            json=flutterwave_payload,
            headers=headers,
            timeout=30
        )
        return Response({
            "payment_gateway": response.json(),
            "notifications": messages_list
        }, status=status.HTTP_200_OK)

    except requests.exceptions.RequestException as e:
        return Response(
            {"error": "Payment initiation failed", "details": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    
@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def payment_callback(request):
    # Support both GET (redirect params) and POST body params
    status_param = request.GET.get('status') or request.data.get('status')
    tx_ref = request.GET.get('tx_ref') or request.data.get('tx_ref')
    transaction_id = request.GET.get('transaction_id') or request.data.get('transaction_id')
    user = request.user

    if not tx_ref:
        return Response({'error': 'Transaction reference missing'}, status=status.HTTP_400_BAD_REQUEST)

    # 1. SUCCESSFUL FLUTTERWAVE REDIRECT / CALLBACK
    if status_param == 'successful' and transaction_id:
        headers = {
            'Authorization': f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}"
        }

        try:
            response = requests.get(
                f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify",
                headers=headers,
                timeout=30
            )
            response_data = response.json()
        except requests.exceptions.RequestException as e:
            return Response(
                {'message': 'Failed to reach Flutterwave API', 'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        if response_data.get('status') == 'success':
            payment_data = response_data.get('data', {})
            paid_amount = Decimal(str(payment_data.get('amount', 0)))
            paid_currency = payment_data.get('currency')
            flw_status = payment_data.get('status')

            with transaction.atomic():
                try:
                    # Row-level lock on Payment object
                    payment = Payment.objects.select_for_update().get(ref=tx_ref)
                except Payment.DoesNotExist:
                    return Response({'error': 'Payment record not found'}, status=status.HTTP_404_NOT_FOUND)

                # Check if already processed (Idempotency check)
                if payment.status == 'successful':
                    return Response({
                        'message': 'Payment already verified!',
                        'subMessage': 'Your order has been confirmed.'
                    }, status=status.HTTP_200_OK)

                # Validate amount, currency, and verification status using Decimal
                if flw_status == 'successful' and paid_amount == Decimal(str(payment.amount)) and paid_currency == payment.currency:
                    # Mark Payment & Order as Completed
                    payment.status = 'successful'
                    payment.payment_method = payment_data.get('payment_type')
                    payment.gateway = 'Flutterwave'
                    payment.paid_at = payment_data.get('created_at')
                    payment.save()

                    order = payment.order
                    order.status = 'Successful'  # or 'Paid' / 'Completed'
                    order.save()

                    # Deactivate active user cart
                    cart = Cart.objects.filter(user=user, is_active=True).first()
                    if cart:
                        cart.is_active = False
                        cart.save()

                    return Response({
                        'message': 'Payment successful!',
                        'subMessage': 'You have successfully completed your purchase.'
                    }, status=status.HTTP_200_OK)
                else:
                    # Amount/Currency mismatch fraud check -> release stock
                    _release_order_stock(payment.order)
                    payment.status = 'failed'
                    payment.save()
                    return Response({
                        'message': 'Payment verification failed due to data mismatch.',
                        'subMessage': 'Amount or currency did not match order details.'
                    }, status=status.HTTP_400_BAD_REQUEST)

    # 2. FAILED OR CANCELLED PAYMENT PATH -> RESTORE STOCK IMMEDIATELY
    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().get(ref=tx_ref)
            if payment.status == 'pending':
                _release_order_stock(payment.order)
                payment.status = 'cancelled'
                payment.save()
        except Payment.DoesNotExist:
            pass

    return Response({
        'message': 'Payment was not successful or was cancelled.',
        'subMessage': 'Your reserved stock has been returned.'
    }, status=status.HTTP_400_BAD_REQUEST)

def _release_order_stock(order):
    """Helper method to return reserved stock back to inventory."""
    if order and order.status == 'Pending':
        for item in order.orderitems.select_related('product', 'variation').all():
            if item.variation:
                variation = type(item.variation).objects.select_for_update().get(pk=item.variation.pk)
                variation.stock += item.quantity
                variation.save()
            elif item.product:
                product = type(item.product).objects.select_for_update().get(pk=item.product.pk)
                product.stock += item.quantity
                product.save()

        order.status = 'Cancelled'
        order.save()

@api_view(['GET'])
@permission_classes([IsAuthenticated]) 
def userAddressApi(request):
    user = request.user
    addressID = request.GET.get('addressID')
    # print(addressID)

    if addressID:
        user_addresses = ShippingAddress.objects.filter(id=addressID).first()
        if user_addresses:
            serializer = ShippingAddressSerializer(user_addresses)
    else:
        user_addresses = user.shipping_addresses.all()
        if user_addresses:
            serializer = ShippingAddressSerializer(user_addresses, many=True)
    if user_addresses:
        return Response(serializer.data)
    return Response({'Not Found': "User does't have any address"}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def CreateUserAddress(request):
    user = request.user
    data = request.data
    addressID = data.get('id')
    state = State.objects.filter(id=data.get('state')).first()
    if not state:
        return Response({'error': 'Selected State not found'}, status=400)
    
    if addressID:
        shipmentAddress = ShippingAddress.objects.filter(id=data.get('id')).first()
        serializer = ShippingAddressSerializer(shipmentAddress, data={**data}, partial=True)
    else:
        serializer = ShippingAddressSerializer(data={**data}, partial=True)
    
    if serializer.is_valid():
        serializer.save(user=user,state_id=state.id)

        
        return Response({'success': 'success', 'data': serializer.data})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def CreatecheckoutApi(request):
    try:
        user = request.user
        data = request.data
        shipping_address = data.get('shipping_address')

        # 1. Verify Active Cart
        cart = Cart.objects.filter(user=user, is_active=True).order_by('-date_added').first()
        if not cart:
            return Response({'error': 'No Cart Found'}, status=404)
            
        if not shipping_address:
            # Get target State zone pricing
            state = State.objects.filter(id=data.get('state')).first()
            if not state:
                return Response({'error': 'Selected State not found'}, status=400)
        else:
            shipping_addressOBJ = ShippingAddress.objects.filter(id=shipping_address).first()
            if not shipping_addressOBJ:
                return Response({'error': 'Invalid shipping address'}, status=404)
            state = shipping_addressOBJ.state
        
        cartcount = 0
        running_total = 0
        cartitems = cart.cartitems.all()
        for item in cartitems:
            if item.is_active == True:
                has_variation = bool(item.variations)
                discount = Decimal(item.product.discount or 0)
                price = item.variations.price if has_variation else item.product.price
                cartcount += item.quantity
                final_price = price
                if discount > 0:
                    final_price = price * (Decimal('100') - discount) / Decimal('100')
                running_total += final_price * item.quantity

        shipping_price = state.zone.price * cartcount

        sub_total = float(running_total) + float(shipping_price)
        # 2. Check for Pending Order
        order = user.orders.filter(Q(status='Pending') | Q(status='Cancelled')).order_by('-created_at').first()
        
        if order:
            if not shipping_address:
                shipmentAddress = ShippingAddress.objects.filter(id=order.shipping_address.id).first()
            else:
                shipmentAddress = ShippingAddress.objects.filter(id=shipping_address).first()
    
            # Update the existing pending order
            order_serializer = OrderSerializer(
                order, 
                data={**data, 'shipping_price': shipping_price, 'sub_total': sub_total, 'total_price': float(running_total)}, 
                partial=True
            )
            status_code = status.HTTP_200_OK
            
        else:
            # Create brand new Shipping Address

            if not shipping_address:
                shipmentAddress = ShippingAddress.objects.create(
                    address_type= data.get('address_type'),
                    user=user, 
                    first_name=data.get('first_name'), 
                    last_name=data.get('last_name'),
                    phone1=data.get('phone1'), 
                    phone2=data.get('phone2'), # Handled perfectly here
                    address_line_1=data.get('address_line_1'),
                    country=data.get('country', 'Nigeria'), 
                    state=state, 
                    city=data.get('city')
                )
            else:
                shipmentAddress = ShippingAddress.objects.filter(id=shipping_address).first()
            
            # Create brand new Order
            order_serializer = OrderSerializer(
                data={
                    **data, 
                    'shipping_price': shipping_price, 
                    'sub_total': sub_total,
                    'total_price': float(running_total)
                }, partial = True
            )
            status_code = status.HTTP_201_CREATED
            
                
        # 3. Finalize and Save Order Serializer
        if order_serializer.is_valid():
            order_serializer.save(user=user,shipping_address=shipmentAddress)
            return Response({'success': True, 'order': order_serializer.data}, status=status_code)
        
        return Response(order_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def OrderView(request):
    user = request.user
    orders = user.orders.all()
    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def OrderDetailView(request):
    orderID = request.GET.get('orderID')
    print(orderID)
    order = Order.objects.filter(order_number=orderID).first()
    orderitems = order.orderitems.all()
    total = 0 
    for orderItem in orderitems:
        total += orderItem.price
    serializer = OrderSerializer(order)
    orderItems_serializer = OrderItemSerializer(orderitems, many=True)
    return Response({
        'order': serializer.data,
        'orderItems': orderItems_serializer.data,
        'total': total,
        }, status=status.HTTP_200_OK)