import os
import re
import sys
import cv2
import math
import time
import json
import yt_dlp
import shutil
import base64
import logging
import requests
from PIL import Image
from rapidfuzz import fuzz
from prompt_toolkit import prompt
import google.generativeai as genai
from scenedetect.scene_manager import save_images
from prompt_toolkit.completion import WordCompleter
from scenedetect import detect, ContentDetector, open_video
from colorama import init as colorama_init, Fore, Style

colorama_init(autoreset=True)

class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        original_levelname = record.levelname
        color = self.LEVEL_COLORS.get(record.levelno, "")
        if color:
            record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname

_handler = logging.StreamHandler()
_handler.setFormatter(ColoredFormatter("%(asctime)s | %(levelname)s | %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    handlers=[_handler]
)

logger = logging.getLogger(__name__)

def UI_line(text: str, color: str = Fore.WHITE, style: str = "") -> None:
    sys.stdout.write(f"{style}{color}{text}{Style.RESET_ALL}\n")
    sys.stdout.flush()

def UI_input(prompt: str, color: str = Fore.WHITE, style: str = "") -> str:
    return input(f"{style}{color}{prompt}{Style.RESET_ALL}")

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
    
    logger.info("Video downloaded successfully: %s", video_filename)
    return video_filename

def detect_scenes(video_path):
    logger.info("Detecting scenes...")
    video = open_video(video_path)
    scene_list = detect(video_path, ContentDetector(threshold=27.0))
    logger.info("Detected %d scenes", len(scene_list))
    os.makedirs('scenes', exist_ok=True)
    save_images(scene_list, video, num_images=1, output_dir='scenes')
    return scene_list

def image_to_base64(image_path):
    # Convert image to base64 string
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def caption_with_ollama(image_path):
    # Generate caption using Ollama's moondream model
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
    # Generate captions for all scene images using Ollama
    if os.path.exists('scene_captions.json'):
        logger.info("Loading existing captions...")
        with open('scene_captions.json', 'r') as f:
            captions = json.load(f)
    else:
        captions = {}
    
    logger.info("Generating captions using Ollama...")
    
    # get all image files in scenes folder
    scene_files = sorted([f for f in os.listdir('scenes') if f.endswith(('.jpg', '.png'))])
    
    for i, scene_file in enumerate(scene_files, 1):
        scene_num = str(i)
        if scene_num in captions:
            logger.info(f"Scene {scene_num}: Already captioned, skipping")
            continue
            
        image_path = os.path.join('scenes', scene_file)
        caption = caption_with_ollama(image_path)
        captions[scene_num] = caption
        logger.info(f"Scene {scene_num}: {caption}")
        with open('scene_captions.json', 'w') as f:
            json.dump(captions, f, indent=2)
    logger.info("Saved captions to scene_captions.json")
    return captions

def extract_words_from_captions(captions):
    # Extract unique words from all captions for autocomplete
    words = set()
    for caption in captions.values():
        # Split by spaces and common punctuation
        caption_words = caption.lower().replace(',', ' ').replace('.', ' ').split()
        words.update(caption_words)
    return sorted(list(words))

def search_scenes_fuzzy(captions, search_term, threshold=70):
    # Search scenes using fuzzy matching
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

def get_next_collage_number():
    # Get the next available collage number
    existing_collages = [f for f in os.listdir('.') if f.startswith('collage_') and f.endswith('.png')]
    if not existing_collages:
        return 1
    
    # Extract numbers from existing collages
    numbers = []
    for filename in existing_collages:
        try:
            num = int(filename.replace('collage_', '').replace('.png', ''))
            numbers.append(num)
        except ValueError:
            continue
    
    return max(numbers) + 1 if numbers else 1

def create_collage(scene_numbers, output_path=None):
    # Create a collage from scene images
    if not scene_numbers:
        logger.error("No scenes found to create collage")
        return
    
    # Generate numbered filename if not provided
    if output_path is None:
        collage_num = get_next_collage_number()
        output_path = f'collage_{collage_num}.png'
    images = []
    scene_files = sorted([f for f in os.listdir('scenes') if f.endswith(('.jpg', '.png'))])
    
    for scene_num in scene_numbers:
        idx = int(scene_num) - 1
        if idx < len(scene_files):
            img_path = os.path.join('scenes', scene_files[idx])
            images.append(Image.open(img_path))
    
    if not images:
        logger.warning("No valid images found")
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
    logger.info(f"Collage saved to {output_path}")
    collage.show()

def search_with_image_model():
    # Search using image captions from moondream
    captions = caption_scenes()
    logger.info(f"Total scenes captioned: {len(captions)}")
    
    # Extract words for autocomplete
    words = extract_words_from_captions(captions)
    word_completer = WordCompleter(words, ignore_case=True)
    
    # Search loop
    while True:
        search_term = prompt("Search the video using a word (b = back, q = quit): ", completer=word_completer)
        if search_term.lower() == 'b':
            return 'back'
        if search_term.lower() == 'q':
            return 'quit'
        
        if not search_term.strip():
            continue
        
        # Search with fuzzy matching
        matching_scenes = search_scenes_fuzzy(captions, search_term, threshold=70)
        
        if matching_scenes:
            logger.info(f"\nFound {len(matching_scenes)} matching scene(s):")
            for scene_num in matching_scenes:
                logger.info(f"  Scene {scene_num}: {captions[scene_num]}")
            
            # Create and display collage
            create_collage(matching_scenes)
        else:
            logger.error(f"No scenes found matching '{search_term}'")

def search_with_video_model(video_path):
    # Search using Gemini video understanding model
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        logger.error("ERROR: GOOGLE_API_KEY not found in environment variables")
        return 'back'
    
    genai.configure(api_key=api_key)
    
    while True:
        user_query = UI_input("Using a video model. What would you like me to find in the video? (b = back, q = quit)\n> ")
        
        if user_query.strip().lower() == 'b':
            return 'back'
        if user_query.strip().lower() == 'q':
            return 'quit'
        
        if not user_query.strip():
            logger.error("No query provided")
            continue
        
        logger.info("Analyzing video with Gemini... (this may take a moment)")
        
        # Upload video to Gemini
        video_file = genai.upload_file(path=video_path)
        
        # Wait for processing
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)
        
        if video_file.state.name == "FAILED":
            logger.error(f"Video processing failed: {video_file.state.name}")
            continue
        
        logger.info("Video processed successfully!")
        
        # Create prompt for Gemini
        model = genai.GenerativeModel(model_name="gemini-2.5-flash-lite")
        
        prompt = f"""Analyze this video and find all the frames/moments that match this query: "{user_query}"

For each matching moment, provide:
1. The timestamp in seconds
2. A brief description of what's happening

Format your response as JSON:
{{
  "matches": [
    {{"timestamp": 5.2, "description": "..."}},
    {{"timestamp": 12.8, "description": "..."}}
  ]
}}"""
        
        response = model.generate_content([video_file, prompt])
        logger.info(f"\nGemini Response:")
        logger.info(response.text)
        
        try:
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                timestamps = [match['timestamp'] for match in result.get('matches', [])]
                
                if timestamps:
                    logger.info(f"\nFound {len(timestamps)} matching moments")
                    # Extract frames at those timestamps
                    extract_frames_from_video(video_path, timestamps)
                else:
                    logger.error("\nNo matching moments found")
            else:
                logger.error("\nCould not parse structured response, showing raw output above")
        except Exception as e:
            logger.error(f"\nNote: Could not extract frames automatically: {e}")
            logger.error("Showing response above for manual review")

