#!/usr/bin/python3

from flask import (
    Flask,
    render_template,
    render_template_string,
    send_file,
    redirect,
    request,
    send_from_directory,
    Response,
    jsonify,
)
import os
import re
import natsort
from urllib.parse import unquote, quote
import posixpath
from math import ceil, floor
from random import sample, randint
from threading import Thread
import argparse
import requests
import signal
import sys

import config, backend, utils

parser = argparse.ArgumentParser(description="Check for command-line options.")

parser.add_argument(
    "--debug", action="store_true", help="Include this option to enable 'debug'."
)

parser.add_argument("--skip-scan", action="store_true", help="Skip startup scan.")

args, unknown = parser.parse_known_args()
args.debug = bool(args.debug)
args.skip_scan = bool(args.skip_scan)

# temporarily enable debug mode
# args.debug = True

app = Flask(__name__)


def set_cache_header(response):
    if not args.debug:
        response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.route(posixpath.join("/", config.url_base, "mt.webmanifest"))
def _webmanifest():
    with open("mt.webmanifest", "r") as f:
        return render_template_string(f.read(), url_base=config.url_base)


@app.route(posixpath.join("/", config.url_base, "js", "<fn>"))
def _js(fn):
    return set_cache_header(send_from_directory("js", fn))


@app.route(posixpath.join("/", config.url_base, "css", "<fn>"))
def _css(fn):
    print(posixpath.join("/", config.url_base, "css", fn))
    return set_cache_header(send_from_directory("css", fn))


@app.route(posixpath.join("/", config.url_base, "img", "<fn>"))
def _img(fn):
    return set_cache_header(send_from_directory("img", fn))


@app.route(posixpath.join("/", config.url_base, "avatar", "<type>", "<name>"))
def _avatar(type, name):
    # print(type, name)
    fn = f"{config.fs_bases[type]}/{name}/avatar"
    if not os.path.exists(fn):
        user = backend.User(name, type)
        user.load_from_db(db)
        avatar_url = user.avatar
        if not avatar_url.startswith("http"):
            return set_cache_header(
                send_file("img/default_avatar.png", mimetype="image/jpeg")
            )
        r = requests.get(avatar_url)
        with open(fn, "wb") as f:
            f.write(r.content)
    return set_cache_header(send_file(fn, mimetype="image/jpeg"))


@app.route(posixpath.join("/", config.url_base, "banner", "<type>", "<name>"))
def _banner(type, name):
    # print(type, name)
    fn = f"{config.fs_bases[type]}/{name}/banner"
    if not os.path.exists(fn):
        user = backend.User(name, type)
        user.load_from_db(db)
        banner_url = user.banner
        if not banner_url.startswith("http"):
            return set_cache_header(send_file("img/empty.png", mimetype="image/jpeg"))
        r = requests.get(banner_url)
        with open(fn, "wb") as f:
            f.write(r.content)
    return set_cache_header(send_file(fn, mimetype="image/jpeg"))


@app.route(posixpath.join("/", config.url_base + "/"))
@app.route(posixpath.join("/", config.url_base))
def _index():
    return redirect(posixpath.join("/", config.url_base, "tl"))


@app.route(posixpath.join("/", config.url_base, "userlist"))
def _userlist():
    if "p" in request.args:
        page = int(request.args["p"]) - 1
        page = max(0, page)
    else:
        page = 0
    if "q" in request.args:
        query = request.args["q"]
    else:
        query = ""
    if query:
        all_users = [
            u
            for u in backend.all_users
            if query.lower() in u.nick.lower() or query.lower() in u.user_name.lower()
        ]
        users = all_users[
            page * config.items_per_page : (page + 1) * config.items_per_page
        ]
        max_page = ceil(len(all_users) / config.items_per_page)
    else:
        users = backend.all_users[
            page * config.items_per_page : (page + 1) * config.items_per_page
        ]
        max_page = ceil(len(backend.all_users) / config.items_per_page)
    seach_bar = render_template("searchbar.html", url_base=config.url_base)
    userlist = render_template("userlist.html", users=users, url_base=config.url_base)
    return render_template(
        "nav.html",
        current_page=page + 1,
        current_q=query,
        current_url=posixpath.join("/", config.url_base, "userlist"),
        max_page=max_page,
        content=seach_bar + userlist,
        section="users",
        url_base=config.url_base,
    )


