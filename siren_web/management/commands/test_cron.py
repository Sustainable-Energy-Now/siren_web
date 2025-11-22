from django.core.management.base import BaseCommand
from django.utils import timezone

class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write(f'Cron test successful at {timezone.now()}')