from django.db import models
from django.utils.text import slugify

class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        db_index=True
    )
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=220, unique=True, db_index=True)
    description = models.TextField(blank=True, default='')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField(default=0)
    image_url = models.CharField(max_length=500, blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(price__gte=0),
                name='check_product_price_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(stock_quantity__gte=0),
                name='check_product_stock_non_negative'
            ),
        ]
        indexes = [
            models.Index(fields=['category', 'is_active'], name='idx_prod_cat_active'),
            models.Index(fields=['price'], name='idx_prod_price'),
            models.Index(fields=['slug'], name='idx_prod_slug'),
        ]

    def __str__(self):
        return f"{self.name} (Stock: {self.stock_quantity})"

    @property
    def is_in_stock(self):
        return self.stock_quantity > 0

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
