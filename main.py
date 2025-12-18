import yt_dlp
from scenedetect import detect, ContentDetector, open_video
from scenedetect.scene_manager import save_images
from PIL import Image
import os
import json
import base64
import requests
from rapidfuzz import fuzz
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
import math

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
    
    # Load existing captions if available
    if os.path.exists('scene_captions.json'):
        print("Loading existing captions...")
        with open('scene_captions.json', 'r') as f:
            captions = json.load(f)
    else:
        captions = {}
    
    print("Generating captions using Ollama...")
    
    # get all image files in scenes folder
    scene_files = sorted([f for f in os.listdir('scenes') if f.endswith(('.jpg', '.png'))])
    
    for i, scene_file in enumerate(scene_files, 1):
        scene_num = str(i)
        
        # Skip if already captioned
        if scene_num in captions:
            print(f"Scene {scene_num}: Already captioned, skipping")
            continue
            
        image_path = os.path.join('scenes', scene_file)
        
        # create caption using Ollama
        caption = caption_with_ollama(image_path)
        
        captions[scene_num] = caption
        print(f"Scene {scene_num}: {caption}")
        
        # Save after each caption (in case of crash)
        with open('scene_captions.json', 'w') as f:
            json.dump(captions, f, indent=2)
    
    print(f"Saved captions to scene_captions.json")
    return captions

def extract_words_from_captions(captions):
    """Extract unique words from all captions for autocomplete"""
    words = set()
    for caption in captions.values():
        # Split by spaces and common punctuation
        caption_words = caption.lower().replace(',', ' ').replace('.', ' ').split()
        words.update(caption_words)
    return sorted(list(words))

def search_scenes_fuzzy(captions, search_term, threshold=70):
    """Search scenes using fuzzy matching"""
    matching_scenes = []
    
    for scene_num, caption in captions.items():
        # Check if search term fuzzy matches any word in caption
        caption_lower = caption.lower()
        search_lower = search_term.lower()
        
        # Simple word matching with fuzzy
        for word in caption_lower.split():
            ratio = fuzz.ratio(search_lower, word)
            if ratio >= threshold:
                matching_scenes.append(scene_num)
                break
    
    return matching_scenes

def create_collage(scene_numbers, output_path='collage.png'):
    """Create a collage from scene images"""
    if not scene_numbers:
        print("No scenes found to create collage")
        return
    
    # Load all images
    images = []
    scene_files = sorted([f for f in os.listdir('scenes') if f.endswith(('.jpg', '.png'))])
    
    for scene_num in scene_numbers:
        idx = int(scene_num) - 1
        if idx < len(scene_files):
            img_path = os.path.join('scenes', scene_files[idx])
            images.append(Image.open(img_path))
    
    if not images:
        print("No valid images found")
        return
    
    # Calculate grid size
    num_images = len(images)
    cols = math.ceil(math.sqrt(num_images))
    rows = math.ceil(num_images / cols)
    
    # Get dimensions (assuming all images same size)
    img_width, img_height = images[0].size
    
    # Create collage
    collage_width = cols * img_width
    collage_height = rows * img_height
    collage = Image.new('RGB', (collage_width, collage_height), color='black')
    
    # Paste images
    for idx, img in enumerate(images):
        row = idx // cols
        col = idx % cols
        x = col * img_width
        y = row * img_height
        collage.paste(img, (x, y))
    
    collage.save(output_path)
    print(f"Collage saved to {output_path}")
    
    # Display the collage
    collage.show()

def main():
    # Download and process video if needed
    if not os.path.exists('video.mp4'):
        video_file = download_video()
        print(f"Downloaded: {video_file}")
    else:
        print("Video already exists, skipping download")
        video_file = 'video.mp4'
    
    # Detect scenes if not already done
    if not os.path.exists('scenes') or len(os.listdir('scenes')) == 0:
        scenes = detect_scenes(video_file)
        print(f"Scene images saved to 'scenes' folder")
    else:
        print("Scenes already detected, skipping scene detection")
    
    # Create captions
    captions = caption_scenes()
    print(f"Total scenes captioned: {len(captions)}")
    
    # Extract words for autocomplete
    words = extract_words_from_captions(captions)
    word_completer = WordCompleter(words, ignore_case=True)
    
    # Search loop
    while True:
        print("\n" + "="*50)
        search_term = prompt("Search the video using a word (or 'quit' to exit): ", 
                            completer=word_completer)
        
        if search_term.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        if not search_term.strip():
            continue
        
        # Search with fuzzy matching
        matching_scenes = search_scenes_fuzzy(captions, search_term, threshold=70)
        
        if matching_scenes:
            print(f"\nFound {len(matching_scenes)} matching scene(s):")
            for scene_num in matching_scenes:
                print(f"  Scene {scene_num}: {captions[scene_num]}")
            
            # Create and display collage
            create_collage(matching_scenes)
        else:
            print(f"No scenes found matching '{search_term}'")

if __name__ == "__main__":
    main()