from PIL import Image
import time, os, re
import subprocess
import signal
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
    # cmd = f"ffmpeg -i {video_path} -ss 00:00:00.000 -vframes 1 {thumbnail_path}"
    cmd = [
        "ffmpeg",
        "-i",
        video_path,
        "-ss",
        "00:00:00.000",
        "-vframes",
        "1",
        thumbnail_path,
    ]
    cmd = [str(x) for x in cmd]
    run_and_monitor_command(
        cmd,
        target_string="",
        quiet=True,
    )


def create_thumbnail(path, thumbnail_size=config.thubnail_size):
    config.cache_path = os.path.expanduser(config.cache_path)
    if not os.path.exists(config.cache_path):
        os.makedirs(config.cache_path)
    thumbnail_path = md5(path.encode()).hexdigest() + f"_{thumbnail_size}.jpg"
    thumbnail_path = os.path.join(config.cache_path, thumbnail_path)
    if os.path.exists(thumbnail_path):
        # print("Thumbnail exists:", thumbnail_path)
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
                    current_url, full = download_jobs.pop()
                    print(f"Downloading {current_url}")
                else:
                    time.sleep(1)
                    continue
            name = current_url.split("/")[-1].lower()
            if config.custom_gallery_dl_location:
                cmd = [os.path.expanduser(config.custom_gallery_dl_location)]
            else:
                cmd = ["gallery-dl"]
            if "bsky" in current_url:
                # cookies not avalible yet
                cmd += [
                    "-c",
                    "gallery-dl-config.json",
                    current_url,
                    "-D",
                    f"{config.fs_bases['bsky']}/{name}/",
                ]
                cmd = [str(x) for x in cmd]
                type = "bsky"
            else:
                if config.cookies_list["x"]:
                    cmd += [
                        "-c",
                        "gallery-dl-config.json",
                        "-C",
                        config.cookies_list["x"],
                        current_url,
                        "-D",
                        f"{config.fs_bases['x']}/{name}/",
                    ]
                    cmd = [str(x) for x in cmd]
                else:
                    cmd += [
                        "-c",
                        "gallery-dl-config.json",
                        current_url,
                        "-D",
                        f"{config.fs_bases['x']}/{name}/",
                    ]
                    cmd = [str(x) for x in cmd]
                type = "x"
            run_and_monitor_command(
                cmd,
                target_string="#" if not full else "",
                quiet=False,
            )
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
hashtag_pattern = re.compile(r"(^|[^/])#([^ ,#\!\n]+)")
# url_pattern = re.compile(r"https?://[\w\-_\./@\?\=\&]+")
url_pattern = re.compile(r"[\w\-\_\.]+/[\w\-\_\./@\?\=\&]+")


def embed_hyperlink(type, text_content):

    text_content = text_content.replace("http://", "").replace("https://", "")

    urls = url_pattern.findall(text_content)
    urls = [url for url in urls if "." in url and not url.endswith("..")]
    urls = list(set(urls))

    for url in urls:
        https_url = "https://" + url
        if https_url.endswith("."):
            https_url = https_url[:-1]
        url_display_text = https_url.replace("https://", "")
        if len(url_display_text) > 40:
            url_display_text = url_display_text[:40] + "..."
        # print("url:", url, https_url, url_display_text)
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
    text_content = text_content.replace("\n", "<br>")
    return text_content


def list_and(list1, list2):
    # Convert both lists to sets for efficient intersection
    set1 = set(list1)
    set2 = set(list2)

    # Find the intersection of the two sets
    intersection = set1.intersection(set2)

    # Convert the intersection back to a list and return it
    return list(intersection)


def run_and_monitor_command(command, target_string="", quiet=False, count=4):
    """
    Runs a system command, monitors its output line by line, and kills the command
    if a specific string is found in the output.

    Args:
        command: A list of strings representing the command to execute.
                 e.g., ["python", "my_script.py"]
        target_string: The string to search for in the command's output.
    """
    if not quiet:
        print(f"Running command: {' '.join(command)}")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,  # Important for line-by-line reading
    )

    def read_output(stdout, stderr, count):
        """Reads output from stdout and stderr and checks for the target string."""
        current_count = 0
        while True:
            line = stdout.readline()
            if line:
                if not quiet:
                    print(f"{line.strip()}")  # Print the output line
                if target_string and target_string in line:
                    current_count += 1
                    if current_count >= count:
                        if not quiet:
                            # print(f"Found target string '{target_string}' in output.")
                            print(f"END OF PROCESS")
                        time.sleep(0.3)
                        process.send_signal(signal.SIGINT)
                        break  # Exit the loop after killing the process
                else:
                    current_count = 0
            else:
                # Check for errors on stderr
                error_line = stderr.readline()
                if error_line and not quiet:
                    print(f"Error: {error_line.strip()}")
                else:
                    # If both stdout and stderr are empty, check if the process is still running
                    if process.poll() is not None:
                        break  # Process finished (either normally or killed)
                    time.sleep(0.1)  # Avoid busy-waiting

    # Start a thread to read the output
    output_thread = Thread(
        target=read_output, args=(process.stdout, process.stderr, count)
    )
    output_thread.daemon = (
        True  # Allow the main thread to exit even if this thread is running
    )
    output_thread.start()

    try:
        process.wait()  # Wait for the process to finish (or be killed)
        # print("Process finished.")
    except KeyboardInterrupt:
        print("Interrupted by user. Killing process...")
        process.send_signal(signal.SIGINT)
        process.wait()  # Ensure process is fully terminated
        print("Process killed.")
