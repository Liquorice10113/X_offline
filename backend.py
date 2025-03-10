import sqlite3
import os, json, re, time, sys
import natsort

import config, utils

class Database:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cached_query_words = dict()
        self.last_text_query_time = -1

    def prepare_db(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS users (
            user_name TEXT PRIMARY KEY,
            nick TEXT,
            avatar TEXT,
            banner TEXT,
            description TEXT,
            type TEXT
        )"""
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS posts (
            post_id TEXT PRIMARY KEY,
            text_content TEXT,
            user_name TEXT,
            nick TEXT,
            time TEXT,
            type TEXT,
            url TEXT,
            likes INTEGER,
            reposts INTEGER,
            comments INTEGER
        )"""
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_posts_user_name ON posts(user_name)"
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS media (
            media_id TEXT PRIMARY KEY,
            post_id TEXT,
            file_name TEXT,
            user_name TEXT,
            type TEXT
        )"""
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_post_id ON media(post_id)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_post_id ON media(user_name)"
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS fav (
            post_id TEXT PRIMARY KEY,
            fav_time TEXT
        )"""
        )
        cursor.close()
        self.conn.commit()

    def insert_or_update_user(self, user_name, nick, avatar, banner, description, type):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?)",
            (user_name, nick, avatar, banner, description, type),
        )
        cursor.close()

    def insert_or_update_post(
        self,
        post_id,
        text_content,
        user_name,
        nick,
        time,
        type,
        url,
        likes,
        reposts,
        comments,
    ):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO posts VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                post_id,
                text_content,
                user_name,
                nick,
                time,
                type,
                url,
                likes,
                reposts,
                comments,
            ),
        )
        cursor.close()

    def insert_or_update_media(self, media_id, post_id, file_name, user_name, type):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO media VALUES (?,?,?,?,?)",
            (media_id, post_id, file_name, user_name, type),
        )
        cursor.close()

    def query_rows(self, table, key, value):
        cursor = self.conn.cursor()
        if key:
            cursor.execute(f"SELECT * FROM {table} WHERE {key} = ?", (value,))
        else:
            cursor.execute(f"SELECT * FROM {table}")
        res = cursor.fetchall()
        cursor.close()
        return res

    def query_post_by_text(self, text_content):
        if abs(self.last_text_query_time - time.time())>1200:
            print('Clear outdated query cache.')
            self.last_text_query_time = time.time()
            self.cached_query_words = dict()
        text_content = text_content.strip()
        words = tuple(set([i for i in text_content.split() if i and i != " "]))
        if words in self.cached_query_words:
            print("Use cached query for", words)
            return self.cached_query_words[words]
        cursor = self.conn.cursor()

        placeholders = " AND ".join(["text_content || user_name || nick LIKE ?"] * len(words))
        sql_query = f"SELECT post_id, time FROM posts WHERE {placeholders}"
        params = tuple([f"%{word}%" for word in words])
        cursor.execute(sql_query, params)
        self.cached_query_words[words] = cursor.fetchall()
        # print(self.cached_query_words[words])

        # placeholders = " OR ".join(["user_name LIKE ?"] * len(words))
        # sql_query = f"SELECT post_id, time FROM posts WHERE {placeholders}"
        # params = tuple([f"%{word}%" for word in words])
        # cursor.execute(sql_query, params)
        # self.cached_query_words[words] = utils.list_and(cursor.fetchall(),self.cached_query_words[words])

        self.cached_query_words[words] = natsort.natsorted(self.cached_query_words[words], key=lambda x:x[1] , reverse=True)

        cursor.close()
        return self.cached_query_words[words]

    def execute(self, sql):
        cursor = self.conn.cursor()
        cursor.execute(sql)
        res = cursor.fetchall()
        cursor.close()
        return res


class Post:
    def __init__(self, post_id, user_name, type=""):
        self.post_id = post_id
        self.user_name = user_name
        self.nick = ""
        self.type = type
        self.fav = False

    def load_from_db(self, db):
        rows = db.query_rows("posts", "post_id", self.post_id)
        if len(rows) == 0:
            return False
        row = rows[0]
        self.user_name = row[2]
        self.nick = row[3]
        self.time = row[4]
        self.type = row[5]
        self.url = row[6]
        self.likes = row[7]
        self.reposts = row[8]
        self.comments = row[9]
        self.text_content = utils.embed_hyperlink(self.type, row[1])
        # check if post is in fav
        rows = db.query_rows("fav", "post_id", self.post_id)
        if len(rows) > 0:
            self.fav = True
        return True

    def save_to_db(self, db):
        db.insert_or_update_post(
            self.post_id,
            self.text_content,
            self.user_name,
            self.nick,
            self.time,
            self.type,
            self.url,
            self.likes,
            self.reposts,
            self.comments,
        )

    def load_from_json(self, json, db):
        if self.type == "x":
            self.post_id = str(json["tweet_id"])
            self.text_content = json["content"]
            self.user_name = json["author"]["name"].lower()
            self.nick = json["author"]["nick"]
            self.time = json["date"]
            self.url = f"https://twitter.com/{self.user_name}/status/{self.post_id}"
            self.likes = json["favorite_count"]
            self.reposts = json["retweet_count"]
            self.comments = json["reply_count"]
        elif self.type == "bsky":
            self.post_id = str(json["post_id"])
            self.text_content = json["text"]
            self.user_name = json["author"]["handle"].lower()
            self.nick = json["author"]["displayName"]
            self.time = json["date"]
            self.url = f"https://bsky.app/profile/{self.user_name}/post/{self.post_id}"
            self.likes = json["likeCount"]
            self.reposts = json["repostCount"]
            self.comments = json["replyCount"]
        self.save_to_db(db)


