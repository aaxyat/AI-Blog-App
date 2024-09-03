from django.apps import AppConfig

#This defines Django app
class BlogGeneratorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blog_generator'
