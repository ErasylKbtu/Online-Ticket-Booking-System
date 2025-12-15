from asyncio import Event
from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import Event, Ticket
import secrets
import string

class TicketSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='event.title', read_only=True)
    event_date = serializers.CharField(source='event.formatted_date', read_only=True)
    event_time = serializers.CharField(source='event.formatted_time', read_only=True)
    event_location = serializers.CharField(source='event.location', read_only=True)
    event_image = serializers.SerializerMethodField()
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    reference_number = serializers.CharField(read_only=True)
    qr_code_data = serializers.CharField(read_only=True)
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'title', 'event', 'event_title', 'event_date', 'event_time', 
            'event_location', 'event_image', 'user', 'price', 'quantity', 
            'total_price', 'purchase_date', 'status', 'reference_number',
            'qr_code_data', 'available'
        ]
        read_only_fields = ['purchase_date', 'reference_number', 'qr_code_data', 'user']
    
    def get_event_image(self, obj):
        if obj.event and obj.event.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.event.image.url)
            return obj.event.image.url
        return None
    
    def get_total_price(self, obj):
        return obj.price * obj.quantity

class TicketPurchaseSerializer(serializers.Serializer):
    event_id = serializers.IntegerField(required=True)
    quantity = serializers.IntegerField(
        required=True, 
        min_value=1,
        max_value=10
    )
    payment_method = serializers.CharField(
        required=False, 
        default='credit_card',
        max_length=50
    )
    payment_last_four = serializers.CharField(
        required=False,
        max_length=4,
        allow_blank=True
    )
    
    def validate(self, data):
        event_id = data.get('event_id')
        quantity = data.get('quantity')
        
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            raise serializers.ValidationError("Event not found")
        
        if not event.is_active:
            raise serializers.ValidationError("Event is not active")
        
        if event.available_seats < quantity:
            raise serializers.ValidationError(f"Only {event.available_seats} seats available")
        
        data['event'] = event
        return data

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name', 'password']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data.get('username') or validated_data['email'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            password=validated_data['password']
        )
        return user

class EmailLoginSerializer(serializers.Serializer): 
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Неверный email или пароль")

        user = authenticate(username=user_obj.username, password=password)
        if not user:
            raise serializers.ValidationError("Неверный email или пароль")

        attrs['user'] = user
        return attrs

class EventSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='category', read_only=True)
    seatsLeft = serializers.IntegerField(source='available_seats', read_only=True)
    date = serializers.SerializerMethodField()
    time = serializers.SerializerMethodField()
    imageUrl = serializers.SerializerMethodField()
    
    class Meta:
        model = Event
        fields = [
            'id', 'type', 'title', 'description', 'category', 'location', 'venue',
            'date', 'time', 'price', 'seatsLeft', 'total_seats', 'available_seats',
            'imageUrl', 'image', 'is_active', 'is_featured', 'organizer',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'organizer']
    
    def get_date(self, obj):
        if hasattr(obj, 'formatted_date'):
            return obj.formatted_date
        return obj.date.strftime("%d.%m.%Y") if obj.date else ""
    
    def get_time(self, obj):
        if hasattr(obj, 'formatted_time'):
            return obj.formatted_time
        return obj.time.strftime("%H:%M") if obj.time else ""
    
    def get_imageUrl(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

def generate_reference_number():
    """Генерация уникального номера билета"""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        ref = 'TKT-' + ''.join(secrets.choice(alphabet) for _ in range(8))
        if not Ticket.objects.filter(reference_number=ref).exists():
            return ref

def generate_qr_code_data(ticket):
    """Генерация данных для QR кода"""
    import json
    from django.utils.timezone import now
    
    qr_data = {
        'ticket_id': str(ticket.id),
        'reference_number': ticket.reference_number,
        'event_id': str(ticket.event.id),
        'event_title': ticket.event.title,
        'user_id': str(ticket.user.id),
        'quantity': ticket.quantity,
        'purchase_date': ticket.purchase_date.isoformat() if ticket.purchase_date else now().isoformat(),
        'verified': False
    }
    return json.dumps(qr_data)