class User:
    def __init__(self, user_name, type=""):
        self.user_name = user_name.lower()
        self.type = type
        self.nick = ""

    def load_from_db(self, db):
        rows = db.query_rows("users", "user_name", self.user_name)
        # print(rows)
        if len(rows) == 0:
            return False
        row = rows[0]
        self.nick = row[1]
        self.avatar = row[2]
        self.banner = row[3]
        self.type = row[5]
        self.description = utils.embed_hyperlink(self.type, row[4])
        self.concat_url()
        return True

    def load_from_inline(self, nick, avatar, banner, description):
        self.nick = nick
        self.avatar = avatar
        self.banner = banner
        self.description = description
        self.concat_url()

    def save_to_db(self, db):
        db.insert_or_update_user(
            self.user_name,
            self.nick,
            self.avatar,
            self.banner,
            self.description,
            self.type,
        )

    def load_from_json(self, json, db):
        if self.type == "x":
            self.nick = json["author"]["nick"]
            self.avatar = json["author"]["profile_image"]
            self.banner = ""
            self.description = ""
            try:
                self.banner = json["author"]["profile_banner"]
            except:
                print(
                    f"warning: user {self.user_name} has no banner.\ndownload again with lasest gallery-dl version to fix this."
                )
            try:
                self.description = json["author"]["description"]
            except:
                print(
                    f"warning: user {self.user_name} has nodescription.\ndownload again with lasest gallery-dl version to fix this."
                )
        elif self.type == "bsky":
            self.nick = json["author"]["displayName"]
            self.avatar = json["author"]["avatar"]
            self.banner = ""
            self.description = ""
            try:
                self.banner = json["user"]["banner"]
            except:
                print(
                    f"warning: user {self.user_name} has no banner.\ndownload again with lasest gallery-dl version to fix this."
                )
            try:
                self.description = json["user"]["description"]
            except:
                print(
                    f"warning: user {self.user_name} has nodescription.\ndownload again with lasest gallery-dl version to fix this."
                )
        self.concat_url()
        self.save_to_db(db)

    def concat_url(self):
        if self.type == "x":
            self.url = f"https://twitter.com/{self.user_name}"
        elif self.type == "bsky":
            self.url = f"https://bsky.app/profile/{self.user_name}"


class Media:
    def __init__(self, media_id, post_id, user_name, type=""):
        self.media_id = media_id
        self.post_id = post_id
        self.user_name = user_name
        self.type = type

    def save_to_db(self, db):
        db.insert_or_update_media(
            self.media_id, self.post_id, self.file_name, self.user_name, self.type
        )

    def load_from_db(self, db):
        rows = db.query_rows("media", "media_id", self.media_id)
        if len(rows) == 0:
            return False
        row = rows[0]
        self.post_id = row[1]
        self.file_name = row[2]
        self.user_name = row[3]
        self.type = row[4]
        self.isvideo = self.file_name.split(".")[-1] in ["mp4", "webm"]
        return True


# scan for content downloaded using gallery-dl
def scan_for_users(type, db, user_name=None):
    global modified_time_cache
    fs_base = config.fs_bases[type]
    # assume that the user name is the same as the directory name
    if not user_name:
        user_names = os.listdir(fs_base)
    else:
        user_names = [user_name]
    for user_name in user_names:
        if not os.path.exists(os.path.join(fs_base, user_name)):
            print(user_name, "does not exists!")
            break
        modified_time = os.path.getmtime(os.path.join(fs_base, user_name))
        modified_time_cache[type][user_name] = modified_time
        print(f"scanning for user {user_name}".ljust(80, " "), end="\r")
        sys.stdout.flush()
        user = User(user_name, type)
        if not user.load_from_db(db) or len(user_names) == 1:
            # user not found in database, create a new entry
            # select the first json file
            file_list = os.listdir(os.path.join(fs_base, user_name))
            json_files = [f for f in file_list if f.endswith(".json")]
            json_files.sort(reverse=True)
            if len(json_files) > 0:
                with open(
                    os.path.join(fs_base, user_name, json_files[0]),
                    "r",
                    encoding="utf=8",
                ) as f:
                    user_json = json.load(f)
                    user.load_from_json(user_json, db)
            else:
                # no json file found, use dummy values
                user.nick = user_name
                user.avatar = ""
                user.banner = ""
                user.description = ""
                user.save_to_db(db)


