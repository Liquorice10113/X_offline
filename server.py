#!/usr/bin/python3

from flask import (
    Flask,
    render_template,
    send_file,
    redirect,
    request,
    send_from_directory,
    Response,
)
import os
import re
import json
from urllib.parse import unquote, quote
from math import ceil, floor

import utils
import config

app = Flask(__name__)

meta = {"users": dict(), "posts": dict(), "tl": dict(), "loaded": set()}


def dump_meta():
    global meta
    c_meta = dict(meta)
    c_meta["loaded"] = list(c_meta["loaded"])
    json.dump(c_meta, open("meta.json", 'w'))


def load_meta():
    global meta
    if os.path.exists("meta.json"):
        c_meta = json.load(open("meta.json", 'r'))
        meta["users"] = c_meta["users"]
        meta["posts"] = c_meta["posts"]
        meta["tl"] = c_meta["tl"]
        meta["loaded"] = set(c_meta["loaded"])


def init_meta(u=""):
    global meta
    print("Scanning...")
    if not u:
        for i in os.listdir(config.fs_base):
            print("Scanning...", i)
            user_fs_base = os.path.join(config.fs_base, i)
            user = {
                "name": i,
                "nick": "",
                "count": 0,
                "avatar": "",
                "banner": "",
                "description": "",
            }
            u_json = [i for i in os.listdir(
                user_fs_base) if i.endswith("json")]
            if len(u_json) == 0:
                continue
            else:
                u_json = u_json[0]
                u_json_d = json.load(
                    open(os.path.join(user_fs_base, u_json),
                         "r", encoding="utf-8")
                )
                user["nick"] = u_json_d["author"]["nick"]
                user["avatar"] = u_json_d["author"]["profile_image"]
                user["banner"] = u_json_d["author"]["profile_banner"]
                user["description"] = utils.hyper_link(
                    u_json_d["author"]["description"])
            user["count"] = len(
                [i for i in os.listdir(user_fs_base) if utils.is_img(i)])
            meta["users"][i] = user
            utils.scan_posts(i, meta)
            print(i, "OK.")
        print("Scanning... OK.")
    else:
        print("Scanning...", u)
        user_fs_base = os.path.join(config.fs_base, u)
        user = {
            "name": u,
            "nick": "",
            "count": 0,
            "avatar": "",
            "banner": "",
            "description": "",
        }
        u_json = [i for i in os.listdir(user_fs_base) if i.endswith("json")]
        if len(u_json) > 0:
            u_json = u_json[0]
            u_json_d = json.load(
                open(os.path.join(user_fs_base, u_json), "r", encoding="utf-8")
            )
            user["nick"] = u_json_d["author"]["nick"]
            user["avatar"] = u_json_d["author"]["profile_image"]
            user["banner"] = u_json_d["author"]["profile_banner"]
            user["description"] = utils.hyper_link(
                u_json_d["author"]["description"])
        user["count"] = len(
            [i for i in os.listdir(user_fs_base) if utils.is_img(i)])
        meta["users"][u] = user
        utils.scan_posts(u, meta)
        print(u, "OK.")
    dump_meta()


@app.route("/")
def rd():
    return redirect("/" + config.url_base)


@app.route("/" + config.url_base + "/static/<path>")
def static_(path):
    print(path)
    return send_from_directory("static", path)


@app.route("/" + config.url_base + "/x.webmanifest")
def pwa():
    return send_from_directory("static", "x.webmanifest")


