from flask import Flask, request, jsonify
from youtubesearchpython import *
import os
import sys
import json
from urllib.parse import parse_qs
import scrapetube_custom as scrapetube
import requests
from bs4 import BeautifulSoup
import yt_dlp
from urllib.parse import urlparse, parse_qs
import threading

app = Flask(__name__)
EXPECTED_TOKEN = "asdasplodd34234sdfas32"

# Traducción de las palabras en español y portugués
TRANSLATIONS = {
    "ago": {"es": "hace", "pt": "atrás"},
    "views": {"es": "de visualizaciones", "pt": "de visualizações"},
    "years": {"es": "años", "pt": "anos"},
    "year": {"es": "año", "pt": "ano"},
    "months": {"es": "meses", "pt": "meses"},
    "month": {"es": "mes", "pt": "mês"},
    "weeks": {"es": "semanas", "pt": "semanas"},
    "week": {"es": "semana", "pt": "semana"},
    "days": {"es": "días", "pt": "dias"},
    "day": {"es": "día", "pt": "dia"},
    "hours": {"es": "horas", "pt": "horas"},
    "hour": {"es": "hora", "pt": "hora"},
    "minutes": {"es": "minutos", "pt": "minutos"},
    "minute": {"es": "minuto", "pt": "minuto"},
    "seconds": {"es": "segundos", "pt": "segundos"},
    "second": {"es": "segundo", "pt": "segundo"}
}

def translate_time(time, language):
    if language in ["es", "pt"]:
        for word in TRANSLATIONS:
            if word in time:
                translated_word = TRANSLATIONS[word].get(language, word)
                time = time.replace(word, translated_word)
        
        # Verificar si el tiempo contiene "ago" y realizar la traducción adecuada
        if "hace" in time:
            time_split = time.split()
            if len(time_split) == 3:  # Solo "1 year ago"
                return f'{TRANSLATIONS["ago"][language]} {time_split[0]} {time_split[1]}'
            else:  # "hace 1 año ago"
                return f'{TRANSLATIONS["ago"][language]} {time_split[-4]} {time_split[-3]} {time_split[-2]} {time_split[-1]}'
        
    return time

def extract_video_info(video, language):
    video_id = video.get('videoId', '')
    title = video.get('title', {}).get('runs', [{}])[0].get('text', '')
    channel_name = video.get('longBylineText', {}).get('runs', [{}])[0].get('text', '')
    published_time = video.get('publishedTimeText', {}).get('simpleText', '')
    # Traducir la fecha de publicación al idioma especificado
    if language in ["es", "pt"]:
        published_time = translate_time(published_time, language)
    duration = video.get('lengthText', {}).get('simpleText', '')
    thumbnails = video.get('thumbnail', {}).get('thumbnails', [])
    best_thumbnail = max(thumbnails, key=lambda t: t.get('width', 0) * t.get('height', 0))
    best_thumbnail_url = best_thumbnail.get('url', '') if best_thumbnail else ''
    views = video.get('shortViewCountText', {}).get('simpleText', '')
    # Traducir "views" al idioma especificado
    if language in ["es", "pt"]:
        views = translate_time(views, language)
    description = ''
    if 'detailedMetadataSnippets' in video and video['detailedMetadataSnippets']:
        description_runs = video['detailedMetadataSnippets'][0].get('snippetText', {}).get('runs', [])
        if len(description_runs) > 1:
            description = description_runs[1].get('text', '')
    preview_moving_url = video.get('richThumbnail', {}).get('movingThumbnailRenderer', {}).get('movingThumbnailDetails', {}).get('thumbnails', [{}])[0].get('url', '')
    channel_thumbnail_url = video.get('channelThumbnailSupportedRenderers', {}).get('channelThumbnailWithLinkRenderer', {}).get('thumbnail', {}).get('thumbnails', [{}])[0].get('url', '')
    return {
        'videoId': video_id,
        'title': title,
        'channel_name': channel_name,
        'published_time': published_time,
        'duration': duration,
        'views': views,
        'thumbnail': best_thumbnail_url,
        'description': description,
        'preview_moving': preview_moving_url,
        'channel_thumbnail': channel_thumbnail_url
    }

