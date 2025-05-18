from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
#all we are doing here is for the database
# Create your models here.
#this is a class
class Post(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    date_posted = models.DateTimeField(default=timezone.now)
    author= models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse("post_detail", kwargs={"pk": self.pk})
    
def user_directory_path(instance, filename):
    # Files will be uploaded to MEDIA_ROOT/user_<id>/documents/<filename>
    return f'user_{instance.owner.id}/documents/{filename}'

class Document(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to=user_directory_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    session_id = models.CharField(max_length=36, blank=True)
    
    def filename(self):
        return os.path.basename(self.file.name)
    
    def __str__(self):
        return f"{self.filename()} (user: {self.owner.username})"