@app.route("/" + config.url_base)
@app.route("/" + config.url_base + "/")
def index():
    global meta
    p = 0
    from_ = ""
    if "p" in request.args:
        p = int(request.args["p"]) - 1
    elif "from" in request.args:
        from_ = request.args["from"]
        print("from", from_)
    users = []
    for i in os.listdir(config.fs_base):
        user_fs_base = os.path.join(config.fs_base, i)
        if i in meta["users"]:
            user = meta["users"][i]
        else:
            user = {
                "name": i,
                "nick": "",
                "count": 0,
                "avatar": "",
                "banner": "",
                "description": "No description available.",
            }
            u_json = [i for i in os.listdir(
                user_fs_base) if i.endswith("json")]
            if len(u_json) == 0:
                user["nick"] = i
            else:
                u_json = u_json[0]
                u_json_d = json.load(
                    open(os.path.join(user_fs_base, u_json),
                         "r", encoding="utf-8")
                )
                user["nick"] = u_json_d["author"]["nick"]
                user["avatar"] = u_json_d["author"]["profile_image"]
                user["banner"] = u_json_d["author"]["profile_banner"]
                user["description"] = u_json_d["author"]["description"]
            user["count"] = len(
                [i for i in os.listdir(user_fs_base) if utils.is_img(i)]
            )
            meta["users"][i] = user
        users.append(user)

    users = sorted(users, key=lambda u: -
                   os.path.getatime(os.path.join(config.fs_base, u['name'])))
    if p == 0 and from_:
        names = [i['name'] for i in users]
        if from_ in names:
            p = int(names.index(from_)/config.items_per_page)
    nav = [0, 0, 0, 0]
    nav[0] = max(p, 1)
    nav[1] = p + 1
    nav[3] = floor(len(users) / config.items_per_page)+1
    nav[2] = min(p + 2, nav[3])
    users = users[p*config.items_per_page:(p+1)*config.items_per_page]
    return render_template("index.html", base=config.url_base, users=users, str=str, nav=nav)


@app.route("/" + config.url_base + "/avatar/<user>")
def avatar(user):
    avatar_path = os.path.join(config.fs_base, user, "avatar")
    if os.path.exists(avatar_path):
        print("/avatar/{0} Serving avatar from local.".format(user))
        return send_file(
            avatar_path,
            mimetype="image/jpeg",
        )
    elif user in meta["users"] and meta["users"][user]["avatar"]:
        avatar_url = meta["users"][user]["avatar"]
        print("/avatar/{0} Fetching avatar from twitter...".format(user))
        utils.put(avatar_url, avatar_path)
        print("/avatar/{0} Serving avatar.".format(user))
        return send_file(
            avatar_path,
            mimetype="image/jpeg",
        )
    else:
        return send_from_directory("static", "default_avatar.png")


@app.route("/" + config.url_base + "/banner/<user>")
def banner(user):
    banner_path = os.path.join(config.fs_base, user, "banner")
    if os.path.exists(banner_path):
        print("/banner/{0} Serving banner from local.".format(user))
        return send_file(
            banner_path,
            mimetype="image/jpeg",
        )
    elif user in meta["users"] and meta["users"][user]["banner"]:
        banner_url = meta["users"][user]["banner"]
        print("/banner/{0} Fetching banner from twitter...".format(user))
        utils.put(banner_url, banner_path)
        print("/banner/{0} Serving banner.".format(user))
        return send_file(
            banner_path,
            mimetype="image/jpeg",
        )
    else:
        return send_from_directory("static", "default_banner.jpg")


