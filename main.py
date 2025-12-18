import yt_dlp
from scenedetect import detect, ContentDetector, open_video
from scenedetect.scene_manager import save_images
import os
import json
import base64
import requests

def download_video():
    search_query = "super mario movie trailer"
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'video.%(ext)s',
        'quiet': True
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(f"ytsearch:{search_query}", download=True)
        video_filename = ydl.prepare_filename(result['entries'][0])
    
    print("Video downloaded successfully")
    return video_filename

def detect_scenes(video_path):
    print("Detecting scenes...")
    
    video = open_video(video_path)
    scene_list = detect(video_path, ContentDetector(threshold=27.0))
    
    print(f"Detected {len(scene_list)} scenes")
    
    os.makedirs('scenes', exist_ok=True)
    
    save_images(
        scene_list,
        video,
        num_images=1,
        output_dir='scenes'
    )
    
    return scene_list

def image_to_base64(image_path):
    """Convert image to base64 string"""
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def caption_with_ollama(image_path):
    """Generate caption using Ollama's moondream model"""
    image_b64 = image_to_base64(image_path)
    
    response = requests.post(
        'http://localhost:11434/api/generate',
        json={
            'model': 'moondream',
            'prompt': 'Describe this image in one sentence.',
            'images': [image_b64],
            'stream': False
        }
    )
    
    return response.json()['response']

def caption_scenes():
    """Generate captions for all scene images using Ollama"""
    
    # check if captions file exists, if so, skip
    if os.path.exists('scene_captions.json'):
        print("Captions file already exists, loading from disk...")
        with open('scene_captions.json', 'r') as f:
            return json.load(f)
    
    print("Generating captions using Ollama...")
    captions = {}
    
    # get all image files in scenes folder
    scene_files = sorted([f for f in os.listdir('scenes') if f.endswith(('.jpg', '.png'))])
    
    for i, scene_file in enumerate(scene_files, 1):
        image_path = os.path.join('scenes', scene_file)
        
        # create caption using Ollama
        caption = caption_with_ollama(image_path)
        
        # keep the scene number as key
        scene_num = str(i)
        captions[scene_num] = caption
        print(f"Scene {scene_num}: {caption}")
    
    # save to JSON
    with open('scene_captions.json', 'w') as f:
        json.dump(captions, f, indent=2)
    
    print(f"Saved captions to scene_captions.json")
    return captions

if __name__ == "__main__":
    video_file = download_video()
    print(f"Downloaded: {video_file}")
    
    scenes = detect_scenes(video_file)
    print(f"Scene images saved to 'scenes' folder")
    
    # create captions
    captions = caption_scenes()
    print(f"Total scenes captioned: {len(captions)}")