@app.route(posixpath.join("/", config.url_base, "tl"))
def _timeline():
    if "q" in request.args:
        query = request.args["q"]
        query = query.strip()
    else:
        query = ""

    if "p" in request.args:
        page = int(request.args["p"]) - 1
        page = max(0, page)
        backend.timeline_current_page = page
    else:
        if query:
            page = 0
        else:
            page = backend.timeline_current_page
    if "tab" in request.args:
        tab = request.args["tab"]
    else:
        tab = "posts"
    if "sort" in request.args:
        sort_ = request.args["sort"]
    else:
        sort_ = "new"
    if query:
        sorted_posts_id = db.query_post_by_text(query)
        all_post_count = len(sorted_posts_id)
        sorted_posts_id = sorted_posts_id[
            page * config.items_per_page : (page + 1) * config.items_per_page
        ]
        sorted_posts_id = [i[0] for i in sorted_posts_id]
    else:
        all_post_count = len(backend.cache_all_posts_id)
        if sort_ == "new":
            sorted_posts_id = backend.cache_all_posts_id[
                page * config.items_per_page : (page + 1) * config.items_per_page
            ]
        elif sort_ == "top":
            sorted_posts_id = backend.cache_all_posts_id_top[
                page * config.items_per_page : (page + 1) * config.items_per_page
            ]
        elif sort_ == "random":
            sorted_posts_id = backend.cache_all_posts_id_random[
                page * config.items_per_page : (page + 1) * config.items_per_page
            ]
        else:
            return "Invalid sort type."
        sorted_posts_id = [i[0] for i in sorted_posts_id]
    posts = dict()
    media_entries = dict()
    users = dict()
    for post_id in sorted_posts_id:
        post = backend.Post(post_id, None, None)
        post.load_from_db(db)
        post.init_embed(db)
        posts[post_id] = post
        for row in db.query_rows(table="media", key="post_id", value=post_id):
            media_id = row[0]
            media = backend.Media(media_id, post_id, None)
            media.load_from_db(db)
            if post_id not in media_entries:
                media_entries[post_id] = [media]
            else:
                media_entries[post_id].append(media)
        if post_id in media_entries:
            media_entries[post_id] = natsort.natsorted(
                media_entries[post_id], key=lambda x: x.media_id
            )
        if post.user_name not in users:
            user = backend.User(post.user_name)
            user.load_from_db(db)
            users[post.user_name] = user
    seach_bar = render_template("searchbar.html", url_base=config.url_base)
    timeline = render_template(
        "timeline.html",
        posts=posts,
        media_entries=media_entries,
        sorted_posts_id=sorted_posts_id,
        page=page,
        items_per_page=config.items_per_page,
        user_name="",
        type="tl",
        users=users,
        url_base=config.url_base,
        page_url=f"{config.url_base}/tl",
        show_sort_type=True,
        sort_type=sort_,
    )
    return render_template(
        "nav.html",
        content=seach_bar + timeline,
        current_page=page + 1,
        current_q=query,
        current_url=posixpath.join("/", config.url_base, "tl")
        + "?tab="
        + tab
        + "&sort="
        + sort_,
        max_page=ceil(all_post_count / config.items_per_page),
        section="tl",
        url_base=config.url_base,
    )


