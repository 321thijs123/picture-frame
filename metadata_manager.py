import json
from threading import Thread
from time import sleep

class MetadataManager:
    def __init__(self, metadata_path, log):
        self.metadata_changed = False
        self.metadata = {}
        self.metadata_path = metadata_path
        self.log = log
        
        metadata_thread = Thread(target=self.write_metadata)
        metadata_thread.start()
    
    def write_metadata(self):
        while True:
            if self.metadata_changed:
                self.log("Updating metadata file")
                self.metadata_changed = False

                with open(self.metadata_path, 'w') as file:
                    json.dump(self.metadata, file, indent=4)

            sleep(1)
    
    def add(self, filename, key, value):
        new_entry = {key: value}

        if filename in self.metadata:
            self.metadata[filename].update(new_entry)
        else:
            self.metadata[filename] = new_entry

        self.metadata_changed = True
    
    def get(self, key, default=False):
        return self.metadata.get(key, default)