def is_live(video):
    badges = video.get('badges', [])
    for badge in badges:
        if 'metadataBadgeRenderer' in badge and 'style' in badge['metadataBadgeRenderer']:
            if badge['metadataBadgeRenderer']['style'] == 'BADGE_STYLE_TYPE_LIVE_NOW':
                return True
    return False

def search_videos(query, limite, language,search_type):
    # Obtener la lista de videos
    videos = []
    if "playlist" in search_type:
        videos = scrapetube.get_playlist(query)
    else:
        videos = scrapetube.get_search(query, limit=limite, sort_by="relevance", results_type=search_type)
    # Convertir la lista de videos a formato JSON
    response_data = {"data": [], "state": "Error"}
    if videos:
        try:
            # Filtrar los videos en vivo
            if "playlist" in search_type:
                response_data = videos
            else:
                filtered_videos = [video for video in videos if not is_live(video)]
                # Extraer la información de los videos y reducirla
                reduced_data = [extract_video_info(video, language) for video in filtered_videos]
                response_data = {"data": reduced_data, "state": "OK"}
                
        except Exception as e:
            print(f"Error processing videos: {e}")
    return response_data

import re

def get_autocomplete_suggestions(query):
    url = f"https://suggestqueries.google.com/complete/search?client=youtube&q={query}"
    response = requests.get(url)
    if response.status_code == 200:
        # Obtener el contenido del archivo descargado
        content = response.text
        match = re.search(r'\[.+\]', content)
        if match:
            # Extraer el contenido JSON de las sugerencias
            json_data = match.group()
            try:
                # Decodificar el JSON y obtener las sugerencias
                suggestions = json.loads(json_data)[1]
                # Extraer solo los términos de búsqueda sugeridos
                suggested_terms = [suggestion[0] for suggestion in suggestions[:10]]
                response_data = {"suggested": suggested_terms, "state": "OK"}
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                response_data = {"suggested": [], "state": "Error"}
        else:
            response_data = {"suggested": [], "state": "Error"}
    else:
        response_data = {"suggested": [], "state": f"Error"}
    
    return response_data

class Video:
    def __init__(self, video_id, title, channel_name, published_time, duration, views, thumbnail, description, preview_moving, channel_thumbnail):
        self.videoId = video_id
        self.title = title
        self.channel_name = channel_name
        self.published_time = published_time
        self.duration = duration
        self.views = views
        self.thumbnail = thumbnail
        self.description = description
        self.preview_moving = preview_moving
        self.channel_thumbnail = channel_thumbnail
        
@app.route('/')
def index():
    return '¡Hola, Render!'
    
@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('txt_query')
    search_type = request.args.get('type', 'videos')  # Tipo de búsqueda: all, videos, channels, playlists, custom
    limit = int(request.args.get('limit', 10))
    language = request.args.get('language', 'en')
    region = request.args.get('region', 'US')
    page = int(request.args.get('page', 1))
    sort_order = request.args.get('sort_order', None)  # Para búsquedas personalizadas

    if not query:
        return jsonify({'error': 'Parámetro de consulta "query" requerido'}), 400

    try:
        if query:
            # Realizar la búsqueda de videos y devolver los resultados
            response = search_videos(query, limit, language,search_type)
            return jsonify(response)
        else:
            # Si no se proporciona un parámetro válido, devolver un mensaje de error
            return jsonify({'error': 'Please provide a valid text parameter.'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/playlist', methods=['GET'])
def get_playlist():
    playlist_url = request.args.get('url')

    if not playlist_url:
        return jsonify({'error': 'Parámetro de consulta "url" requerido'}), 400

    try:
        playlist = Playlist.get(playlist_url, mode=ResultMode.dict)  # Obtener los resultados como un diccionario
        return jsonify(playlist)  # Convertir el diccionario en JSON utilizando jsonify

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/video', methods=['GET'])
def get_video():
    video_url = request.args.get('url')

    if not video_url:
        return jsonify({'error': 'Parámetro de consulta "url" requerido'}), 400

    try:
        fetcher = StreamURLFetcher()
        video = Video.getInfo('https://youtu.be/'+video_url, mode = ResultMode.json)
        url = fetcher.get(video, 251)
        return jsonify({'url': url})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
