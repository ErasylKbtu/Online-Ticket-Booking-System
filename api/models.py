from datetime import timezone
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
import secrets
import string

class Event(models.Model):
    CATEGORY_CHOICES = [
        ('music', 'Music'),
        ('sports', 'Sports'),
        ('conference', 'Conference'),
        ('art', 'Art & Culture'),
        ('food', 'Food & Drink'),
        ('tech', 'Technology'),
        ('other', 'Other'),
    ]
    
    title = models.CharField(max_length=200, verbose_name="Название события")
    description = models.TextField(verbose_name="Описание", blank=True, default="")
    
    category = models.CharField(
        max_length=20, 
        choices=CATEGORY_CHOICES, 
        default='music',
        verbose_name="Категория"
    )
    
    location = models.CharField(max_length=200, verbose_name="Место проведения", default="")
    venue = models.CharField(max_length=100, verbose_name="Площадка", blank=True)
    
    date = models.DateField(verbose_name="Дата события", default=timezone.now,)
    time = models.TimeField(verbose_name="Время начала", default='18:00')
    
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Цена ($)",
        validators=[MinValueValidator(0)],
        default=0.00
    )
    
    total_seats = models.PositiveIntegerField(verbose_name="Всего мест", default=200)
    available_seats = models.PositiveIntegerField(verbose_name="Доступно мест", default=200)
    
    image = models.ImageField(
        upload_to='events/images/',
        verbose_name="Изображение",
        blank=True,
        null=True
    )
    
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    is_featured = models.BooleanField(default=False, verbose_name="Рекомендуемое")
    
    organizer = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='organized_events',
        verbose_name="Организатор",
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Событие"
        verbose_name_plural = "События"
        ordering = ['date', 'title']
        app_label = 'api'
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.pk:
            self.available_seats = self.total_seats
        super().save(*args, **kwargs)
    
    @property
    def seats_left(self):
        return self.available_seats
    
    @property
    def formatted_date(self):
        return self.date.strftime("%d.%m.%Y") if self.date else ""
    
    @property
    def formatted_time(self):
        return self.time.strftime("%H:%M") if self.time else ""
    
    @property
    def is_sold_out(self):
        return self.available_seats == 0
    
    @property
    def is_upcoming(self):
        from django.utils import timezone
        if not self.date:
            return False
        return self.date >= timezone.now().date()


class Ticket(models.Model):
    STATUS_CHOICES = [
        ('pending', 'В ожидании'),
        ('confirmed', 'Подтвержден'),
        ('cancelled', 'Отменен'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', 'Кредитная карта'),
        ('debit_card', 'Дебетовая карта'),
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Банковский перевод'),
    ]
    
    title = models.CharField(max_length=100, default="Standard Ticket", verbose_name="Название билета")
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Цена за единицу"
    )
    available = models.BooleanField(default=True, verbose_name="Доступен")
    
    event = models.ForeignKey(
        Event, 
        on_delete=models.CASCADE, 
        related_name='ticket_set',
        verbose_name="Событие",
        null=True,
        blank=True
    )
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='user_tickets',
        verbose_name="Пользователь",
        null=True,
        blank=True
    )
    
    purchase_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата покупки")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус"
    )
    
    quantity = models.PositiveIntegerField(
        default=1, 
        verbose_name="Количество",
        validators=[MinValueValidator(1)]
    )
    
    reference_number = models.CharField(
        max_length=20, 
        unique=True, 
        verbose_name="Номер билета",
        blank=True,
        null=True,
        db_index=True
    )
    
    qr_code_data = models.TextField(
        verbose_name="Данные QR кода",
        blank=True,
        null=True
    )
    
    payment_method = models.CharField(
        max_length=50,
        choices=PAYMENT_METHOD_CHOICES,
        default='credit_card',
        verbose_name="Способ оплаты",
        blank=True
    )
    
    payment_last_four = models.CharField(
        max_length=4,
        blank=True,
        null=True,
        verbose_name="Последние 4 цифры карты"
    )
    
    cancelled_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Дата отмены"
    )
    
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Сумма возврата"
    )
    
    class Meta:
        verbose_name = "Билет"
        verbose_name_plural = "Билеты"
        ordering = ['-purchase_date']
        indexes = [
            models.Index(fields=['reference_number']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['event', 'status']),
        ]
    
    def __str__(self):
        if self.event:
            return f"{self.title} - {self.event.title} ({self.reference_number})"
        return f"{self.title} ({self.reference_number})"
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            self.reference_number = self.generate_reference_number()
        
        if self.event and not self.price:
            self.price = self.event.price
        
        if not self.qr_code_data and self.event and self.user:
            self.qr_code_data = self.generate_qr_code_data()
        
        if self.status == 'cancelled' and not self.cancelled_date:
            self.cancelled_date = timezone.now()
            self.refund_amount = self.total_price
        
        super().save(*args, **kwargs)
    
    @property
    def total_price(self):
        """Общая стоимость билетов"""
        return self.price * self.quantity
    
    @staticmethod
    def generate_reference_number():
        """Генерация уникального номера билета"""
        alphabet = string.ascii_uppercase + string.digits
        while True:
            ref = 'TKT-' + ''.join(secrets.choice(alphabet) for _ in range(8))
            if not Ticket.objects.filter(reference_number=ref).exists():
                return ref
    
    def generate_qr_code_data(self):
        """Генерация данных для QR кода"""
        import json
        qr_data = {
            'ticket_id': str(self.id),
            'reference_number': self.reference_number,
            'event_id': str(self.event.id) if self.event else '',
            'event_title': self.event.title if self.event else '',
            'event_date': self.event.formatted_date if self.event else '',
            'event_time': self.event.formatted_time if self.event else '',
            'user_id': str(self.user.id) if self.user else '',
            'quantity': self.quantity,
            'total_price': str(self.total_price),
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else '',
            'status': self.status,
            'verified': False
        }
        return json.dumps(qr_data)
    
    @property
    def can_be_cancelled(self):
        """Можно ли отменить билет"""
        if self.status != 'confirmed':
            return False
        
        if not self.event or not self.event.date:
            return False
        
        from django.utils import timezone
        event_datetime = timezone.make_aware(
            timezone.datetime.combine(self.event.date, self.event.time)
        )
        time_difference = event_datetime - timezone.now()
        return time_difference.total_seconds() > 24 * 60 * 60  
    
    def cancel(self, refund_amount=None):
        """Отмена билета"""
        if not self.can_be_cancelled:
            return False
        
        self.status = 'cancelled'
        self.cancelled_date = timezone.now()
        
        if refund_amount is not None:
            self.refund_amount = refund_amount
        else:
            self.refund_amount = self.total_price
        
        if self.event:
            self.event.available_seats += self.quantity
            self.event.save()
        
        self.save()
        return True