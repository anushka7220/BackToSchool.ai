from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView
)
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib.auth.decorators import login_required
import os
import logging
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from .models import Post
from django.conf import settings
import uuid

# Set up logging
logger = logging.getLogger(__name__)

# Configure API key (use environment variables in production)
GOOGLE_API_KEY = "AIzaSyC-kXQEZb_WILuVCML2vLNX0PvpE8RTjKU"  
# ==================== BLOG VIEWS ====================

def home(request):
    context = {
        'posts': Post.objects.all()
    }
    return render(request, 'blog/home.html', context)

class PostListView(ListView):
    model = Post
    template_name = 'blog/home.html'
    context_object_name = 'posts'
    ordering = ['-date_posted']
    paginate_by = 5

class UserPostListView(ListView):
    model = Post
    template_name = 'blog/user_posts.html'
    context_object_name = 'posts'
    paginate_by = 5

    def get_queryset(self):
        user = get_object_or_404(User, username=self.kwargs.get('username'))
        return Post.objects.filter(author=user).order_by('-date_posted')

class PostDetailView(DetailView):
    model = Post

class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    fields = ['title', 'content']
    
    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Post
    fields = ['title', 'content']

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author

class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Post
    success_url = '/'

    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author

def about(request):
    return render(request, 'blog/about.html', {'title': 'About'})

# ==================== AI TOOLS VIEWS ====================

def ai_tools(request):
    return render(request, 'blog/base.html')



# ----- Document Chat -----

def docchat(request):
    """Document chat interface"""
    return render(request, 'blog/docchat.html')

@login_required
@csrf_exempt
def process_documents(request):
    """Handle PDF upload and processing with session support"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

    if not request.FILES.getlist('pdf_files'):
        return JsonResponse({'error': 'No files uploaded'}, status=400)

    try:
        # Create a unique session ID for this document set
        session_id = str(uuid.uuid4())
        os.makedirs(settings.FAISS_INDEX_DIR, exist_ok=True)

        all_text = ""
        documents = []
        
        for pdf_file in request.FILES.getlist('pdf_files'):
            # Validate file type
            if not pdf_file.name.endswith('.pdf'):
                return JsonResponse({'error': 'Only PDF files are allowed'}, status=400)
            
            # Validate file size (10MB max)
            if pdf_file.size > 10 * 1024 * 1024:
                return JsonResponse({'error': f'File {pdf_file.name} is too large (max 10MB)'}, status=400)
            
            # Save the document to database and disk
            document = Document(
                owner=request.user,
                file=pdf_file,
                session_id=session_id
            )
            document.save()
            documents.append(document)
            
            try:
                # Extract text from the saved file
                text = ""
                reader = PdfReader(document.file.path)
                for page in reader.pages:
                    text += page.extract_text() or ""
                
                if text.strip():
                    all_text += text + "\n\n"
                
            except Exception as e:
                logger.error(f"Error processing {pdf_file.name}: {str(e)}")
                document.delete()
                return JsonResponse({'error': f'Error processing {pdf_file.name}'}, status=500)

        if not all_text.strip():
            return JsonResponse({'error': 'No text could be extracted from the PDFs'}, status=400)

        # Create and save FAISS index with session ID
        text_chunks = get_text_chunks(all_text)
        index_path = os.path.join(settings.FAISS_INDEX_DIR, session_id)
        
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_API_KEY)
        vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)
        vector_store.save_local(index_path)

        # Mark documents as processed
        Document.objects.filter(session_id=session_id).update(processed=True)

        return JsonResponse({
            'status': 'success',
            'message': f'Processed {len(text_chunks)} text chunks',
            'chunk_count': len(text_chunks),
            'session_id': session_id
        })

    except Exception as e:
        logger.error(f"Error in process_documents: {str(e)}", exc_info=True)
        # Clean up any created documents
        Document.objects.filter(session_id=session_id).delete()
        return JsonResponse({'error': str(e)}, status=500)

# Update the ask_question view
@csrf_exempt
def ask_question(request):
    """Handle user questions with session support"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    question = request.POST.get('question', '').strip()
    session_id = request.POST.get('session_id', 'default')
    
    if not question:
        return JsonResponse({'error': 'No question provided'}, status=400)
    
    try:
        logger.info(f"Received question: {question} for session {session_id}")
        
        index_path = os.path.join(settings.FAISS_INDEX_DIR, session_id)
        if not os.path.exists(index_path):
            return JsonResponse({'error': 'No documents processed yet. Please upload documents first.'}, status=400)
        
        # Load embeddings and search
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_API_KEY)
        new_db = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
        
        # Perform similarity search
        docs = new_db.similarity_search(question, k=4)
        logger.info(f"Found {len(docs)} relevant document chunks")
        
        # Generate response
        chain = get_conversational_chain()
        response = chain(
            {"input_documents": docs, "question": question},
            return_only_outputs=True
        )
        
        answer = response['output_text']
        logger.info(f"Generated answer: {answer}")
        
        return JsonResponse({'answer': answer})
        
    except Exception as e:
        logger.error(f"Error answering question: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Error generating answer: {str(e)}'}, status=500)
# ----- Notes -----

def notes(request):
    """Notes tool main view"""
    return render(request, 'blog/notes.html')

@csrf_exempt
def save_note(request):
    """Handle saving notes"""
    if request.method == 'POST':
        # Placeholder for note saving functionality
        return JsonResponse({'status': 'success', 'message': 'Note saved successfully'})
    return JsonResponse({'error': 'Invalid request method'}, status=400)

# ----- Flashcards -----

def flashcards(request):
    """Flashcards tool main view"""
    return render(request, 'blog/flashcards.html')

@csrf_exempt
def generate_flashcards(request):
    """Handle flashcard generation"""
    if request.method == 'POST':
        # Placeholder for flashcard generation functionality
        return JsonResponse({'status': 'success', 'message': 'Flashcards generated successfully'})
    return JsonResponse({'error': 'Invalid request method'}, status=400)

# ==================== HELPER FUNCTIONS ====================

def get_pdf_text(pdf_paths):
    """Extract text from PDF files with error handling"""
    text = ""
    for pdf_path in pdf_paths:
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
        except Exception as e:
            logger.warning(f"Error reading {pdf_path}: {str(e)}")
            continue
    return text

def get_text_chunks(text):
    """Split text into manageable chunks with validation"""
    if not text.strip():
        raise ValueError("No text provided for chunking")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=10000,
        chunk_overlap=1000,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks

def get_vector_store(text_chunks):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_API_KEY)
    vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)
    index_path = os.path.join(settings.FAISS_INDEX_DIR, index_name)
    vector_store.save_local(index_path)
    return index_path
def load_vector_store(index_name="default"):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_API_KEY)
    index_path = os.path.join(settings.FAISS_INDEX_DIR, index_name)
    return FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)

def get_conversational_chain():
    """Create conversational chain with improved prompt"""
    prompt_template = """
    You are an AI assistant helping with educational content. Answer the question as detailed as possible from the provided context.
    Follow these rules:
    1. Be concise but thorough
    2. If the answer isn't in the context, say "I couldn't find the answer in the documents"
    3. Format your response clearly with bullet points or paragraphs when appropriate
    
    Context:\n{context}\n
    Question: {question}
    
    Answer:
    """
    
    model = ChatGoogleGenerativeAI(
        model="models/gemini-pro",  # Updated model name
        temperature=0.3,
        google_api_key=GOOGLE_API_KEY
    )
    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=['context', 'question']
    )
    chain = load_qa_chain(model, chain_type="stuff", prompt=prompt)
    return chain