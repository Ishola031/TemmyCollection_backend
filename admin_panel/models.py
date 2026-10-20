from django.db import models




class StoreSettings(models.Model):
    store_name = models.CharField(max_length=150,default="TemmyCollection",)
    store_email = models.EmailField(blank=True, default="")
    store_phone = models.CharField(max_length=30, blank=True, default="")
    store_address = models.TextField(blank=True, default="")

    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True, default="We are performing scheduled maintenance. Please check back soon.",)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Store Settings"
        verbose_name_plural = "Store Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    def __str__(self):
        return f"{self.store_name} Settings"






