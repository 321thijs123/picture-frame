import os
import random
from media_tools import is_landscape, is_video, is_media
import shutil
from threading import Thread, Lock
from queue import Queue

class cache_manager:
    def __init__(self, cache_depth, show_landscape, show_portrait, media_path, cache_path, all_files, log, add_metadata):
        self.cache_depth = cache_depth
        self.show_landscape = show_landscape
        self.show_portrait = show_portrait
        self.media_path = media_path
        self.cache_path = cache_path
        self.all_files = all_files
        self.cached_files = Queue()
        self.lock = Lock()

        self.log = log
        self.add_metadata = add_metadata

    def new_cache(self):
        while True:
            with self.lock:
                if self.cached_files.qsize() >= self.cache_depth:
                    self.log("Cache already full", "WARN")
                    return
                
            if not self.all_files:
                self.log("No files available to cache", "WARN")
                return

            picked = random.choice(self.all_files)

            if self.cache_file(picked):
                return
    
    def cache_file(self, filename):
        self.log("Caching: " + filename)

        source = os.path.join(self.media_path, filename)
        destination = os.path.join(self.cache_path, filename)

        destination_dir = os.path.dirname(destination)

        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)

        try:
            shutil.copy2(source, destination)
            landscape = is_landscape(os.path.join(self.cache_path, filename))

            self.add_metadata(filename, "landscape", landscape)

            if (self.show_landscape and landscape) or (self.show_portrait and not landscape):
                with self.lock:
                    self.cached_files.put(filename)
                    self.log("Cached: " + filename + " - Cache size: " + str(self.cached_files.qsize()))
                return True
            else:
                self.log("Undesired orientation: " + filename)
                os.remove(os.path.join(self.cache_path, filename))
                with self.lock:
                    self.all_files.remove(filename)
                return False
        except Exception as error:
            self.log("Caching failed: " + filename + ", " + str(error), "ERROR")
            return False
    
    def new_cache_thread(self):
        caching_thread = Thread(target=self.new_cache)
        caching_thread.start()

    def fill(self):
        with self.lock:
            remaining = self.cache_depth - self.cached_files.qsize()
        
        for _ in range(remaining):
            self.new_cache_thread()

    def clean(self):
        with self.lock:
            while not self.cached_files.empty():
                filename = self.cached_files.get()
                self.log("Removing from cache folder: " + filename)
                os.remove(os.path.join(self.cache_path, filename))
    
    def get(self):
        with self.lock:
            empty = self.cached_files.empty()

        if not empty:
            with self.lock:    
                size = self.cached_files.qsize()
                file = self.cached_files.get()

            self.log("Retrieved from cache: " + file + " - Remaining cache size: " + str(size))
            self.fill()
            return file
        else:
            self.log("Cache empty: " + str(self.cached_files.qsize()), "WARN")
            return False
