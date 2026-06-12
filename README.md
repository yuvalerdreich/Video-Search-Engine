# Video Search Engine

A content-aware video search engine that lets you search inside a video using natural language. Supports two modes: a local **image model** (Moondream, runs fully offline) and a cloud **video model** (Google Gemini). Results are displayed as a visual collage of matching scenes.

## How It Works

### Image Model Mode (Moondream)
1. Downloads the "Super Mario Movie Trailer" from YouTube via `yt-dlp`
2. Detects scenes using `pyscenedetect` (ContentDetector, threshold 27.0)
3. Captions each scene image locally using the **Moondream** model running in Ollama
4. Saves captions to `scene_captions.json` — subsequent runs skip steps 1–3
5. User types a search word with **autocomplete** suggestions (powered by `prompt_toolkit`)
6. **Fuzzy matching** via `rapidfuzz` finds scenes where any caption word is ≥70% similar to the query
7. Matching scene images are assembled into a numbered collage (`collage_N.png`) and displayed

### Video Model Mode (Gemini)
1. Uploads the local video directly to the Gemini API
2. User enters a free-text query (not just a single word)
3. Gemini (`gemini-2.5-flash-lite`) analyzes the full video and returns matching timestamps with descriptions
4. Frames are extracted from the video at those timestamps using OpenCV
5. A collage of the extracted frames is saved and displayed

## Prerequisites

- Python 3.9+
- [Ollama](https://ollama.ai/) running locally with the Moondream model pulled:
  ```bash
  ollama pull moondream
  ```
- A Google API key with Gemini access (for video model mode)

## Setup

1. Clone the repository.

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file:
   ```env
   GOOGLE_API_KEY=your_google_api_key
   ```

4. Make sure Ollama is running:
   ```bash
   ollama serve
   ```

## Running

```bash
python main.py
```

On first run the program downloads the video, detects scenes, and generates captions (takes a few minutes). On subsequent runs it loads the cached `scene_captions.json` and goes straight to the search prompt.

## Usage

```
==================================================
Choose search method:
1. Image model (moondream - searches scene captions)
2. Video model (Gemini - analyzes entire video)

Enter your choice (1 or 2) (q = quit):
```

### Image model search
- Type a word — autocomplete suggests words from the captions as you type
- Press Enter to search; a collage of matching scenes opens and is saved as `collage_N.png`
- Type `b` to go back to the mode menu, `q` to quit

### Video model search
- Type any natural language query (e.g. "Mario jumping on enemies")
- Gemini identifies matching timestamps and frames are extracted into a collage
- Type `b` to go back, `q` to quit

## Project Structure

```
Video-Search-Engine/
├── main.py                 # All program logic
├── requirements.txt
├── .env                    # GOOGLE_API_KEY (not committed)
├── scene_captions.json     # Cached scene → caption mapping (auto-generated)
├── scenes/                 # Scene images extracted from the video (auto-generated)
├── video.mp4               # Downloaded video (auto-generated, gitignored)
└── collage_N.png           # Search result collages (auto-generated)
```

## Key Design Decisions

| Decision | Detail |
|---|---|
| **Caching** | `scene_captions.json` is written incrementally after each scene so progress is never lost on interruption |
| **Collage naming** | Each search creates a new `collage_N.png` so previous results are not overwritten |
| **Fuzzy threshold** | Word-level `fuzz.ratio` at 70% — finds typos and partial matches without too many false positives |
| **Scene detection threshold** | `ContentDetector(threshold=27.0)` tuned to yield ~50–80 meaningful scenes |
| **Gemini model** | `gemini-2.5-flash-lite` — free tier compatible, sufficient for trailer-length videos |

## Dependencies

| Library | Purpose |
|---|---|
| `yt-dlp` | YouTube video download |
| `scenedetect[opencv]` | Scene boundary detection |
| `opencv-python` | Frame extraction for Gemini timestamps |
| `moondream` | Local image-to-text captioning (via Ollama) |
| `rapidfuzz` | Fuzzy string matching for scene search |
| `prompt_toolkit` | Interactive autocomplete in the terminal |
| `google-generativeai` | Gemini video understanding API |
| `Pillow` | Collage image assembly |
| `python-dotenv` | `.env` loading |
