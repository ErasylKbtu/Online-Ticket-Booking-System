from rest_framework import viewsets, generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import Event, Ticket
from .serializers import (
    EventSerializer, TicketSerializer, TicketPurchaseSerializer,
    RegisterSerializer, EmailLoginSerializer,
    generate_reference_number, generate_qr_code_data
)

from rest_framework.decorators import api_view, permission_classes, action
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def current_user(request):
    user = request.user

    if request.method == 'GET':
        return Response({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
        })

    elif request.method == 'PUT':
        user = request.user
        data = request.data
        user.username = data.get('username', user.username)
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.email = data.get('email', user.email)
        try:
            user.save()
        except IntegrityError:
            return Response(
                {'error': 'Username or email already exists.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response({'message': 'Profile updated successfully'})
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    new_password = request.data.get('new_password')
    if not new_password:
        return Response({'error': 'New password is required'}, status=status.HTTP_400_BAD_REQUEST)
    user.set_password(new_password)
    user.save()
    return Response({'message': 'Password changed successfully'})

class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Пользователь видит только свои билеты"""
        return Ticket.objects.filter(user=self.request.user).order_by('-purchase_date')
    
    def create(self, request, *args, **kwargs):
        """Покупка билета"""
        purchase_serializer = TicketPurchaseSerializer(data=request.data, context={'request': request})
        purchase_serializer.is_valid(raise_exception=True)
        
        event = purchase_serializer.validated_data['event']
        quantity = purchase_serializer.validated_data['quantity']
        
        with transaction.atomic():
            if event.available_seats < quantity:
                return Response(
                    {'error': f'Only {event.available_seats} seats available'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            event.available_seats -= quantity
            event.save()
            
            ticket = Ticket.objects.create(
                event=event,
                user=request.user,
                title=f"{event.title} Ticket",
                price=event.price,
                quantity=quantity,
                status='confirmed',
                reference_number=generate_reference_number(),
                qr_code_data=generate_qr_code_data({
                    'id': 0,  
                    'event': event,
                    'user': request.user,
                    'quantity': quantity,
                    'purchase_date': timezone.now(),
                    'reference_number': generate_reference_number()
                })
            )
            
            ticket.qr_code_data = generate_qr_code_data(ticket)
            ticket.save()
        
        serializer = self.get_serializer(ticket)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Отмена билета"""
        ticket = self.get_object()
        
        if ticket.status == 'cancelled':
            return Response(
                {'error': 'Ticket already cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        event_date = ticket.event.date
        if event_date:
            time_until_event = event_date - timezone.now().date()
            if time_until_event.days < 1:
                return Response(
                    {'error': 'Cannot cancel ticket less than 24 hours before event'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        with transaction.atomic():
            ticket.event.available_seats += ticket.quantity
            ticket.event.save()
            
            ticket.status = 'cancelled'
            ticket.save()
        
        return Response(
            {'message': 'Ticket cancelled successfully', 'refund_amount': float(ticket.price * ticket.quantity)},
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Получение предстоящих билетов"""
        tickets = self.get_queryset().filter(
            status='confirmed',
            event__date__gte=timezone.now().date()
        )
        serializer = self.get_serializer(tickets, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Статистика по билетам пользователя"""
        tickets = self.get_queryset()
        total_tickets = tickets.count()
        upcoming_tickets = tickets.filter(
            status='confirmed',
            event__date__gte=timezone.now().date()
        ).count()
        total_spent = sum(ticket.price * ticket.quantity for ticket in tickets.filter(status='confirmed'))
        
        return Response({
            'total_tickets': total_tickets,
            'upcoming_tickets': upcoming_tickets,
            'total_spent': float(total_spent)
        })


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        }, status=status.HTTP_201_CREATED)


class EmailLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        })
    

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [AllowAny]