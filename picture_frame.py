#!/usr/bin/env python3
from flask import Flask, render_template, send_from_directory, url_for, request
import os
import random
import subprocess
from threading import Timer, Thread
import shutil
from datetime import datetime
import exifread
from geopy.geocoders import Nominatim
import json
from PIL import Image
from moviepy.editor import VideoFileClip
from time import sleep
from datetime import datetime, timedelta
from multiprocessing import Process

from cache_manager import cache_manager
from media_tools import is_video, is_media

def log(message, logtype="INFO"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    formatted = "[{}] [{}] {}".format(logtype, now, message)
    
    print(formatted)

    with open("log.txt", "a") as myfile:
        myfile.write(formatted + "\n")

log("--- Starting ---")

app = Flask(__name__)
active_file = None
browser_process = None
metadata_changed = False
metadata = {}

with open("config.json") as file:
    config = json.load(file)

    media_path = config["media"]["path"]
    show_portrait = config["media"]["portrait"]
    show_landscape = config["media"]["landscape"]
    cache_path = config["cache"]["path"]
    cache_depth = config["cache"]["depth"]
    metadata_path = config["metadata"]["path"]
    browserdata_path = config["browserdata"]["path"]
    pos_x = config["position"]["x"]
    pos_y = config["position"]["y"]
    port = config["port"]
    autorefresh = config["autorefresh"]["enable"]
    refreshtime = datetime.strptime(config["autorefresh"]["time"], "%H:%M:%S").time()

log("Config loaded")

def runServer():
    try:
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        log(f"Server terminated due to an exception: {e}", "ERROR")
    finally:
        log("Server process is exiting", "INFO")

server = Process(target=runServer)

def index_files():
    global metadata

    all_files = []

    num_excluded = 0
    for path, subdirs, files in os.walk(media_path):
        for name in files:
            if is_media(name):
                folder = path.replace(media_path,"")
                file_path = os.path.join(folder, name)

                exclude = metadata.get(file_path, {}).get("exclude")
                landscape = metadata.get(file_path, {}).get("landscape")

                orientation_ok = (show_landscape and landscape) or (show_portrait and not landscape) or not landscape

                if not exclude and orientation_ok:
                    all_files.append(file_path)
                else:
                    num_excluded += 1

    log("Indexed " + str(len(all_files)) + " files")
    log("Excluded: " + str(num_excluded) + " file(s) from indexing")

    return all_files

def get_date(file_path):
    full_path = os.path.join(cache_path, file_path)

    if is_video(file_path):
        try:
            cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 
                   'format_tags=creation_time', '-of', 'default=noprint_wrappers=1:nokey=1', full_path]
            creation_time = subprocess.check_output(cmd).strip().decode('utf-8')
            dt = datetime.fromisoformat(creation_time.rstrip("Z"))
            return dt.strftime("%d-%m-%Y %H:%M:%S")
        except Exception as e:
            log(f"Error reading video metadata: {e}", "ERROR")
    else:
        with open(full_path, 'rb') as fh:
            exif_tags = exifread.process_file(fh, stop_tag="EXIF DateTimeOriginal")

            if "EXIF DateTimeOriginal" in exif_tags:
                date_str = str(exif_tags["EXIF DateTimeOriginal"])
                formatted_date = date_str[8:10] + "/" + date_str[5:7] + "/" + date_str[0:4] + date_str[10:]
                return formatted_date

    return "Unknown"

def get_coordinates(file_path):
    def _to_degrees(value):
        d, m, s = value.values
        return d.num / d.den + (m.num / m.den / 60.0) + (s.num / s.den / 3600.0)

    with open(os.path.join(cache_path, file_path), 'rb') as fh:
        exif_tags = exifread.process_file(fh)

        if 'GPS GPSLatitude' in exif_tags and 'GPS GPSLongitude' in exif_tags:
            latitude = exif_tags['GPS GPSLatitude']
            latitude_ref = exif_tags['GPS GPSLatitudeRef'].values
            longitude = exif_tags['GPS GPSLongitude']
            longitude_ref = exif_tags['GPS GPSLongitudeRef'].values

            lat = _to_degrees(latitude)
            if latitude_ref != 'N':
                lat = -lat

            lon = _to_degrees(longitude)
            if longitude_ref != 'E':
                lon = -lon

            return lat, lon
        else:
            return None, None

