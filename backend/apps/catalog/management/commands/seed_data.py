from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.catalog.models import Category, Product

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds initial categories, products, demo admin, and demo customer'

    def handle(self, *args, **options):
        self.stdout.write("Seeding demo accounts and product catalog...")

        # 1. Create Admin
        admin_user, created = User.objects.get_or_create(
            email='admin@ecommerce.com',
            defaults={
                'full_name': 'Shop Administrator',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created admin: admin@ecommerce.com / admin123"))

        # 2. Create Demo Customer
        customer_user, created = User.objects.get_or_create(
            email='customer@ecommerce.com',
            defaults={
                'full_name': 'Ali Khan',
                'role': 'customer',
            }
        )
        if created:
            customer_user.set_password('customer123')
            customer_user.save()
            self.stdout.write(self.style.SUCCESS("Created customer: customer@ecommerce.com / customer123"))

        # 3. Create Categories
        categories_data = [
            {'name': 'Electronics', 'slug': 'electronics'},
            {'name': 'Audio', 'slug': 'audio'},
            {'name': 'Accessories', 'slug': 'accessories'},
            {'name': 'Wearables', 'slug': 'wearables'},
        ]
        cat_map = {}
        for c in categories_data:
            cat_obj, _ = Category.objects.get_or_create(slug=c['slug'], defaults={'name': c['name']})
            cat_map[c['slug']] = cat_obj

        # 4. Create Products
        products_data = [
            {
                'category': cat_map['audio'],
                'name': 'Wireless Noise Cancelling Headphones',
                'slug': 'wireless-noise-cancelling-headphones',
                'description': 'Over-ear Bluetooth headphones with active noise cancellation and 30-hour battery life.',
                'price': Decimal('4600.00'),
                'stock_quantity': 15,
                'image_url': 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800&q=80',
                'is_active': True,
            },
            {
                'category': cat_map['accessories'],
                'name': 'USB-C Fast Charging Braided Cable (2m)',
                'slug': 'usb-c-fast-charging-cable',
                'description': 'Durable nylon braided high-speed 60W power delivery cable.',
                'price': Decimal('400.00'),
                'stock_quantity': 50,
                'image_url': 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=800&q=80',
                'is_active': True,
            },
            {
                'category': cat_map['electronics'],
                'name': 'Mechanical Gaming Keyboard (RGB)',
                'slug': 'mechanical-gaming-keyboard',
                'description': 'Tactile mechanical switches with customizable per-key RGB backlighting and wrist rest.',
                'price': Decimal('6200.00'),
                'stock_quantity': 8,
                'image_url': 'https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=800&q=80',
                'is_active': True,
            },
            {
                'category': cat_map['electronics'],
                'name': 'Ergonomic Precision Wireless Mouse',
                'slug': 'ergonomic-wireless-mouse',
                'description': 'Sculpted design for all-day comfort with multi-device Bluetooth connectivity.',
                'price': Decimal('2850.00'),
                'stock_quantity': 12,
                'image_url': 'https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=800&q=80',
                'is_active': True,
            },
            {
                'category': cat_map['wearables'],
                'name': 'AMOLED Smart Watch with Heart Rate Monitor',
                'slug': 'amoled-smart-watch',
                'description': 'Fitness tracker with SpO2 sensor, sleep analysis, and water resistance.',
                'price': Decimal('7500.00'),
                'stock_quantity': 5,
                'image_url': 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&q=80',
                'is_active': True,
            },
            {
                'category': cat_map['audio'],
                'name': 'Portable Waterproof Bluetooth Speaker',
                'slug': 'portable-waterproof-speaker',
                'description': 'IPX7 waterproof speaker delivering punchy 360-degree bass.',
                'price': Decimal('3200.00'),
                'stock_quantity': 0, # Out of stock item for testing AC2 / error paths
                'image_url': 'https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=800&q=80',
                'is_active': True,
            },
            {
                'category': cat_map['accessories'],
                'name': 'Aluminum Laptop Stand (Adjustable)',
                'slug': 'aluminum-laptop-stand',
                'description': 'Ventilated desktop riser compatible with all laptops up to 16 inches.',
                'price': Decimal('1900.00'),
                'stock_quantity': 20,
                'image_url': 'https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=800&q=80',
                'is_active': True,
            },
            {
                'category': cat_map['electronics'],
                'name': '1080p Full HD Pro Streaming Webcam',
                'slug': 'pro-streaming-webcam',
                'description': 'Crisp autofocus webcam with dual stereo noise-reduction microphones.',
                'price': Decimal('4100.00'),
                'stock_quantity': 1, # Last 1 item in stock for concurrency testing
                'image_url': 'https://images.unsplash.com/photo-1588702547919-26089e690ecc?w=800&q=80',
                'is_active': True,
            },
        ]

        for p_data in products_data:
            prod, _ = Product.objects.get_or_create(
                slug=p_data['slug'],
                defaults=p_data
            )

        self.stdout.write(self.style.SUCCESS("Database seeded successfully with 8 products and 2 demo accounts!"))
