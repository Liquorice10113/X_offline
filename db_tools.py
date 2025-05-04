#!/usr/bin/env python3

import config
import os, re, sqlite3, shutil, time

config.fs_bases["x"] = os.path.expanduser(config.fs_bases["x"])
config.fs_bases["bsky"] = os.path.expanduser(config.fs_bases["bsky"])
sqlite_file = "./test.db"


def remove_legacy_json():
    for folder in os.listdir(config.fs_bases["x"]):
        folder_path = os.path.join(config.fs_bases["x"], folder)
        if not os.path.isdir(folder_path):
            continue
        for file in os.listdir(folder_path):
            match = re.search(r"(_\d\.\w{3})\.json", file)
            if match:
                new_json = file.replace(match.group(1), "")
                legacy_file = os.path.join(folder_path, file)
                new_file = os.path.join(folder_path, new_json)
                if os.path.exists(new_file):
                    print(
                        "File already exists: "
                        + new_json
                        + " so safe to remove "
                        + file
                    )
                    print(legacy_file + " -> " + new_file)
                    os.remove(legacy_file)
        if os.path.exists(os.path.join(folder_path, "info.json")):
            os.remove(os.path.join(folder_path, "info.json"))
    for folder in os.listdir(config.fs_bases["bsky"]):
        folder_path = os.path.join(config.fs_bases["bsky"], folder)
        if not os.path.isdir(folder_path):
            continue
        for file in os.listdir(folder_path):
            match = re.search(r"(_\d\.\w{3})\.json", file)
            if match:
                new_json = file.replace(match.group(1), "")
                legacy_file = os.path.join(folder_path, file)
                new_file = os.path.join(folder_path, new_json)
                if os.path.exists(new_file):
                    print(
                        "File already exists: "
                        + new_json
                        + " so safe to remove "
                        + file
                    )
                    print(legacy_file + " -> " + new_file)
                    os.remove(legacy_file)
        if os.path.exists(os.path.join(folder_path, "info.json")):
            os.remove(os.path.join(folder_path, "info.json"))


def drop_table_users():
    if input("drop users table?[y/n]") == "y":
        table_name_to_drop = "users"
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {table_name_to_drop}")
        conn.commit()
        conn.close()


def sanity_check():
    suggestions = set()
    print("Starting sanity check...")
    conn = sqlite3.connect(sqlite_file)
    cursor = conn.cursor()
    users = set()
    cursor.execute("SELECT user_name,type FROM media")
    for row in cursor.fetchall():
        users.add((row[0], row[1]))
    cursor.execute("SELECT user_name,type FROM posts")
    for row in cursor.fetchall():
        users.add((row[0], row[1]))
    conn.close()
    files_list = dict()
    for user, type_ in list(users):
        user_fs_base = os.path.join(config.fs_bases[type_], user)
        if not os.path.exists(user_fs_base):
            suggestions.add(
                f"UID {user} no longer exsists in filesystem. Try clean_user()."
            )
            continue
        for file in os.listdir(user_fs_base):
            if file in files_list:
                files_list[file].append(user)
            else:
                files_list[file] = [user]
    for file, users in files_list.items():
        if file in ["info.json", "avatar", "banner"]:
            continue
        if len(users) > 1:
            # print(f"File {file} is shared by {users}")
            suggestions.add(
                f"{' '.join(users)} may be the same user. Try user_rename()."
            )
    print("Sanity check done.")
    if suggestions:
        print("Suggestions:")
        for suggestion in suggestions:
            print(suggestion)


def clean_user():
    id_ = input("id>>")
    if len(id_) < 2:
        print("Not allowed.")
        return
    sql1 = f'DELETE FROM posts WHERE user_name = "{id_}"'
    sql2 = f'DELETE FROM media WHERE user_name = "{id_}"'
    sql3 = f'DELETE FROM users WHERE user_name = "{id_}"'
    if input(f"{sql1}\n{sql2}\n{sql3}\nSure?[y/n]>>") == "y":
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        cursor.execute(sql1)
        cursor.execute(sql2)
        cursor.execute(sql3)
        conn.commit()
        conn.close()