def scan_for_posts(type, db, user_name=None):
    fs_base = config.fs_bases[type]
    if not user_name:
        user_names = os.listdir(fs_base)
    else:
        user_names = [user_name]
    for cnt, user_name in enumerate(user_names):
        print(
            f"[{cnt+1}/{len(user_names)}] scanning for posts of user {user_name}".ljust(
                90, " "
            ),
            end="\r",
        )
        sys.stdout.flush()
        filelist = os.listdir(os.path.join(fs_base, user_name))
        json_files = [f for f in filelist if f.endswith(".json")]
        regex_map = {
            "x": {"file_patterns": [r"\d+.+json"], "id_pattern": r"(\d+)"},
            "bsky": {
                "file_patterns": [r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}.+\.json"],
                "id_pattern": r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_([^_]+).+",
            },
        }

        patterns = regex_map.get(type)
        if patterns:
            post_files = []
            for pat in patterns["file_patterns"]:
                post_files += [f for f in json_files if re.match(pat, f)]
            for post_file in post_files:
                # print(post_file)
                post_id = re.match(patterns["id_pattern"], post_file).group(1)
                # print("matching post_id:", post_id)
                post = Post(post_id, user_name, type)
                if not post.load_from_db(db):
                    with open(
                        os.path.join(fs_base, user_name, post_file),
                        "r",
                        encoding="utf=8",
                    ) as f:
                        try:
                            post_json = json.load(f)
                            post.load_from_json(post_json, db)
                        except Exception as e:
                            print(e)
                            print(
                                "Error loading:",
                                os.path.join(fs_base, user_name, post_file),
                            )
        db.conn.commit()


def scan_for_media(type, db, user_name=None):
    fs_base = config.fs_bases[type]
    valid_media_types = ["jpg", "jpeg", "png", "gif", "mp4", "webm"]
    if not user_name:
        user_names = os.listdir(fs_base)
    else:
        user_names = [user_name]
    for cnt, user_name in enumerate(user_names):
        print(
            f"[{cnt+1}/{len(user_names)}] scanning for media of user {user_name}".ljust(
                90, " "
            ),
            end="\r",
        )
        sys.stdout.flush()
        filelist = os.listdir(os.path.join(fs_base, user_name))
        media_files = [f for f in filelist if f.split(".")[-1] in valid_media_types]
        for media_file in media_files:
            media_id = media_file.split(".")[0]
            if type == "x":
                id_pattern = r"(\d+)"
            else:
                id_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_([^_]+).+"
            try:
                related_post_id = re.match(id_pattern, media_file).group(1)
                # print("matching post_id from filename:", related_post_id)
            except:
                related_post_id = "0" + media_file
                print("warning: no post_id found in filename:", media_file)
            media = Media(media_id, related_post_id, user_name, type)
            media.file_name = media_file
            if not media.load_from_db(db):
                media.save_to_db(db)
            # test if related post exists
            post = Post(related_post_id, user_name, type)
            if not post.load_from_db(db):
                print(
                    f"warning: media {media_id} has no related post {related_post_id} in database"
                )
                # create a dummy post
                post.text_content = media_file
                post.user_name = user_name
                post.time = time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.gmtime(
                        os.path.getmtime(
                            os.path.join(config.fs_bases[type], user_name, media_file)
                        )
                    ),
                )
                post.type = type
                post.url = ""
                post.likes = 0
                post.reposts = 0
                post.comments = 0
                post.save_to_db(db)


def get_users(db):
    rows = db.execute("SELECT * FROM users")
    users = []
    for row in rows:
        user = User(row[0], row[5])
        user.load_from_inline(row[1], row[2], row[3], row[4])
        users.append(user)
    users.sort(key=lambda u: modified_time_cache[u.type][u.user_name], reverse=True)
    # users.sort()
    return users


cache_all_posts_id = []
modified_time_cache = {"x": dict(), "bsky": dict()}


def build_cache_all_posts_id(db):
    global cache_all_posts_id
    rows = db.execute("SELECT post_id,type,time FROM posts")
    cache_all_posts_id = []
    for row in rows:
        post_id = row[0]
        post_time = row[2]
        cache_all_posts_id.append((post_id, post_time))
    cache_all_posts_id = natsort.natsorted(
        cache_all_posts_id, key=lambda p: p[1], reverse=True
    )


def add_favorite(db, post_id):
    if not db.query_rows("posts", "post_id", post_id):
        return
    db.execute(f"INSERT OR REPLACE INTO fav VALUES ('{post_id}', '{time.ctime()}')")
    db.conn.commit()


def remove_favorite(db, post_id):
    db.execute(f"DELETE FROM fav WHERE post_id = '{post_id}'")
    db.conn.commit()


if not os.path.exists(config.fs_bases["x"]):
    os.makedirs(config.fs_bases["x"])
if not os.path.exists(config.fs_bases["bsky"]):
    os.makedirs(config.fs_bases["bsky"])

if __name__ == "__main__":
    db = Database("test.db")
    db.prepare_db()
    scan_for_users("x", db)
    scan_for_posts("x", db)
    scan_for_media("x", db)
    db.conn.close()
