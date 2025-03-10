from PIL import Image
import time, os, re
from hashlib import md5
from threading import Thread, Lock

import config, backend

global_lock = Lock()
global_running_flag = True
download_jobs = []
current_url = ""

config.fs_bases["x"] = os.path.expanduser(config.fs_bases["x"])
config.fs_bases["bsky"] = os.path.expanduser(config.fs_bases["bsky"])
config.url_base = config.url_base.strip("/")
if config.url_base:
    config.url_base = "/" + config.url_base


def create_image_thumbnail(image_path, thumbnail_path, thumbnail_size):
    image = Image.open(image_path)
    image.thumbnail((thumbnail_size, thumbnail_size))
    image.convert("RGB").save(thumbnail_path)


def create_video_thumbnail(video_path, thumbnail_path):
    cmd = f"ffmpeg -i {video_path} -ss 00:00:00.100 -vframes 1 {thumbnail_path}"
    os.system(cmd)


def create_thumbnail(path, thumbnail_size=config.thubnail_size):
    config.cache_path = os.path.expanduser(config.cache_path)
    if not os.path.exists(config.cache_path):
        os.makedirs(config.cache_path)
    thumbnail_path = md5(path.encode()).hexdigest() + f"_{thumbnail_size}.jpg"
    thumbnail_path = os.path.join(config.cache_path, thumbnail_path)
    if os.path.exists(thumbnail_path):
        print("Thumbnail exists:", thumbnail_path)
        return thumbnail_path
    print("Creating thumbnail:", thumbnail_path)
    if path.endswith(".mp4") or path.endswith(".webm"):
        create_video_thumbnail(path, thumbnail_path)
    else:
        create_image_thumbnail(path, thumbnail_path, thumbnail_size)
    return thumbnail_path


class DownloadWorker(Thread):
    def __init__(self, db):
        super().__init__()
        self.db = db

    def run(self):
        global download_jobs, global_lock, global_running_flag, current_url
        while global_running_flag:
            with global_lock:
                if len(download_jobs) > 0:
                    current_url = download_jobs.pop()
                    print(f"Downloading {current_url}")
                else:
                    time.sleep(1)
                    continue
            name = current_url.split("/")[-1].lower()
            if "bsky" in current_url:
                # cookies not avalible yet
                cmd = f"gallery-dl -c gallery-dl-config.json {current_url} -D \"{config.fs_bases['bsky']}/{name}/\""
                type = "bsky"
            else:
                if config.cookies_list['x']:
                    cmd = f"gallery-dl -c gallery-dl-config.json -C {config.cookies_list['x']} {current_url} -D \"{config.fs_bases['x']}/{name}/\""
                else:
                    cmd = f"gallery-dl -c gallery-dl-config.json {current_url} -D \"{config.fs_bases['x']}/{name}/\""
                type = "x"
            os.system(cmd)
            try:
                backend.scan_for_users(type, self.db, name)
                backend.scan_for_posts(type, self.db, name)
                backend.scan_for_media(type, self.db, name)
                self.db.conn.commit()
                backend.build_cache_all_posts_id(self.db)
                print(name, "downloaded")
            except Exception as e:
                print(e)
                print("Failed. Cookies required?")
            current_url = ""


mention_pattern = re.compile(r"(^|[^/])@([\w\-_\.]+)")
hashtag_pattern = re.compile(r"(^|[^/])#([^ ,#\!]+)")
url_pattern = re.compile(r"https?://\S+")

def embed_hyperlink(type, text_content):
    urls = url_pattern.findall(text_content)
    for url in urls:
        https_url = url.replace("http://", "https://")
        if https_url.endswith('.'):
            https_url = https_url[:-1]
        url_display_text = https_url.replace("https://", "")
        if len(url_display_text) > 30:
            url_display_text = url_display_text[:30] + "..."
        text_content = text_content.replace(
            url,
            f"<a class='hyperlink' href='{https_url}' target=\"_blank\">{url_display_text}</a>",
        )
    if type == "x":
        user_url = "https://x.com/{user}"
        hastag_url = "https://x.com/hashtag/{tag}"
    else:
        user_url = "https://bsky.app/profile/{user}"
        hastag_url = "https://bsky.app/hashtag/{tag}"
    mentions = [i[1] for i in mention_pattern.findall(text_content)]
    mentions = list(set(mentions))
    hashtags = [i[1] for i in hashtag_pattern.findall(text_content)]
    hashtags = list(set(hashtags))
    for mention in mentions:
        if mention.endswith("."):
            mention = mention[:-1]
        text_content = text_content.replace(
            f"@{mention}",
            f"<a class='hyperlink' href='{user_url.format(user=mention)}' target=\"_blank\">@{mention}</a>",
        )
    for hashtag in hashtags:
        text_content = text_content.replace(
            f"#{hashtag}",
            f"<a class='hyperlink' href='{hastag_url.format(tag=hashtag)}' target=\"_blank\">#{hashtag}</a>",
        )
    return text_content

def list_and(list1, list2):
    # Convert both lists to sets for efficient intersection
    set1 = set(list1)
    set2 = set(list2)
    
    # Find the intersection of the two sets
    intersection = set1.intersection(set2)
    
    # Convert the intersection back to a list and return it
    return list(intersection)