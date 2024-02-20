#!/usr/bin/env python3
from flask import Flask, render_template, send_from_directory, url_for, request
import os
import random
import subprocess
from threading import Timer, Thread
import shutil
from datetime import datetime

app = Flask(__name__)
allFiles = []
cached_files = []
cache_depth = 10
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

        if (is_video(cached_file)):
            video_url=url_for('media', filename=cached_file)
            return render_template('index.html', video_url=video_url, filename=cached_file, timestamp=datetime.now().timestamp())
        else:
            image_url=url_for('media', filename=cached_file)
            return render_template('index.html', image_url=image_url, filename=cached_file, timestamp=datetime.now().timestamp())
        
    else:
        return render_template('index.html')

@app.route('/media/<path:filename>')
def media(filename):
    response = send_from_directory(cache_path, filename)

    if filename in cached_files:
        cached_files.remove(filename)
        caching_thread = Thread(target=new_cache)
        caching_thread.start()

    return response

@app.route('/stop/')
def stop():
    print("Stopping Chromium and Flask server")

    global browser_process
    if browser_process:
        browser_process.terminate()
        browser_process = None
    
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