def extract_frames_from_video(video_path, timestamps):
    # Extract frames at specific timestamps and create collage
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = []
    temp_dir = 'temp_frames'
    os.makedirs(temp_dir, exist_ok=True)
    
    for i, timestamp in enumerate(timestamps):
        frame_number = int(timestamp * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        
        if ret:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            temp_path = os.path.join(temp_dir, f'frame_{i}.jpg')
            img.save(temp_path)
            frames.append(img)
    
    cap.release()
    
    if not frames:
        logger.error("No frames could be extracted")
        return
    
    # Create collage
    num_images = len(frames)
    cols = math.ceil(math.sqrt(num_images))
    rows = math.ceil(num_images / cols)
    img_width, img_height = frames[0].size
    collage_width = cols * img_width
    collage_height = rows * img_height
    collage = Image.new('RGB', (collage_width, collage_height), color='black')
    
    for idx, img in enumerate(frames):
        row = idx // cols
        col = idx % cols
        x = col * img_width
        y = row * img_height
        collage.paste(img, (x, y))
    
    collage_num = get_next_collage_number()
    output_path = f'collage_{collage_num}.png'
    collage.save(output_path)
    logger.info(f"Collage saved to {output_path}")
    collage.show()
    
    # Cleanup temp directory
    shutil.rmtree(temp_dir)

def main():
    # Download and process video if needed
    if not os.path.exists('video.mp4'):
        video_file = download_video()
        logger.info(f"Downloaded: {video_file}")
    else:
        logger.info("Video already exists, skipping download")
        video_file = 'video.mp4'
    
    # Detect scenes if not already done
    if not os.path.exists('scenes') or len(os.listdir('scenes')) == 0:
        logger.info(f"Scene images saved to 'scenes' folder")
    else:
        logger.info("Scenes already detected, skipping scene detection")
    
    # Ask user which model to use
    while True:
        UI_line(Fore.CYAN + "\n" + "="*50 + Style.RESET_ALL)
        UI_line(Style.BRIGHT + "Choose search method:" + Style.RESET_ALL)
        UI_line(Fore.GREEN + "1. Image model (moondream - searches scene captions)" + Style.RESET_ALL)
        UI_line(Fore.YELLOW + "2. Video model (Gemini - analyzes entire video)" + Style.RESET_ALL)
        choice = UI_input(Fore.MAGENTA + "\nEnter your choice (1 or 2) (q = quit): " + Style.RESET_ALL).strip()
        
        if choice.lower() == 'q':
            return
        
        if choice == '1':
            action = search_with_image_model()
            if action == 'quit':
                return
        elif choice == '2':
            action = search_with_video_model(video_file)
            if action == 'quit':
                return
        else:
            logger.error("Invalid choice.")
            continue

if __name__ == "__main__":
    main()