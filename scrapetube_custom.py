import json
import time
from typing import Generator
import requests
from typing_extensions import Literal
from bs4 import BeautifulSoup

results_type_map = {
    "video": ["B", "videoRenderer"],
    "channel": ["C", "channelRenderer"],
    "playlist": ["D", "playlistRenderer"],
    "movie": ["E", "videoRenderer"],
    "music": ["F", "musicVideoRenderer"],  # Adjusted for music videos
}

def get_search(
    query: str,
    limit: int = None,
    sleep: int = 1,
    sort_by: Literal["relevance", "upload_date", "view_count", "rating"] = "relevance",
    results_type: Literal["video", "channel", "playlist", "movie", "music"] = "video",
    proxies: dict = None,
) -> Generator[dict, None, None]:

    sort_by_map = {
        "relevance": "A",
        "upload_date": "I",
        "view_count": "M",
        "rating": "E",
    }

    param_string = f"CA{sort_by_map[sort_by]}SAhA{results_type_map[results_type][0]}"
    if results_type in ["playlist", "music"]:
        return get_playlist_or_music_search(query, limit, sleep, sort_by, proxies, results_type_map[results_type][1])
    else:
        url = f"https://www.youtube.com/results?search_query={query}&sp={param_string}"
        api_endpoint = "https://www.youtube.com/youtubei/v1/search"
        videos = get_videos(
            url, api_endpoint, results_type_map[results_type][1], limit, sleep, proxies
        )
        for video in videos:
            yield video


def get_playlist_or_music_search(query, limit, sleep, sort_by, proxies, selector):
    sort_by_map = {
        "relevance": "relevance",
        "upload_date": "upload_date",
        "view_count": "view_count",
        "rating": "rating",
    }

    url = f"https://www.youtube.com/results?search_query={query}&sp=EgIQAQ%253D%253D"  # Music filter
    response = requests.get(url, proxies=proxies)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        items = soup.find_all("ytd-video-renderer")
        for item in items[:limit]:
            video_data = {
                "videoId": item.find("a", class_="yt-simple-endpoint style-scope ytd-video-renderer")["href"].split("=", 1)[1],
                "title": item.find("yt-formatted-string", class_="style-scope ytd-video-renderer").text.strip(),
                "channel_name": item.find("yt-formatted-string", class_="style-scope ytd-channel-name complex-string").text.strip(),
                "published_time": item.find("yt-formatted-string", class_="style-scope ytd-video-renderer").text.strip(),
                "views": item.find("span", class_="style-scope ytd-video-meta-block").text.strip(),
                "thumbnail": item.find("img", class_="style-scope yt-img-shadow")["src"],
                "description": item.find("yt-formatted-string", class_="style-scope ytd-video-renderer").text.strip(),
            }
            yield video_data


def get_videos(
    url: str, api_endpoint: str, selector: str, limit: int, sleep: float, proxies: dict = None, sort_by: str = None
) -> Generator[dict, None, None]:
    session = get_session(proxies)
    is_first = True
    quit_it = False
    count = 0
    while True:
        if is_first:
            html = get_initial_data(session, url)
            client = json.loads(
                get_json_from_html(html, "INNERTUBE_CONTEXT", 2, '"}},') + '"}}'
            )["client"]
            api_key = get_json_from_html(html, "innertubeApiKey", 3)
            session.headers["X-YouTube-Client-Name"] = "1"
            session.headers["X-YouTube-Client-Version"] = client["clientVersion"]
            data = json.loads(
                get_json_from_html(html, "var ytInitialData = ", 0, "};") + "}"
            )
            next_data = get_next_data(data, sort_by)
            is_first = False
            if sort_by and sort_by != "relevance": 
                continue
        else:
            data = get_ajax_data(session, api_endpoint, api_key, next_data, client)
            next_data = get_next_data(data)
        for result in get_videos_items(data, selector):
            try:
                count += 1
                yield result
                if count == limit:
                    quit_it = True
                    break
            except GeneratorExit:
                quit_it = True
                break

        if not next_data or quit_it:
            break

        time.sleep(sleep)

    session.close()


def get_session(proxies: dict = None) -> requests.Session:
    session = requests.Session()
    if proxies:
        session.proxies.update(proxies)
    session.headers[
        "User-Agent"
    ] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    session.headers["Accept-Language"] = "en"
    return session

def get_initial_data(session: requests.Session, url: str) -> str:
    session.cookies.set("CONSENT", "YES+cb", domain=".youtube.com")
    response = session.get(url, params={"ucbcb":1})

    html = response.text
    return html


def get_ajax_data(
    session: requests.Session,
    api_endpoint: str,
    api_key: str,
    next_data: dict,
    client: dict,
) -> dict:
    data = {
        "context": {"clickTracking": next_data["click_params"], "client": client},
        "continuation": next_data["token"],
    }
    response = session.post(api_endpoint, params={"key": api_key}, json=data)
    return response.json()


def get_json_from_html(html: str, key: str, num_chars: int = 2, stop: str = '"') -> str:
    pos_begin = html.find(key) + len(key) + num_chars
    pos_end = html.find(stop, pos_begin)
    return html[pos_begin:pos_end]


def get_next_data(data: dict, sort_by: str = None) -> dict:
    sort_by_map = {
        "relevance": 0, 
        "upload_date": 1,
        "view_count": 2, 
        "rating": 3
    }
    if sort_by and sort_by != "relevance":
        endpoint = next(
            search_dict(data, "feedFilterChipBarRenderer"), None)["contents"][sort_by_map[sort_by]]["chipCloudChipRenderer"]["navigationEndpoint"]
    else:
        endpoint = next(search_dict(data, "continuationEndpoint"), None)
    if not endpoint:
        return None
    next_data = {
        "token": endpoint["continuationCommand"]["token"],
        "click_params": {"clickTrackingParams": endpoint["clickTrackingParams"]},
    }

    return next_data


def search_dict(partial: dict, search_key: str) -> Generator[dict, None, None]:
    stack = [partial]
    while stack:
        current_item = stack.pop(0)
        if isinstance(current_item, dict):
            for key, value in current_item.items():
                if key == search_key:
                    yield value
                else:
                    stack.append(value)
        elif isinstance(current_item, list):
            for value in current_item:
                stack.append(value)


def get_videos_items(data: dict, selector: str) -> Generator[dict, None, None]:
    return search_dict(data, selector)
