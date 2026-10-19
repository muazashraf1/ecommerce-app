from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'amount', 'status', 'provider_ref', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('provider_ref', 'order__id', 'order__user__email')
    readonly_fields = ('order', 'amount', 'status', 'provider_ref', 'created_at')
