from django.urls import path
from .views import (
    PostListView,
    PostDetailView,
    PostCreateView,
    PostUpdateView,
    PostDeleteView,
    UserPostListView,
    home,
    about,
    ai_tools,
    docchat,
    process_documents,
    ask_question,
    notes,
    save_note,
    flashcards,
    generate_flashcards
)

urlpatterns = [
    # Blog URLs
    path('', PostListView.as_view(), name='blog-home'),
    path('user/<str:username>/', UserPostListView.as_view(), name='user-posts'),
    path('post/<int:pk>/', PostDetailView.as_view(), name='post-detail'),
    path('post/new/', PostCreateView.as_view(), name='post-create'),
    path('post/<int:pk>/update/', PostUpdateView.as_view(), name='post-update'),
    path('post/<int:pk>/delete/', PostDeleteView.as_view(), name='post-delete'),
    path('about/', about, name='blog-about'),
    
    # AI Tools URLs
    path('ai-tools/', ai_tools, name='ai-tools'),
    
    # Document Chat URLs
    path('ai-tools/docchat/', docchat, name='docchat'),
    path('ai-tools/docchat/process/', process_documents, name='process-documents'),
    path('ai-tools/docchat/ask/', ask_question, name='ask-question'),
    
    # Notes URLs
    path('ai-tools/notes/', notes, name='notes'),
    path('ai-tools/notes/save/', save_note, name='save-note'),
    
    # Flashcards URLs
    path('ai-tools/flashcards/', flashcards, name='flashcards'),
    path('ai-tools/flashcards/generate/', generate_flashcards, name='generate-flashcards'),
]