import os
import re
import json
import time
import config
import requests
from threading import Lock, Thread

from PIL import Image

dl_lock = Lock()
dl_Q = []
current = ""


def put(url, file_path):
    if config.proxy:
        proxies = {
            "http": config.proxy,
            "https": config.proxy
        }
        resp = requests.get(url, proxies=proxies)
    else:
        resp = requests.get(url)
    bin_ = resp.content
    with open(file_path, "wb") as f:
        f.write(bin_)


def is_img(p):
    for i in [".jpg", ".png", ".gif"]:
        if p.endswith(i):
            return True
    return False


def is_vid(p):
    for i in [".mkv", ".mp4"]:
        if p.endswith(i):
            return True
    return False


def thumbnails(p, size=0):
    print(size, "x", size)
    if size == 0:
        size = config.thumbnail_big_size
    if not os.path.exists("cache"):
        os.mkdir("cache")
    fn = os.path.split(p)[-1]
    thumbnail_full_path = os.path.join("cache", "{}_{}.jpg".format(fn, size))
    thumbnail_vid_full_path = os.path.join("cache", "{}_v.jpg".format(fn))
    # Serve existing thumbnail
    if os.path.exists(thumbnail_full_path):
        print("Serving", p, "from cache.")
        return thumbnail_full_path
    if os.path.exists(thumbnail_vid_full_path):
        print("Serving", p, "from cache.")
        return thumbnail_vid_full_path
    # Create thumbnail
    if is_img(p):
        # For image
        print("Creating thumbnail", p)
        image = Image.open(p)
        image = image.convert("RGB")
        scale = max(image.size) / size
        new_size = (int(image.size[0] / scale), int(image.size[1] / scale))
        image.thumbnail(new_size)
        image.save(thumbnail_full_path)
        return thumbnail_full_path
    else:
        # For video
        cmd = 'ffmpeg -i "{}" -ss 00:00:05.000 -vframes 1 -vf scale=640:-1 "{}"'.format(
            p, thumbnail_vid_full_path
        )
        print(cmd)
        os.system(cmd)
        if not os.path.exists(thumbnail_vid_full_path):
            print("Failed at 5s, now try at 0s.")
            cmd = 'ffmpeg -i "{}" -ss 00:00:00.000 -vframes 1 -vf scale=640:-1 "{}"'.format(
                p, thumbnail_vid_full_path
            )
            print(cmd)
            os.system(cmd)
        return thumbnail_vid_full_path


def scan_posts(name, meta):
    if name in meta['posts']:
        posts = meta['posts'][name]
    else:
        posts = dict()
    user_fs_base = os.path.join(config.fs_base, name)
    isolated = 0
    for i in os.listdir(user_fs_base):
        if is_img(i) or is_vid(i):
            full_img_path = os.path.join(user_fs_base, i)
            if full_img_path in meta["loaded"]:
                continue
            if os.path.exists(full_img_path + ".json"):
                json_d = json.load(
                    open(full_img_path + ".json", "r", encoding="utf-8"))
                twt_id = str(json_d["tweet_id"])
                if not twt_id in posts:
                    posts[twt_id] = {
                        "imgs": [],
                        "vids": [],
                        "text": "",
                        "fav": 0,
                        "reply": 0,
                        "ret": 0,
                        "date": "",
                        "name": name,
                        "nick": name,
                    }
                try:
                    posts[twt_id]["name"] = json_d["author"]["name"]
                    posts[twt_id]["nick"] = json_d["author"]["nick"]
                    posts[twt_id]["text"] = hyper_link(json_d["content"])
                    posts[twt_id]["date"] = json_d["date"]
                    posts[twt_id]["fav"] = int(json_d["favorite_count"])
                    posts[twt_id]["reply"] = int(json_d["reply_count"])
                    posts[twt_id]["ret"] = int(json_d["retweet_count"])
                except:
                    print('-'*10, '\n', name, "paseing error.")
                    print(twt_id)
                    print(full_img_path + ".json")

                    raise
                if is_img(i):
                    if not i in posts[twt_id]["imgs"]:
                        posts[twt_id]["imgs"].append(i)
                else:
                    if not i in posts[twt_id]["vids"]:
                        posts[twt_id]["vids"].append(i)
                meta["tl"][twt_id] = posts[twt_id]
            else:
                posts[isolated] = {
                    "imgs": [],
                    "vids": [],
                    "text": "n/a",
                    "fav": 0,
                    "reply": 0,
                    "ret": 0,
                    "date": "",
                    "name": i,
                    "nick": i,
                }
                if is_img(i):
                    if not i in posts[isolated]["imgs"]:
                        posts[isolated]["imgs"].append(i)
                else:
                    if not i in posts[isolated]["vids"]:
                        posts[isolated]["vids"].append(i)
                isolated += 1
                meta["tl"][isolated] = posts[isolated]
            meta["loaded"].add(full_img_path)
    meta['posts'][name] = posts
    return posts

# def gallery_dl(url):
#     global dl_lock
#     if not dl_lock.acquire(blocking=False):
#         return False
#     Thread(target=dl_worker,args=[url]).start()
#     return True


def dl_worker():
    global dl_lock, current, dl_Q
    while True:
        if len(dl_Q) > 0:
            url = dl_Q.pop(0)
            name = os.path.split(url)[-1]
            current = url
            cmd = "gallery-dl {0} -C ./twitter.com_cookies.txt --write-metadata -D {1}".format(
                url, os.path.join(config.fs_base, name))
            if config.proxy:
                cmd += " --proxy '{0}'".format(config.proxy)
            print(cmd)
            os.system(cmd)
            # dl_lock.release()
            print(name, "finished.")
            current = ""
        time.sleep(1)


patt_at = re.compile("(\@\w+)")
patt_link = re.compile("(https{0,1}\:\/\/[^\s]+)")


def hyper_link(ostr):
    s = ostr
    ats = patt_at.findall(ostr)
    for a in set(ats):
        segment = '<a href="https://twitter.com/{0}" class="at" target="_blank">{1}<span class="hyper" style="border: 1px solid rgb(29, 155, 240);color: rgb(29, 155, 240);border-radius: 3px;">↗️</span></a>'.format(
            a[1:].replace("/", ""), a)
        s = s.replace(a, segment)
    links = patt_link.findall(ostr)
    for l in set(links):
        segment = '<a href="{0}" class="at" target="_blank">{0}<span class="hyper" style="border: 1px solid rgb(29, 155, 240);color: rgb(29, 155, 240);border-radius: 3px;">↗️</span></a>'.format(
            l)
        s = s.replace(l, segment)
    return s


Thread(target=dl_worker, daemon=True).start()