def get_location_name(lat, lon):
    if lat and lon:
        try:
            geo_loc = Nominatim(user_agent="GetLoc")
            locname = geo_loc.reverse((lat, lon))
            return locname.address
        except:
            return str(lat) + ", " + str(lon)

    return None

def add_metadata(filename, key, value):
    global metadata_changed, metadata

    new_entry = {key: value}

    if filename in metadata:
        metadata[filename].update(new_entry)
    else:
        metadata[filename] = new_entry

    metadata_changed = True

def write_metadata():
    global metadata_changed, metadata

    while True:
        if metadata_changed:
            log("Updating metadata file")
            metadata_changed = False

            with open(metadata_path, 'w') as file:
                json.dump(metadata, file, indent=4)

        sleep(1)

@app.route('/')
def index():
    cached_file = cache.get()

    if (cached_file):
        [lat, lon] = get_coordinates(cached_file)
        location_name = get_location_name(lat, lon)

        if (is_video(cached_file)):
            video_url=url_for('media', filename=cached_file)
            return render_template('index.html', video_url=video_url, filename=cached_file, timestamp=datetime.now().timestamp(), datetaken=get_date(cached_file), location=location_name)
        else:
            image_url=url_for('media', filename=cached_file)
            return render_template('index.html', image_url=image_url, filename=cached_file, timestamp=datetime.now().timestamp(), datetaken=get_date(cached_file), location=location_name)
        
    else:
        cache.fill()
        return render_template('index.html')

@app.route('/media/<path:filename>')
def media(filename):
    global active_file

    if filename != active_file and active_file:
        log("Removing from cache: " + active_file)
        os.remove(os.path.join(cache_path, active_file))

    active_file = filename

    response = send_from_directory(cache_path, filename)

    return response

@app.route('/exclude/<path:filename>')
def exclude(filename):
    add_metadata(filename, "exclude", True)

    try:
        cache.all_files.remove(filename)
        log("Removing from index: " + filename)
    except ValueError:
        log("Removal from index failed: " + filename + " not found in index")

    return index()

@app.route('/stop/')
def stop():
    global active_file

    log("Stopping Chromium and Flask server")

    log("Removing from cache: " + active_file)
    os.remove(os.path.join(cache_path, active_file))

    cache.clean()

    global browser_process
    log("Closing browser")
    try:
        browser_process.terminate()
    except Exception as error:
        log(error, "WARN")

    global server
    try:
        log("Stopping server")
        server.terminate()
    except Exception as error:
        log(error, "WARN")

    return "Stopping..."

def open_browser():
    global browser_process
    url = 'http://localhost:' + str(port)
    browser_process = subprocess.Popen(['chromium-browser', '--kiosk', '--incognito','--user-data-dir=' + browserdata_path, "--window-position=" + str(pos_x) + "," + str(pos_y), url])

    if (autorefresh):
        setNextRefresh()

def setNextRefresh():
    now=datetime.today()
    
    target=now.replace(hour=refreshtime.hour, minute=refreshtime.minute, second=refreshtime.second, microsecond=0)

    if target < now:
        target = target + timedelta(days=1)

    delta_t=target-now

    secs=delta_t.total_seconds()
    Timer(secs, open_browser).start()

if __name__ == '__main__':
    metadata_thread = Thread(target=write_metadata)
    metadata_thread.start()

    all_files = index_files()

    cache = cache_manager(cache_depth, show_landscape, show_portrait, media_path, cache_path, all_files, log, add_metadata)
    cache.new_cache()

    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as file:
            metadata = json.load(file)

    # cache.fill()

    Timer(1, open_browser).start()

    server.start()
    server.join()