@app.route(posixpath.join("/", config.url_base, "fav"))
def _timeline_fav():
    if "p" in request.args:
        page = int(request.args["p"]) - 1
    else:
        page = 0
    if "tab" in request.args:
        tab = request.args["tab"]
    else:
        tab = "posts"
    try:
        sorted_posts_id = db.query_rows(
            table="fav", key="", value="", ignore_cache=True
        )
        all_post_count = len(sorted_posts_id)
        sorted_posts_id = [i[0] for i in sorted_posts_id if i[0]][::-1]
        if tab == "posts":
            sorted_posts_id = sorted_posts_id[
                page * config.items_per_page : (page + 1) * config.items_per_page
            ]
        else:
            sorted_posts_id = sorted_posts_id[
                page
                * config.items_per_page
                * 2 : (page + 1)
                * config.items_per_page
                * 2
            ]
    except ValueError:
        return "Not enough posts. Download more and come back later."

    if tab == "posts":
        posts = dict()
        media_entries = dict()
        users = dict()
        for post_id in sorted_posts_id:
            post = backend.Post(post_id, None, None)
            if not post.load_from_db(db):
                print(f"Post [{post_id}] not found.")
                continue
            post.init_embed(db)
            posts[post_id] = post
            for row in db.query_rows(table="media", key="post_id", value=post_id):
                media_id = row[0]
                media = backend.Media(media_id, post_id, None, post.type)
                media.load_from_db(db)
                if post_id not in media_entries:
                    media_entries[post_id] = [media]
                else:
                    media_entries[post_id].append(media)
            if post_id in media_entries:
                media_entries[post_id] = natsort.natsorted(
                    media_entries[post_id], key=lambda x: x.media_id
                )
            if post.user_name not in users:
                user = backend.User(post.user_name, post.type)
                user.load_from_db(db)
                users[post.user_name] = user
        timeline = render_template(
            "timeline.html",
            posts=posts,
            media_entries=media_entries,
            sorted_posts_id=sorted_posts_id,
            page=page,
            items_per_page=config.items_per_page,
            user_name="",
            type="",
            users=users,
            url_base=config.url_base,
            page_url=f"{config.url_base}/fav",
            show_media_toggle=True,
        )
        max_page = ceil(all_post_count / config.items_per_page)
    elif tab == "media":
        media_entries = dict()
        users = dict()
        sorted_media_id = []
        for post_id in sorted_posts_id:
            post = backend.Post(post_id, None, None)
            if not post.load_from_db(db):
                return f"Post [{post_id}] not found."
            for row in db.query_rows(table="media", key="post_id", value=post_id):
                media_id = row[0]
                sorted_media_id.append(media_id)
                media = backend.Media(media_id, post_id, None, post.type)
                media.load_from_db(db)
                media_entries[media_id] = media
            if post.user_name not in users:
                user = backend.User(post.user_name, post.type)
                user.load_from_db(db)
                users[post.user_name] = user
        timeline = render_template(
            "mediagrid.html",
            media_entries=media_entries,
            sorted_media_id=sorted_media_id,
            page=page,
            items_per_page=config.items_per_page * 2,
            user_name="",
            type=type,
            users=users,
            url_base=config.url_base,
            page_url=f"{config.url_base}/fav",
        )
        max_page = ceil(all_post_count / config.items_per_page / 2)
    return render_template(
        "nav.html",
        current_page=page + 1,
        current_url=posixpath.join("/", config.url_base, "fav") + "?tab=" + tab,
        max_page=max_page,
        content=timeline,
        section="fav",
        url_base=config.url_base,
    )