def user_rename():
    print("Rename user.")
    print("Figure out the user's latest id first, search on x.com or bsky.social to see which one currently exsits.")
    id_ = input("id>>").lower().strip()
    to_id_ = input("to_id>>").lower().strip()
    if "." in id_:
        type_ = "bsky"
    else:
        type_ = "x"
    if input(f"Rename {id_} to {to_id_}?[y/n]>>") == "y":

        if not os.path.exists(os.path.join(config.fs_bases[type_], id_)):
            print(f"UID {id_} no longer exsists in filesystem.")
            return
        # move os.path.join(config.fs_bases[type_],id_) to os.path.join(config.fs_bases[type_],to_id_)
        # if os.path.join(config.fs_bases[type_],to_id_) exists, move all files in os.path.join(config.fs_bases[type_],id_) to os.path.join(config.fs_bases[type_],to_id_)
        if os.path.exists(os.path.join(config.fs_bases[type_], to_id_)):
            for file in os.listdir(os.path.join(config.fs_bases[type_], id_)):
                # skip exsisitng files
                if os.path.exists(os.path.join(config.fs_bases[type_], to_id_, file)):
                    continue
                os.rename(
                    os.path.join(config.fs_bases[type_], id_, file),
                    os.path.join(config.fs_bases[type_], to_id_, file),
                )
            shutil.rmtree(os.path.join(config.fs_bases[type_], id_))
        else:
            os.rename(
                os.path.join(config.fs_bases[type_], id_),
                os.path.join(config.fs_bases[type_], to_id_),
            )

        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        try:
            cursor.execute(
                f'UPDATE posts SET user_name = "{to_id_}" WHERE user_name = "{id_}"'
            )
        except Exception as e:
            print(e)
        try:
            cursor.execute(
                f'UPDATE media SET user_name = "{to_id_}" WHERE user_name = "{id_}"'
            )
        except Exception as e:
            print(e)
            pass
        try:
            cursor.execute(
                f'UPDATE users SET user_name = "{to_id_}" WHERE user_name = "{id_}"'
            )
        except Exception as e:
            print(e)
            if "UNIQUE constraint failed" in str(e):
                print(f"Trying to delete {id_} from users table.")
                cursor.execute(f'DELETE FROM users WHERE user_name = "{id_}"')
                print('Done.')
            pass
        conn.commit()
        conn.close()


def sql_console():
    conn = sqlite3.connect(sqlite_file)
    cursor = conn.cursor()
    while True:
        sql = input("sql>>")
        if sql == "exit":
            break
        try:
            cursor.execute(sql)
            print(cursor.fetchall())
        except Exception as e:
            print(e)
        except KeyboardInterrupt:
            break
        conn.commit()
    conn.close()

def external_vid_fix():
    print("This will try to download all external videos of posts, which gallery-dl won't. Only twitter/x has this issue.")
    print("This will take a while, so be patient. If the download keeps failing, you are rate limited, wait and try again later.")
    print("Using yt-dlp to download videos. Make sure yt-dlp is installed.")
    user_id = input("user_id(twitter/x) >>")
    if "bsky" in user_id:
        print("This is a bsky user, so no need to download videos.")
        return
    json_list = os.listdir(os.path.join(config.fs_bases["x"], user_id))
    json_list.sort(reverse=True)
    for json_file in json_list:
        if not json_file.endswith(".json"):
            continue
        post_id = re.match("(\d+)", json_file)
        if not post_id:
            continue

        post_id = post_id.group(1)
        if os.path.exists(os.path.join(config.fs_bases["x"], user_id, f"{post_id}.mp4")) or os.path.exists(os.path.join(config.fs_bases["x"], user_id, f"{post_id}_1.mp4")) or os.path.exists(os.path.join(config.fs_bases["x"], user_id, f"{post_id}.jpg")) or os.path.exists(os.path.join(config.fs_bases["x"], user_id, f"{post_id}_1.jpg")):
            print(f"Post {post_id}'s media already exists, skipping.")
            continue
        
        time.sleep(1)

        post_url = f"https://x.com/{user_id}/status/{post_id}"
        video_file_name = os.path.join(config.fs_bases["x"], user_id, f"{post_id}.%(ext)s")
        cmd = [
            'yt-dlp',
            post_url,
            "-o",
            f"\"{video_file_name}\"",
            "--cookies",
            config.cookies_list["x"]
        ]
        print(f"Downloading {post_url} to {video_file_name}, pay attention to the output of yt-dlp.")
        print(" ".join(cmd))
        os.system(" ".join(cmd))
        print("Done.")




if __name__ == "__main__":
    while True:
        choice = input(
            "[0] sanity_check()\n[1] remove_legacy_json()\n[2] drop_table_users()\n[3] clean_user()\n[4] user_rename()\n[5] sql_console()\n[6] external_vid_fix() \n>>"
        )
        if choice == "0":
            sanity_check()
        if choice == "1":
            remove_legacy_json()
        elif choice == "2":
            drop_table_users()
        elif choice == "3":
            clean_user()
        elif choice == "4":
            user_rename()
        elif choice == "5":
            sql_console()
        elif choice == "6":
            external_vid_fix()
