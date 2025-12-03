from django.core.management.base import BaseCommand
from chat.models import User


class Command(BaseCommand):
    help = 'Create a superuser admin account'

    def handle(self, *args, **options):
        username = 'admin'
        email = 'admin@yapper.com'
        password = 'admin123'  # Change this to something secure!
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists!'))
            user = User.objects.get(username=username)
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Updated user "{username}" to superuser'))
        else:
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" created successfully!'))
        
        self.stdout.write(self.style.SUCCESS(f'Username: {username}'))
        self.stdout.write(self.style.SUCCESS(f'Password: {password}'))
        self.stdout.write(self.style.SUCCESS('Admin URL: https://out-app-production.up.railway.app/admin/'))
