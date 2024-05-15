import exifread
from moviepy.editor import VideoFileClip
import json
import subprocess
import os
from PIL import Image

def is_media(file_path):
    _, file_extension = os.path.splitext(file_path)
    return file_extension.lower() in (".jpeg", ".jpg", ".png")

def is_video(file_path):
    _, file_extension = os.path.splitext(file_path)
    return file_extension.lower() in (".mp4")

def get_photo_rotation(file_path):
    with open(file_path, 'rb') as img_file:
        exif_tags = exifread.process_file(img_file)
        orientation_key = 'Image Orientation'

        if orientation_key in exif_tags:
            orientation = exif_tags[orientation_key].values[0]
            return orientation

    return False

def is_photo_landscape(file_path):
    rotated = get_photo_rotation(file_path) in [5, 6, 7, 8]
        
    with Image.open(file_path) as img:
        width, height = img.size
        if rotated:
            return height > width or width == height
        else:
            return width > height or width == height

def get_video_rotation(file_path):
    try:
        result = subprocess.run(
            ["ffprobe", "-i", file_path, "-v", "quiet", 
             "-print_format", "json", "-show_streams"],
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT
        )
        video_metadata = json.loads(result.stdout)
        
        for stream in video_metadata.get('streams', []):
            if stream.get('codec_type') == 'video':
                for side_data in stream.get('side_data_list', []):
                    if side_data.get('side_data_type') == 'Display Matrix':
                        return side_data.get('rotation', 0)
        return 0
    except Exception as e:
        log(f"Error extracting metadata for {file_path}: {e}", "ERROR")
        return 0

def is_video_landscape(file_path):
    rotation = get_video_rotation(file_path)
    if rotation in [90, 270, -90, -270]:
        return False
    else:
        with VideoFileClip(file_path) as video:
            width, height = video.size
            return width > height

def is_landscape(file_path):
    if (is_video(file_path)):
        return is_video_landscape(file_path)
    else:
        return is_photo_landscape(file_path)