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

def search_with_image_model():
    """Search using image captions from moondream"""
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

def search_with_video_model(video_path):
    """Search using Gemini video understanding model"""
    import google.generativeai as genai
    
    # Configure Gemini API
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not found in environment variables")
        print("Please set it with: export GOOGLE_API_KEY='your-api-key'")
        return
    
    genai.configure(api_key=api_key)
    
    print("\n" + "="*50)
    user_query = input("Using a video model. What would you like me to find in the video?\n> ")
    
    if not user_query.strip():
        print("No query provided")
        return
    
    print("\nAnalyzing video with Gemini... (this may take a moment)")
    
    # Upload video to Gemini
    video_file = genai.upload_file(path=video_path)
    
    # Wait for processing
    import time
    while video_file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(2)
        video_file = genai.get_file(video_file.name)
    
    if video_file.state.name == "FAILED":
        print(f"\nVideo processing failed: {video_file.state.name}")
        return
    
    print("\nVideo processed successfully!")
    
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
    
    print(f"\nGemini Response:")
    print(response.text)
    
    # Try to extract timestamps and create collage
    try:
        # Parse JSON response
        import re
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            timestamps = [match['timestamp'] for match in result.get('matches', [])]
            
            if timestamps:
                print(f"\nFound {len(timestamps)} matching moments")
                # Extract frames at those timestamps
                extract_frames_from_video(video_path, timestamps)
            else:
                print("\nNo matching moments found")
        else:
            print("\nCould not parse structured response, showing raw output above")
    except Exception as e:
        print(f"\nNote: Could not extract frames automatically: {e}")
        print("Showing response above for manual review")

def extract_frames_from_video(video_path, timestamps):
    """Extract frames at specific timestamps and create collage"""
    import cv2
    
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
            
            # Save temporarily
            temp_path = os.path.join(temp_dir, f'frame_{i}.jpg')
            img.save(temp_path)
            frames.append(img)
    
    cap.release()
    
    if not frames:
        print("No frames could be extracted")
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
    
    collage.save('collage.png')
    print(f"Collage saved to collage.png")
    collage.show()
    
    # Cleanup temp directory
    import shutil
    shutil.rmtree(temp_dir)

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
    
    # Ask user which model to use
    print("\n" + "="*50)
    print("Choose search method:")
    print("1. Image model (moondream - searches scene captions)")
    print("2. Video model (Gemini - analyzes entire video)")
    choice = input("\nEnter your choice (1 or 2): ").strip()
    
    if choice == '1':
        search_with_image_model()
    elif choice == '2':
        search_with_video_model(video_file)
    else:
        print("Invalid choice. Exiting.")
        return

if __name__ == "__main__":
    main()