@app.route(posixpath.join("/", config.url_base, "user", "<type>", "<name>"))
def _timeline_user(type, name):
    if "p" in request.args:
        page = int(request.args["p"]) - 1
    else:
        page = 0
    if "tab" in request.args:
        tab = request.args["tab"]
    else:
        tab = "posts"

    user = backend.User(name, type)
    user.load_from_db(db)

    if tab == "posts":
        posts = dict()
        media_entries = dict()

        all_rows = db.query_rows(table="posts", key="user_name", value=name, sort_key=lambda x: x[0])
        for row in all_rows[
            page * config.items_per_page : (page + 1) * config.items_per_page
        ]:
            post_id = row[0]
            post = backend.Post(post_id, name, type)
            post.load_from_db(db)
            post.init_embed(db)
            posts[post_id] = post
            for row in db.query_rows(table="media", key="post_id", value=post_id):
                media_id = row[0]
                media = backend.Media(media_id, post_id, name, type)
                media.load_from_db(db)
                if post_id not in media_entries:
                    media_entries[post_id] = [media]
                else:
                    media_entries[post_id].append(media)
            if post_id in media_entries:
                media_entries[post_id] = natsort.natsorted(
                    media_entries[post_id], key=lambda x: x.media_id
                )
        sorted_posts_id = natsort.natsorted(posts.keys(), reverse=True)
        timeline = render_template(
            "timeline.html",
            posts=posts,
            media_entries=media_entries,
            sorted_posts_id=sorted_posts_id,
            page=page,
            items_per_page=config.items_per_page,
            user_name=name,
            type=type,
            users={f"{name}": user},
            url_base=config.url_base,
            page_url=f"{config.url_base}/user/{type}/{name}",
            show_media_toggle=True,
        )
        max_page = ceil(len(all_rows) / config.items_per_page)
    elif tab == "media":
        media_entries = dict()
        all_rows = db.query_rows(table="media", key="user_name", value=name)
        all_rows = natsort.natsorted(all_rows, key=lambda x: x[1], reverse=True)
        sorted_media_id = []
        for row in all_rows[
            page * config.items_per_page * 2 : (page + 1) * config.items_per_page * 2
        ]:
            media_id = row[0]
            post_id = row[1]
            media = backend.Media(media_id, post_id, name, type)
            media.load_from_db(db)
            media_entries[media_id] = media
            sorted_media_id.append(media_id)

        timeline = render_template(
            "mediagrid.html",
            media_entries=media_entries,
            sorted_media_id=sorted_media_id,
            page=page,
            items_per_page=config.items_per_page * 2,
            user_name=name,
            type=type,
            users={f"{name}": user},
            url_base=config.url_base,
            page_url=f"{config.url_base}/user/{type}/{name}",
        )
        max_page = ceil(len(all_rows) / config.items_per_page / 2)
    userheader = render_template(
        "userheader.html",
        type=type,
        user=user,
        url_base=config.url_base,
        posts_cnt=len(all_rows),
    )
    return render_template(
        "nav.html",
        content=userheader + timeline,
        section="users",
        current_page=page + 1,
        current_url=posixpath.join("/", config.url_base, "user", type, name)
        + "?tab="
        + tab,
        max_page=max_page,
        alt_home_icon=posixpath.join("/", config.url_base, "avatar", type, name),
        title=f"{user.nick} (@{name}) - {type}",
        url_base=config.url_base,
        user=user,
    )


@app.route(posixpath.join("/", config.url_base, "add_fav"))
def _add_fav():
    post_id = request.args["post_id"]
    if db.query_rows(table="fav", key="post_id", value=post_id, ignore_cache=True):
        print("remove favorite", post_id)
        backend.remove_favorite(db, post_id)
        return {
            "result": "removed",
        }
    else:
        print("add favorite", post_id)
        backend.add_favorite(db, post_id)
        return {
            "result": "added",
        }


@app.route(
    posixpath.join("/", config.url_base, "card", "<type>", "<name>", "<filename>")
)
def _card(type, name, filename):
    media_id = filename.split(".")[0]
    media = backend.Media(media_id, None, name, type)
    media.load_from_db(db)
    user = backend.User(name, type)
    user.load_from_db(db)
    post = backend.Post(media.post_id, name, type)
    post.load_from_db(db)
    card = render_template(
        "card.html", media=media, user=user, post=post, url_base=config.url_base
    )
    return card


@app.route(posixpath.join("/", config.url_base, "download"))
def _download():
    url = ""
    # print('-'*10,request.args)
    # print('+'*10,"url" in request.args)
    if "url" in request.args:
        url = request.args["url"]
    download = render_template(
        "download.html",
        default_input=url,
        msg=utils.current_url,
        queue="",
        url_base=config.url_base,
    )
    return render_template(
        "nav.html",
        content=download,
        current_page=0,
        current_url="",
        max_page=0,
        section="download",
        url_base=config.url_base,
    )


