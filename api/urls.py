from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TicketViewSet, RegisterView, EmailLoginView, EventViewSet  
from . import views

router = DefaultRouter()
router.register(r'tickets', TicketViewSet, basename='ticket')
router.register(r'events', EventViewSet, basename='event')

urlpatterns = [
    path('', include(router.urls)),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', EmailLoginView.as_view(), name='email-login'),  
    path('current_user/', views.current_user, name='current_user'),
    path('change-password/', views.change_password, name='change-password'),
    
    path('tickets/<int:pk>/cancel/', 
         TicketViewSet.as_view({'post': 'cancel'}), 
         name='ticket-cancel'),
    
    path('tickets/upcoming/', 
         TicketViewSet.as_view({'get': 'upcoming'}), 
         name='ticket-upcoming'),
    
    path('tickets/stats/', 
         TicketViewSet.as_view({'get': 'stats'}), 
         name='ticket-stats'),
]