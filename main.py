import yt_dlp
from scenedetect import detect, ContentDetector, open_video
from scenedetect.scene_manager import save_images
from transformers import AutoModelForCausalLM, AutoTokenizer
from PIL import Image
import os
import json

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

def caption_scenes():
    """Generate captions for all scene images using Moondream"""
    
    # check if captions file exists, if so, skip
    if os.path.exists('scene_captions.json'):
        print("Captions file already exists, loading from disk...")
        with open('scene_captions.json', 'r') as f:
            return json.load(f)
    
    print("Loading Moondream model...")
    model_id = "vikhyatk/moondream2"
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision="2024-08-26")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        trust_remote_code=True,
        revision="2024-08-26",
        attn_implementation=None
    )
    model.eval()
    
    print("Generating captions for scenes...")
    captions = {}
    
    # get all image files in scenes folder
    scene_files = sorted([f for f in os.listdir('scenes') if f.endswith(('.jpg', '.png'))])
    
    for i, scene_file in enumerate(scene_files, 1):
        image_path = os.path.join('scenes', scene_file)
        image = Image.open(image_path)
        
        # create caption
        caption = model.caption(image, tokenizer)["caption"]
        
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