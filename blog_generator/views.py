from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from pytubefix import YouTube
from dotenv import load_dotenv
from django.conf import settings
from openai import OpenAI
import google.generativeai as genai
from .models import BlogPost
import assemblyai
import json
import os
import requests
import logging

load_dotenv()

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')
openai_logger = logging.getLogger('openai')
openai_logger.setLevel(logging.DEBUG)
# Create your views here.


@login_required
def index(request):
    return (render(request, 'index.html'))


def yt_title(link):
    yt = YouTube(link)
    return (yt.title)


def download_audio(link):
    yt = YouTube(link)
    outfile = yt.streams.filter(only_audio=True).first().download(
        output_path=settings.MEDIA_ROOT)
    base, ext = os.path.splitext(outfile)
    newfile = base + '.mp3'
    os.rename(outfile, newfile)
    return (newfile)


def get_transcript(link):
    # audio_file
    audio_file = download_audio(link)
    assemblyai.settings.api_key = os.getenv('ASSEMBLYAI_API_KEY')

    transcriber = assemblyai.Transcriber()
    transcript = transcriber.transcribe(audio_file)
    os.remove(audio_file)

    return (transcript.text)


def generate_blog_from_transcript(transcript):
    if os.getenv('OPENAI_API_KEY') and os.getenv('GEMINI_API_KEY'):
        raise Exception("Both OpenAI and Gemini API Keys are set. Please use only one API Key")


    elif os.getenv('OPENAI_API_KEY'):
        client = OpenAI(
            base_url="https://zukijourney.xyzbot.net/v1",
            api_key=os.getenv('OPENAI_API_KEY'),
        )
        prompt = f"You are a highly skilled writer who has been tasked with writing a blog post based on the following transcript from a YouTube video. Write the blog post in a way that is engaging and informative. Make it look like a professional blog post. Don't disclose that you were fed a transcript. assume that you watched the video. The title of the blog is going to be the title of the video itself. So, Don't give the title of the article.  \n\n{
            transcript} \n\nArticle:"

        response = client.chat.completions.create(
            model="gpt-3.5-turbo-instruct",
            messages=[
                {"role": "user", "content": f"{prompt}"},
            ],
        )
        generated_content = response.choices[0].message.content.strip()
        return (generated_content)
    elif os.getenv('GEMINI_API_KEY'):
        prompt = f"You are a highly skilled writer who has been tasked with writing a blog post based on the following transcript from a YouTube video. Write the blog post in a way that is engaging and informative. Make it look like a professional blog post. Don't disclose that you were fed a transcript. assume that you watched the video. The title of the blog is going to be the title of the video itself. So, Don't give the title of the article.  \n\n{
            transcript}"
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        grenerated_content = response.text
        return (grenerated_content)




@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return (JsonResponse({'error': 'Invalid Data Sent'}, status=400))
    else:
        return(JsonResponse({'error': 'Invalid Request'}, status=405))
    
    # TODO: Get The Title Of The Video
    youtube_title = yt_title(yt_link)

    transcript = get_transcript(yt_link)
    if not transcript:
        return (JsonResponse({'error': 'Failed To Generate Transcript'}, status=500))

    # TODO: Generate the Blog Using OpenAI's Model 
    blog_content = generate_blog_from_transcript(transcript)
    if not blog_content:
        return(JsonResponse({'error': 'Failed To Generate Blog Article'}, status=500))
  
    # TODO: Save the Blog to the Database
    new_blog_article = BlogPost.objects.create(
        user=request.user,
        youtube_title=youtube_title,
        youtube_link=yt_link,
        generated_content=blog_content,
    )
    new_blog_article.save()

    # TODO: Return the Blog to the User as a Response
    return(JsonResponse({'title': youtube_title, 'content': blog_content}))


        

def user_login(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return (redirect('/'))
        else:
            error_message = 'Invalid Username or Password'
            return (render(request, 'login.html', {'error_message': error_message}))

    return (render(request, 'login.html'))


def user_register(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return (redirect('/'))
            except:
                error_message = 'Username or Email already exists'
                return (render(request, 'register.html', {'error_message': error_message}))
        else:
            error_message = 'Passwords do not match'
            return (render(request, 'register.html', {'error_message': error_message}))

    return (render(request, 'register.html'))


def user_logout(request):
    logout(request)
    return (redirect('/'))


@login_required
def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return (render(request, "all-blogs.html", {'blog_articles': blog_articles}))


def blog_details(request, pk):
    blog_article_details = BlogPost.objects.get(id=pk)
    if request.user == blog_article_details.user:
        return (render(request, "blog-details.html", {'blog_article_details': blog_article_details}))
    else:
        return redirect("/")