@app.route(posixpath.join("/", config.url_base, "file", "<type>", "<name>", "<fn>"))
def _file(type, name, fn):
    return set_cache_header(send_from_directory(config.fs_bases[type], f"{name}/{fn}"))


@app.route(posixpath.join("/", config.url_base, "thumb", "<type>", "<name>", "<fn>"))
def _thumb(type, name, fn):
    size = config.thubnail_size
    if "size" in request.args:
        size = int(request.args["size"])
        size = min(max(size, 32), 2500)
    path = f"{config.fs_bases[type]}/{name}/{fn}"
    thumbnail_path = utils.create_thumbnail(path, size)
    return set_cache_header(send_file(thumbnail_path, mimetype="image/jpeg"))


@app.route(posixpath.join("/", config.url_base, "view", "<type>", "<name>", "<fn>"))
def _view(type, name, fn):
    return render_template(
        "viewer.html",
        type=type,
        user_name=name,
        file_name=fn,
        isvideo=fn.endswith(".mp4") or fn.endswith(".webm"),
        url_base=config.url_base,
    )


@app.route(posixpath.join("/", config.url_base, "add"), methods=["POST"])
def _add_download_job():
    data = request.get_json()
    if "url" in data and data["url"]:
        url = data["url"]
        full = data.get("full", False)
        if not ("bsky" in url or "x.com" in url or "twitter" in url):
            msg = f"Invalid URL: {url}\n"
            print(msg)
            return jsonify(
                {"msg": msg, "current": utils.current_url, "queue": utils.download_jobs}
            )
        if "did:" in url:
            msg = f"Go get the actual bsky handle like 'xxx.bsky.social', {url} won't do.\n"
            print(msg)
            return jsonify(
                {"msg": msg, "current": utils.current_url, "queue": utils.download_jobs}
            )
        if re.match("\w+\.bsky\.social", url):
            url = "https://bsky.app/profile/" + url
        else:
            if not url.startswith("http"):
                url = f"https://{url}"
            url = url.replace("http://", "https://")
            if "bsky" in url:
                url = re.match("https://bsky.app/profile/[^/]+", url).group(0)
            elif "x.com" in url:
                url = re.match("https://x.com/[^/]+", url).group(0)
            elif "twitter.com" in url:
                url = re.match("https://twitter.com/[^/]+", url).group(0)
                url = url.replace("twitter.com","x.com")

        if not (url, full) in utils.download_jobs:
            utils.download_jobs.append((url, full))
            msg = f"Added {url} to download queue.\n"
        else:
            msg = f"{url} already in download queue.\n"
        print(msg)
    else:
        msg = "Input your url above.\n"
    return jsonify(
        {"msg": msg, "current": utils.current_url, "queue": utils.download_jobs}
    )


@app.route(posixpath.join("/", config.url_base, "shorts"), methods=["GET"])
def _shorts():
    if "idx" in request.args:
        idx = int(request.args["idx"])
    else:
        idx = 0
    if "user" in request.args:
        user_name = request.args["user"]
        if not user_name in backend.cache_user_media_id:
            media_ids = db.raw_query(
                f"SELECT media_id FROM media WHERE user_name = '{user_name}' AND file_name LIKE '%.mp4'"
            )
            media_ids = [i[0] for i in media_ids]
            if len(media_ids) > 0:
                media_ids = natsort.natsorted(media_ids)[::-1]
                backend.cache_user_media_id[user_name] = media_ids
            total_cnt = len(media_ids)
        else:
            total_cnt = len(backend.cache_user_media_id[user_name])
        return render_template(
            "shorts.html",
            url_base=config.url_base,
            user=user_name,
            current_cnt=idx,
            total_cnt=total_cnt,
        )
    else:
        user_name = ""
        idx = randint(0, len(backend.cache_all_media_id))
        return render_template(
            "shorts.html",
            url_base=config.url_base,
            current_cnt=idx,
            user=user_name,
            total_cnt=0,
        )