@app.route("/" + config.url_base + "/u/<name>")
def user_page(name):
    global meta
    p = 0
    if "p" in request.args:
        p = int(request.args["p"]) - 1
    user_fs_base = os.path.join(config.fs_base, name)
    if not os.path.exists(user_fs_base):
        return Response("Not found.", status=404)

    items_per_page = config.items_per_page

    grid = False
    if "grid" in request.args:
        grid = True
        items_per_page *= 2

    # Prepare user data
    if name in meta["users"]:
        user = meta["users"][name]
    else:
        user = {
            "name": name,
            "nick": "",
            "count": 0,
            "avatar": "",
            "banner": "",
            "description": "No description available.",
        }
        u_json = [i for i in os.listdir(user_fs_base) if i.endswith("json")]
        if len(u_json) == 0:
            user["nick"] = name
        else:
            u_json = u_json[0]
            u_json_d = json.load(
                open(os.path.join(user_fs_base, u_json), "r", encoding="utf-8")
            )
            user["nick"] = u_json_d["author"]["nick"]
            user["avatar"] = u_json_d["author"]["profile_image"]
            user["banner"] = u_json_d["author"]["profile_banner"]
            user["description"] = utils.hyper_link(
                u_json_d["author"]["description"])
        user["count"] = len(
            [i for i in os.listdir(user_fs_base) if utils.is_img(i)])
        meta["users"][name] = user
    # Prepare posts
    if name in meta["posts"]:
        posts = meta["posts"][name]
    else:
        posts = utils.scan_posts(name, meta)
    sorted_posts = sorted(list(posts.keys()), key=int, reverse=True)[
        p * items_per_page: (p + 1) * items_per_page
    ]
    nav = [0, 0, 0, 0]
    nav[0] = max(p, 1)
    nav[1] = p + 1
    nav[3] = floor(len(posts) / items_per_page)+1
    nav[2] = min(p + 2, nav[3])

    if grid:
        contents_frag = render_template(
            "user_g.html",
            base=config.url_base,
            user=user,
            posts=posts,
            sorted_posts=sorted_posts,
            nav=nav,
        )
    else:
        contents_frag = render_template(
            "user_p.html",
            base=config.url_base,
            user=user,
            posts=posts,
            sorted_posts=sorted_posts,
            nav=nav,
        )

    return render_template(
        "user.html",
        base=config.url_base,
        user=user,
        posts=posts,
        sorted_posts=sorted_posts,
        nav=nav,
        contents_frag=contents_frag,
        grid=grid,
        grid_suffix="&grid" if grid else ""
    )


@app.route("/" + config.url_base + "/thumb/<user>/<fn>")
def thumb(user, fn):
    user = unquote(user)
    if "size" in request.args:
        size = int(request.args["size"])
    else:
        size = config.thumbnail_big_size
    return send_file(
        utils.thumbnails(os.path.join(config.fs_base, user, fn), size),
        mimetype="image/jpeg",
    )


@app.route("/" + config.url_base + "/full/<user>/<fn>")
def full(user, fn):
    user = unquote(user)
    full_img_path = os.path.join(config.fs_base, user, fn)
    return send_file(full_img_path)


@app.route("/" + config.url_base + "/add")
def dl():
    url = unquote(request.args["url"])
    if not re.match("https\:\/\/(x\.com|twitter\.com)/.+", url):
        return "Not a valid URL."
    if url in utils.dl_Q or url == utils.current:
        return "Already in queue.\n Current job:\n {0}\n Queue:\n {1}".format(utils.current, "\n ".join(utils.dl_Q))
    else:
        utils.dl_Q.append(url)
        return "Job added.\n Current job:\n {0}\n Queue:\n {1}".format(utils.current, "\n ".join(utils.dl_Q))


@app.route("/" + config.url_base + "/dl_statue")
def dl_status():
    return "Current job:\n {0}\n Queue:\n {1}".format(utils.current, "\n ".join(utils.dl_Q))


@app.route("/" + config.url_base + "/reload")
def meta_reload():
    u = ""
    if "u" in request.args:
        u = request.args["u"]
    init_meta(u)
    return "ok"


@app.route("/" + config.url_base + "/tl")
def tl():
    p = 0
    if "p" in request.args:
        p = int(request.args["p"]) - 1

    sorted_posts = sorted(list(meta["tl"].keys()), key=int, reverse=True)[
        p*config.items_per_page:(p+1)*config.items_per_page]
    nav = [0, 0, 0, 0]
    nav[0] = max(p, 1)
    nav[1] = p + 1
    nav[3] = floor(len(meta["tl"]) / config.items_per_page)+1
    nav[2] = min(p + 2, nav[3])
    return render_template("timeline.html", base=config.url_base, nav=nav, sorted_posts=sorted_posts, posts=meta["tl"])


@app.route("/" + config.url_base + "/large/<user>/<fn>")
def large(user, fn):
    return render_template("view_img.html", base=config.url_base, user=user, fn=fn, is_vid=utils.is_vid(fn))


load_meta()
init_meta()
app.run(debug=True, port=config.port, host="0.0.0.0")
