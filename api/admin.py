from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Event, Ticket
import csv
from django.http import HttpResponse

@admin.action(description="Активировать выбранные события")
def make_active(modeladmin, request, queryset):
    queryset.update(is_active=True)

@admin.action(description="Деактивировать выбранные события")
def make_inactive(modeladmin, request, queryset):
    queryset.update(is_active=False)

@admin.action(description="Отметить как рекомендованные")
def make_featured(modeladmin, request, queryset):
    queryset.update(is_featured=True)

@admin.action(description="Экспорт в CSV")
def export_to_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="events.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Title', 'Category', 'Location', 'Date', 'Price', 
        'Total Seats', 'Available Seats', 'Is Active'
    ])
    
    for event in queryset:
        writer.writerow([
            event.title, event.get_category_display(), event.location,
            event.date, event.price, event.total_seats,
            event.available_seats, event.is_active
        ])
    
    return response

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'category_display', 'location', 'date_display', 
        'price_display', 'seats_left_display', 'status_display', 
        'image_preview'
    ]
    
    list_filter = ['category', 'date', 'is_active', 'is_featured']
    search_fields = ['title', 'description', 'location']
    ordering = ['date', 'title']
    
    date_hierarchy = 'date'
    
    actions = [make_active, make_inactive, make_featured, export_to_csv]
    
    readonly_fields = ['created_at', 'updated_at', 'image_preview_large']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'category', 'organizer')
        }),
        ('Место и время', {
            'fields': ('location', 'venue', 'date', 'time')
        }),
        ('Цена и места', {
            'fields': ('price', 'total_seats', 'available_seats')
        }),
        ('Изображение', {
            'fields': ('image', 'image_preview_large')
        }),
        ('Статус', {
            'fields': ('is_active', 'is_featured')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def category_display(self, obj):
        """Отображение категории с цветом"""
        colors = {
            'music': '#ff6b6b',
            'sports': '#4ecdc4',
            'conference': '#45b7d1',
            'art': '#96ceb4',
            'food': '#feca57',
            'tech': '#5f27cd',
            'other': '#8395a7'
        }
        color = colors.get(obj.category, '#8395a7')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_category_display()
        )
    category_display.short_description = 'Категория'
    
    def date_display(self, obj):
        """Форматированная дата"""
        if obj.date:
            return format_html(
                '<span style="font-weight: bold;">{}</span>',
                obj.formatted_date
            )
        return '-'
    date_display.short_description = 'Дата'
    
    def price_display(self, obj):
        """Отображение цены"""
        if obj.price == 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">FREE</span>'
            )
        return format_html(
            '<span style="font-weight: bold;">${}</span>',
            obj.price
        )
    price_display.short_description = 'Цена'
    
    def seats_left_display(self, obj):
        """Отображение оставшихся мест с цветом"""
        if obj.available_seats == 0:
            color = 'red'
            text = 'SOLD OUT'
        elif obj.available_seats < 10:
            color = 'orange'
            text = f'{obj.available_seats} seats left'
        else:
            color = 'green'
            text = f'{obj.available_seats} seats left'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, text
        )
    seats_left_display.short_description = 'Доступно мест'
    
    def status_display(self, obj):
        """Отображение статуса события"""
        if not obj.is_active:
            return format_html(
                '<span style="color: gray; font-weight: bold;">INACTIVE</span>'
            )
        elif obj.is_featured:
            return format_html(
                '<span style="color: gold; font-weight: bold;">★ FEATURED</span>'
            )
        elif obj.is_sold_out:
            return format_html(
                '<span style="color: red; font-weight: bold;">SOLD OUT</span>'
            )
        else:
            return format_html(
                '<span style="color: green; font-weight: bold;">ACTIVE</span>'
            )
    status_display.short_description = 'Статус'
    
    def image_preview(self, obj):
        """Превью изображения в списке"""
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />',
                obj.image.url
            )
        return "No image"
    image_preview.short_description = 'Изображение'
    
    def image_preview_large(self, obj):
        """Большое превью изображения в форме"""
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 300px; height: auto; border-radius: 8px; margin: 10px 0;" />',
                obj.image.url
            )
        return "Изображение не загружено"
    image_preview_large.short_description = 'Превью изображения'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.organizer:
            obj.organizer = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(organizer=request.user)


@admin.action(description="Подтвердить выбранные билеты")
def confirm_tickets(modeladmin, request, queryset):
    queryset.update(status='confirmed')

@admin.action(description="Отменить выбранные билеты")
def cancel_tickets(modeladmin, request, queryset):
    queryset.update(status='cancelled')

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'event_link', 'user_display', 'price_display', 
        'quantity', 'total_price_display', 'status_display', 
        'purchase_date_display'
    ]
    
    list_filter = ['status', 'purchase_date', 'available', 'event__category']
    search_fields = ['title', 'event__title', 'user__username', 'user__email']
    ordering = ['-purchase_date']
    
    actions = [confirm_tickets, cancel_tickets]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'event', 'user', 'price', 'quantity')
        }),
        ('Статус', {
            'fields': ('available', 'status')
        }),
        ('Информация о покупке', {
            'fields': ('purchase_date',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['purchase_date']
    
    def event_link(self, obj):
        """Ссылка на событие"""
        if obj.event:
            url = reverse('admin:events_event_change', args=[obj.event.id])
            return format_html(
                '<a href="{}">{}</a>',
                url, obj.event.title
            )
        return "-"
    event_link.short_description = 'Событие'
    
    def user_display(self, obj):
        """Отображение пользователя"""
        if obj.user:
            return format_html(
                '<span style="font-weight: bold;">{}</span>',
                obj.user.username
            )
        return "-"
    user_display.short_description = 'Пользователь'
    
    def price_display(self, obj):
        """Отображение цены"""
        return format_html(
            '<span style="font-weight: bold;">${}</span>',
            obj.price
        )
    price_display.short_description = 'Цена за билет'
    
    def total_price_display(self, obj):
        """Отображение общей стоимости"""
        return format_html(
            '<span style="color: #27ae60; font-weight: bold;">${}</span>',
            obj.total_price
        )
    total_price_display.short_description = 'Общая стоимость'
    
    def status_display(self, obj):
        """Отображение статуса с цветом"""
        colors = {
            'pending': 'orange',
            'confirmed': 'green',
            'cancelled': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Статус'
    
    def purchase_date_display(self, obj):
        """Форматированная дата покупки"""
        return obj.purchase_date.strftime("%d.%m.%Y %H:%M")
    purchase_date_display.short_description = 'Дата покупки'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)