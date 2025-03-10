#!/usr/bin/env python3

import config
import os, re, sqlite3

config.fs_bases["x"] = os.path.expanduser(config.fs_bases["x"])
config.fs_bases["bsky"] = os.path.expanduser(config.fs_bases["bsky"])
sqlite_file = './test.db'

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
                    print("File already exists: " + new_json + " so safe to remove " + file)
                    print( legacy_file + " -> " + new_file)
                    os.remove(legacy_file)
        if os.path.exists(os.path.join(folder_path,"info.json")):
            os.remove(os.path.join(folder_path,"info.json"))
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
                    print("File already exists: " + new_json + " so safe to remove " + file)
                    print( legacy_file + " -> " + new_file)
                    os.remove(legacy_file)
        if os.path.exists(os.path.join(folder_path,"info.json")):
            os.remove(os.path.join(folder_path,"info.json"))

def drop_table_users():
    if input("drop users table?[y/n]") == 'y':
        table_name_to_drop = "users"
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {table_name_to_drop}")
        conn.commit()
        conn.close()

def check_users():
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        users = set()
        cursor.execute("SELECT user_name,type FROM media")
        for row in cursor.fetchall():
            users.add((row[0],row[1]))
        cursor.execute("SELECT user_name,type FROM posts")
        for row in cursor.fetchall():
            users.add((row[0],row[1]))
        conn.close()
        for user,type_ in list(users):
            user_fs_base = os.path.join(config.fs_bases[type_],user)
            if not os.path.exists(user_fs_base):
                print(f"UID {user} no longer exsists in filesystem, try clean_user().")

def clean_user():
    id_ = input("id>>")
    if len(id_)<2:
        print("Not allowed.")
        return
    sql1 = f"DELETE FROM posts WHERE user_name = \"{id_}\""
    sql2 = f"DELETE FROM media WHERE user_name = \"{id_}\""
    sql3 = f"DELETE FROM users WHERE user_name = \"{id_}\""
    if input(f"{sql1}\n{sql2}\n{sql3}\nSure?[y/n]>>") == 'y':
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        cursor.execute(sql1)
        cursor.execute(sql2)
        cursor.execute(sql3)
        conn.commit()
        conn.close()

if __name__ == "__main__":
    check_users()
    choice = input("[1] remove_legacy_json()\n[2] drop_table_users()\n[3] clean_user()\n>>")
    if choice == '1':
        remove_legacy_json()
    elif choice == '2':
        drop_table_users()
    elif choice == '3':
        clean_user()