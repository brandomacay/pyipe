from flask import Flask, request, jsonify
from youtubesearchpython import *

app = Flask(__name__)

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
        search_results = None

        if search_type == 'all':
            search = Search(query, limit=limit, language=language, region=region)
        elif search_type == 'videos':
            search = VideosSearch(query, limit=limit, language=language, region=region)
        elif search_type == 'channels':
            search = ChannelsSearch(query, limit=limit, language=language, region=region)
        elif search_type == 'playlists':
            search = PlaylistsSearch(query, limit=limit, language=language, region=region)
        elif search_type == 'custom' and sort_order:
            search = CustomSearch(query, VideoSortOrder[sort_order], language=language, region=region)
        else:
            return jsonify({'error': 'Tipo de búsqueda "type" no válido o falta "sort_order" para búsqueda personalizada'}), 400

        for _ in range(page - 1):
            search.next()

        search_results = search.result(mode=ResultMode.dict)  # Obtener los resultados como un diccionario

        # Filtrar videos en vivo, aquellos con duración nula y publicados con fecha nula
        filtered_results = []
        for result in search_results['result']:
            if ('liveBroadcastContent' not in result or result['liveBroadcastContent'] != 'live') and \
                    'duration' in result and result['duration'] is not None and \
                    'publishedTime' in result and result['publishedTime'] is not None:
                
                # Convertir la duración a milisegundos
                duration_parts = result['duration'].split(':')
                minutes = int(duration_parts[0])
                seconds = int(duration_parts[1])
                duration_ms = (minutes * 60 + seconds) * 1000

                # Construir el objeto Video filtrado
                video = Video(
                    video_id=result['id'],
                    title=result['title'],
                    channel_name=result['channel']['name'],
                    published_time=result['publishedTime'],
                    duration=duration_ms,
                    views=result['viewCount']['text'],
                    thumbnail=result['thumbnails'][0]['url'] if 'thumbnails' in result else None,
                    description=' '.join([snippet['text'] for snippet in result.get('descriptionSnippet', [])]),
                    preview_moving=result['thumbnails'][0]['url'] if 'thumbnails' in result else None,
                    channel_thumbnail=result['channel']['thumbnails'][0]['url'] if 'thumbnails' in result['channel'] else None
                )

                filtered_results.append(video.__dict__)

        return jsonify({'data': filtered_results})

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
        video = Video(video_url, componentMode='getFormats', resultMode=1, timeout=20, enableHTML=False)
        video.sync_create()  # Ejecutar la solicitud de forma síncrona

        # Obtener el componente de video que incluye la información de formatos
        video_info = video.__result(1)

        return jsonify(video_info)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
