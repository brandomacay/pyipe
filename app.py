from flask import Flask, send_file, request, jsonify
from youtubesearchpython import *
import os
import sys
import json
import scrapetube
import video_extractor as YouTubeVideoExtractor
import requests
from bs4 import BeautifulSoup
import yt_dlp
from urllib.parse import urlparse, parse_qs
import threading
import logging
import re
import subprocess  # Añade esta línea para importar subprocess
import datetime  # Añade esta línea para importar datetime

app = Flask(__name__)
EXPECTED_TOKEN = "asdasplodd34234sdfas32"
logging.basicConfig(level=logging.DEBUG)  # Establece el nivel de registro a DEBUG

# Agrega un manejador de registro para enviar registros a la consola
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
app.logger.addHandler(handler)

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
    if not channel_name:
        channel_name = video.get('shortBylineText', {}).get('runs', [{}])[0].get('text', '')
        
    published_time = video.get('publishedTimeText', {}).get('simpleText', '')
    # Traducir la fecha de publicación al idioma especificado
    if language in ["es", "pt"]:
        published_time = translate_time(published_time, language)
        
    duration = video.get('lengthText', {}).get('simpleText', '')
    thumbnails = video.get('thumbnail', {}).get('thumbnails', [])
    best_thumbnail = max(thumbnails, key=lambda t: t.get('width', 0) * t.get('height', 0), default={})
    best_thumbnail_url = best_thumbnail.get('url', '') if best_thumbnail else ''
    views = video.get('shortViewCountText', {}).get('simpleText', '')
    if not views:
        views = video.get('videoInfo', {}).get('runs', [{}])[0].get('text', '')
    if not published_time:
        published_time = video.get('videoInfo', {}).get('runs', [{}])[2].get('text', '')
        
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

def search_videos(query, limite, language, search_type):
    command = [
            "yt-dlp",
            "ytsearch{}:{}".format(limite, query),
            "--dump-json", 
            "--default-search", "ytsearch",
            "--no-playlist", "--no-check-certificate", "--geo-bypass",
            "--flat-playlist", "--skip-download", "--quiet", "--ignore-errors"
    ]
    
    try:
        # Get the output and analyze it
        output = subprocess.check_output(command).decode('utf-8')
        videos = [json.loads(line) for line in output.splitlines()]
        # Simplify the results for displaying to the user
        simplified_results = []
        for video in videos:
            duration_seconds = video.get("duration")
            if duration_seconds is not None:
                duration_str = str(datetime.timedelta(seconds=duration_seconds))
            else:
                duration_str = "N/A"

            simplified_results.append({
                "title": video.get("title", "N/A"),
                "url": video.get("webpage_url", "N/A"),
                "origin_url": video.get("original_url", "N/A"),
                "duration": duration_str,
                "uploader": video.get("uploader", "N/A")
            })

        return json.dumps(simplified_results)  # Convertir la lista de diccionarios a JSON

    except subprocess.CalledProcessError:
        return json.dumps([])
    
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
        response_data = {"suggested": [], "state": "Error"}

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
    search_type = request.args.get('type', 'videos')
    limit = int(request.args.get('limit', 10))
    language = request.args.get('language', 'en')
    region = request.args.get('region', 'US')
    page = int(request.args.get('page', 1))
    sort_order = request.args.get('sort_order', None)

    if not query:
        return jsonify({'error': 'Parámetro de consulta "query" requerido'}), 400

    try:
        if query:
            # Realizar la búsqueda de videos y devolver los resultados
            response = search_videos(query, limit, language, search_type)
            response_data = json.loads(response)
            print("debug result:", response_data)
            return jsonify(response_data)
        else:
            return jsonify({'error': 'Please provide a valid text parameter.'})
    except Exception as e:
        app.logger.error(f"Error processing videos: {e}")  # Registra el error con el logger de Flask     
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

def is_url_accessible(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    response = requests.head(url, headers=headers)
    return response.status_code == 200

@app.route('/video', methods=['GET'])
def get_streams():
    video_id = request.args.get('video_id')
    if not video_id:
        return jsonify({'error': 'Parámetro de consulta "video_id" requerido'}), 400

    URL = f'https://www.youtube.com/watch?v={video_id}'
    ydl_opts = {
        'quiet': True,
        'format': 'bestvideo+bestaudio/best',  # Obtener todos los formatos disponibles
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False)
            formats = info.get('formats', [])

            # Filtrar y mapear la información de los formatos
            streams = []
            for f in formats:
                if 'height' in f:
                    quality_label = f'{f["height"]}p'
                else:
                    quality_label = f['format_note']
                stream = {
                    'url': f['url'],
                    'quality': quality_label,
                    'format': f['format_id'],
                    'ext': f['ext'],
                    'filesize': f.get('filesize'),
                    'height': f.get('height', 0) or 0  # Asegurarse de que height sea un número
                }
                streams.append(stream)

            # Selección de calidades de video
            qualities = [
                {'min': 240, 'max': 460},
                {'min': 720, 'max': 1080},
            ]
            selected_streams = []
            for quality in qualities:
                for stream in streams:
                    if quality['min'] <= stream['height'] <= quality.get('max', float('inf')):
                        selected_streams.append(stream)
                        break

            if not selected_streams:
                return jsonify({'error': 'No se encontraron calidades de video adecuadas'}), 404

            # Función generadora para transmitir el video
            def generate_video_stream(url):
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                }
                response = requests.get(url, headers=headers, stream=True)
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        yield chunk

            # Transmitir el primer video
            stream_1 = generate_video_stream(selected_streams[0]['url'])
            return Response(stream_1, content_type='video/mp4', headers={
                'Content-Disposition': f'attachment; filename={video_id}_low.mp4'
            })

    except Exception as e:
        return jsonify({'error': f'Error al procesar el video: {str(e)}'}), 500
        
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
