import yt_dlp
from scenedetect import detect, ContentDetector, open_video
from scenedetect.scene_manager import save_images
import os

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
    
    # Open the video file as a video object
    video = open_video(video_path)
    
    # Detect scenes
    scene_list = detect(video_path, ContentDetector(threshold=27.0))
    
    print(f"Detected {len(scene_list)} scenes")
    
    # Create directory for scenes
    os.makedirs('scenes', exist_ok=True)
    
    # Save images - now with video object instead of string
    save_images(
        scene_list,
        video,
        num_images=1,
        output_dir='scenes'
    )
    
    return scene_list

if __name__ == "__main__":
    video_file = download_video()
    print(f"Downloaded: {video_file}")
    scenes = detect_scenes(video_file)
    print(f"Scene images saved to 'scenes' folder")