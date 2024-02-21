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

app = Flask(__name__)
allFiles = []
cached_files = []
cache_depth = 10
active_file = None
media_path = "/mnt/diskstation/Photos/"
cache_path = "cache/"
browser_process = None

def is_media(file_path):
    _, file_extension = os.path.splitext(file_path)
    return file_extension.lower() in (".jpeg", ".jpg", ".png", ".mp4")

def is_video(file_path):
    _, file_extension = os.path.splitext(file_path)
    return file_extension.lower() in (".mp4")

def index_files():
    for path, subdirs, files in os.walk(media_path):
        for name in files:
            if is_media(name):
                folder = path.replace(media_path,"")
                allFiles.append(os.path.join(folder, name))
    
    print("Indexed " + str(len(allFiles)) + " files")

def get_date(file_path):
    with open(os.path.join(cache_path, file_path), 'rb') as fh:
        exif_tags = exifread.process_file(fh, stop_tag="EXIF DateTimeOriginal")

        if "EXIF DateTimeOriginal" in exif_tags:
            return exif_tags["EXIF DateTimeOriginal"]

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

def new_cache():
    global cached_files

    picked = random.choice(allFiles)
    
    print ("Caching: " + picked)

    source = os.path.join(media_path, picked)
    destination = os.path.join(cache_path, picked)

    destination_dir = os.path.dirname(destination)

    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)

    try:
        shutil.copy2(source, destination)
        cached_files.append(picked)
        print("Cached: " + picked + " - Cache size: " + str(len(cached_files)))
    except:
        print("Caching failed: " + picked)
        new_cache()
        return

@app.route('/')
def index():
    if (cached_files):
        cached_file = cached_files[0]

        [lat, lon] = get_coordinates(cached_file)
        location_name = get_location_name(lat, lon)

        if (is_video(cached_file)):
            video_url=url_for('media', filename=cached_file)
            return render_template('index.html', video_url=video_url, filename=cached_file, timestamp=datetime.now().timestamp(), datetaken=get_date(cached_file), location=location_name)
        else:
            image_url=url_for('media', filename=cached_file)
            return render_template('index.html', image_url=image_url, filename=cached_file, timestamp=datetime.now().timestamp(), datetaken=get_date(cached_file), location=location_name)
        
    else:
        return render_template('index.html')

@app.route('/media/<path:filename>')
def media(filename):
    global active_file

    if filename != active_file and active_file:
        print("Removing from cache: " + active_file)
        os.remove(os.path.join(cache_path, active_file))

    active_file = filename

    response = send_from_directory(cache_path, filename)

    if filename in cached_files:
        cached_files.remove(filename)
        caching_thread = Thread(target=new_cache)
        caching_thread.start()

    return response

@app.route('/stop/')
def stop():
    global active_file

    print("Stopping Chromium and Flask server")

    print("Removing from cache: " + active_file)
    os.remove(os.path.join(cache_path, active_file))

    for filename in cached_files:
        print("Removing from cache: " + filename)
        os.remove(os.path.join(cache_path, filename))

    print("Closing browser")
    global browser_process
    if browser_process:
        browser_process.terminate()
        browser_process = None
    
    print("Stopping server")
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

    return "Stopping..."

def open_browser():
    global browser_process
    url = 'http://localhost:5000'
    browser_process = subprocess.Popen(['chromium-browser', '--kiosk', '--incognito', url])

if __name__ == '__main__':
    index_files()
    
    new_cache()

    for i in range(cache_depth - 1):
        caching_thread = Thread(target=new_cache)
        caching_thread.start()

    Timer(1, open_browser).start()

    app.run(host='0.0.0.0', port=5000)
