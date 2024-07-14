import json
import re
from urllib.parse import urlparse, parse_qs, urlencode
from xml.dom.minidom import parseString
import requests

class YouTubeVideoExtractor:
    def __init__(self, video_url):
        self.video_url = video_url
        self.streams = {}

    def extract_video_streams(self):
        video_id = self.get_video_id(self.video_url)
        if not video_id:
            raise ValueError("Invalid YouTube video URL")

        video_info_url = f"https://www.youtube.com/get_video_info?video_id={video_id}"
        response = requests.get(video_info_url)
        if response.status_code != 200:
            raise ConnectionError(f"Failed to retrieve video info: {response.status_code}")

        video_info = parse_qs(response.text)
        if 'player_response' in video_info:
            player_response = json.loads(video_info['player_response'][0])
            if 'streamingData' in player_response:
                streaming_data = player_response['streamingData']
                if 'formats' in streaming_data:
                    self.parse_formats(streaming_data['formats'])
                if 'adaptiveFormats' in streaming_data:
                    self.parse_formats(streaming_data['adaptiveFormats'])

    def parse_formats(self, formats):
        for format_data in formats:
            itag = format_data.get('itag')
            if itag:
                self.streams[itag] = {
                    'itag': itag,
                    'url': format_data.get('url'),
                    'quality': format_data.get('quality'),
                    'type': format_data.get('mimeType').split(';')[0] if 'mimeType' in format_data else None,
                    'container': self.mime_to_container(format_data.get('mimeType').split(';')[0]) if 'mimeType' in format_data else None
                }

    def get_video_id(self, video_url):
        video_id = parse_qs(urlparse(video_url).query).get('v')
        return video_id[0] if video_id else None

    def mime_to_container(self, mime_type):
        if mime_type:
            if 'mp4' in mime_type:
                return 'mp4'
            elif 'webm' in mime_type:
                return 'webm'
            elif '3gp' in mime_type:
                return '3gp'
            elif 'flv' in mime_type:
                return 'flv'
        return None