@app.route(posixpath.join("/", config.url_base, "get-a-vid"), methods=["GET"])
def _get_a_vid():
    if "user" in request.args:
        user_name = request.args["user"]
    else:
        user_name = ""
    if "idx" in request.args:
        idx = int(request.args["idx"])
    else:
        idx = 0
    if user_name:
        # get a media_id from user by order
        if not user_name in backend.cache_user_media_id:
            media_ids = db.raw_query(
                f"SELECT media_id FROM media WHERE user_name = '{user_name}' AND file_name LIKE '%.mp4'"
            )
            media_ids = [i[0] for i in media_ids]
            media_ids = natsort.natsorted(media_ids)[::-1]
            if not media_ids:
                return {
                    "error": f"No video found for user {user_name}.",
                }
            backend.cache_user_media_id[user_name] = media_ids
        else:
            print(f"cache hit for {user_name}")
            media_ids = backend.cache_user_media_id[user_name]
            print(len(media_ids), idx)
        idx = idx % len(media_ids)
        media_id = media_ids[idx]
    else:
        if len(backend.cache_all_media_id) == 0:
            return {
                "error": f"No video found.",
            }
        media_id = backend.cache_all_media_id[idx % len(backend.cache_all_media_id)]
    media = backend.Media(media_id, None, None)
    media.load_from_db(db)
    post = backend.Post(media.post_id, None, None)
    post.load_from_db(db)
    user = backend.User(post.user_name, post.type)
    user.load_from_db(db)
    data = {
        "url": posixpath.join(
            "/", config.url_base, "file", post.type, post.user_name, media.file_name
        ),
        "preview": posixpath.join(
            "/", config.url_base, "thumb", post.type, post.user_name, media.file_name
        ),
        "author": user.nick,
        "author_id": post.user_name,
        "avatar": f"{config.url_base}/avatar/{post.type}/{post.user_name}",
        "likes": post.likes,
        "comments": post.comments,
        "reposts": post.reposts,
        "description": post.text_content,
        "post_id": post.post_id,
        "media_id": media.media_id,
        "fav": bool(db.query_rows(table="fav", key="post_id", value=post.post_id)),
        "post_url": (
            f"https://bsky.app/profile/{post.user_name}/post/{post.post_id}"
            if post.type == "bsky"
            else f"https://x.com/{post.user_name}/status/{post.post_id}"
        ),
        "user_url": f"{config.url_base}/user/{post.type}/{post.user_name}",
        "time": post.time,
    }
    return jsonify(data)


def init(db, skip_scan):
    backend.scan_for_users("x", db)
    backend.scan_for_users("bsky", db)
    if not skip_scan:
        backend.scan_for_posts("x", db)
        backend.scan_for_media("x", db)
        backend.scan_for_posts("bsky", db)
        backend.scan_for_media("bsky", db)
    db.conn.commit()
    print("Scan finished.")

    print("Building cache...")
    backend.build_cache_all_posts_id(db)
    print("Cache built.")


db = backend.Database("test.db")
db.prepare_db()
utils.global_running_flag = True
worker = utils.DownloadWorker(db)
worker.setDaemon(True)
worker.start()
print("Download worker started.")
print("Ready.")


def shutdown_cleanup():
    utils.global_running_flag = False
    db.conn.close()


def signal_handler(signal, frame):
    shutdown_cleanup()
    sys.exit(0)


def pass_args(skip_scan=False):
    init(db, skip_scan)
    return app


if __name__ == "__main__":
    init(db, args.skip_scan)
    print(f"app is ready at: http://{config.host}:{config.port}/{config.url_base}")
    app.run(host=config.host, port=config.port, debug=args.debug)
    shutdown_cleanup()
else:
    signal.signal(signal.SIGTERM, signal_handler)
