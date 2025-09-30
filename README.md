# QuoteGenerator

An AI-powered business quote generator that creates viral-ready motivational images using OpenAI GPT-4o for quote generation and Google Imagen for background imagery.

## Features

- **Smart Quote Generation**: Uses GPT-4o to create concise, actionable business advice quotes
- **Negative Prompting**: Automatically avoids repeating recent quotes by using the last 20 generated quotes as negative examples
- **Professional Image Creation**: Generates backgrounds using Google Imagen AI and overlays text with sophisticated typography
- **Persistent Storage**: Saves both raw and text-overlaid images to filesystem with SQLite database for metadata
- **REST API**: Simple HTTP endpoints for generation and retrieval
- **Comprehensive Logging**: Detailed logs for debugging and monitoring

## Prerequisites

- Python 3.8+
- OpenAI API key (for quote and image prompt generation)
- Google AI API key (for Imagen image generation)

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd QuoteGenerator
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   **Note on bcrypt compatibility:** This project uses `passlib` 1.7.4 for password hashing, which requires `bcrypt==4.0.1`. If you encounter errors like `AttributeError: module 'bcrypt' has no attribute '__about__'` or `ValueError: password cannot be longer than 72 bytes`, ensure you have the correct bcrypt version:
   ```bash
   pip install bcrypt==4.0.1
   ```

3. **Set up environment variables:**
   
   Create a `.env` file in the project root:
   ```bash
   OPENAI_API_KEY=your_openai_api_key_here
   GEMINI_API_KEY=your_google_ai_api_key_here
   ```
   
   **API Key Setup:**
   - **OpenAI API Key**: Get from https://platform.openai.com/api-keys
   - **Google AI API Key**: Get from https://ai.google.dev/ (used for Imagen image generation)

4. **Install system fonts (optional but recommended):**
   
   For better text rendering, install TrueType fonts:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install fonts-dejavu-core fonts-liberation
   
   # macOS (already includes good fonts)
   # Windows (already includes Arial and other fonts)
   ```

## Usage

### Starting the Server

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8101
```

Or run directly:
```bash
python app/main.py
```

The server will start at `http://localhost:8101`

### API Endpoints

#### Generate Quote Image
```bash
POST /quote-image
```

**Request Body (JSON):**
```json
{
  "seed": "productivity tips"  // Optional: theme/inspiration for the quote
}
```

**Response:** PNG image stream

**Example:**
```bash
curl -X POST http://localhost:8101/quote-image \
  -H "Content-Type: application/json" \
  -d '{"seed": "leadership"}' \
  --output quote.png
```

#### List All Quotes
```bash
GET /quotes
```

Returns all saved quotes with metadata including filenames, generation dates, and image prompts.

#### Get Specific Quote
```bash
GET /quotes/{id}
```

Returns details for a specific quote by ID.

### Testing

A test script is provided to generate and display a quote image:

```bash
# Make sure the server is running first
python tests/fetch_and_show.py
```

This will:
1. Request a new quote image from the API
2. Save it to a temporary file
3. Open it with your default image viewer

## Project Structure

```
QuoteGenerator/
├── app/
│   ├── main.py                 # FastAPI application and main logic
│   ├── database.py             # SQLite database operations
│   ├── filesystem.py           # Image storage utilities
│   └── image_prompt_generator.py # Image prompt generation helpers
├── tests/
│   └── fetch_and_show.py       # Test script
├── generated_images/           # Created automatically
│   ├── raw/                    # Raw generated backgrounds
│   └── overlay/                # Images with text overlay
├── quotes.db                   # SQLite database (created automatically)
├── requirements.txt            # Python dependencies
└── README.md
```

## How It Works

1. **Quote Generation**: GPT-4o creates a business advice quote, using the last 20 quotes as negative examples to ensure variety
2. **Image Prompt Creation**: Another GPT-4o call generates a prompt optimized for viral, shareable imagery
3. **Background Generation**: Google Imagen creates a professional background image
4. **Text Overlay**: Sophisticated text rendering with adaptive font sizing, wrapping, and semi-transparent backgrounds
5. **Persistence**: Both raw and final images are saved to filesystem, with metadata stored in SQLite

## Configuration

### Environment Variables

- `OPENAI_API_KEY` - Required for quote and prompt generation
- `GEMINI_API_KEY` / `IMAGEN_API_KEY` / `GOOGLE_API_KEY` - Required for image generation
- Database and image storage locations are configurable in the code

### Text Rendering

The system includes robust text overlay with:
- Adaptive font sizing based on image dimensions
- Automatic text wrapping
- Multiple font fallbacks
- Upscaling for small fonts
- Semi-transparent backgrounds for readability

## Troubleshooting

### Common Issues

1. **"OPENAI_API_KEY environment variable is required"**
   - Ensure your `.env` file contains a valid OpenAI API key

2. **"GEMINI_API_KEY or IMAGEN_API_KEY or GOOGLE_API_KEY environment variable is required"**
   - Add a Google AI API key to your `.env` file

3. **"google-genai package is required"**
   - Run `pip install -r requirements.txt` to install dependencies

4. **bcrypt/passlib compatibility errors**
   - **Error**: `AttributeError: module 'bcrypt' has no attribute '__about__'`
   - **Error**: `ValueError: password cannot be longer than 72 bytes`
   - **Cause**: `passlib` 1.7.4 is not fully compatible with `bcrypt` 5.x
   - **Solution**: Downgrade bcrypt to 4.0.1: `pip install bcrypt==4.0.1`
   - **Note**: Bcrypt has a built-in 72-byte password length limit. The application automatically truncates passwords at 72 bytes during both hashing and verification to comply with this limitation. This is secure and standard practice.

5. **Server won't start**
   - Check that port 8101 is available
   - Verify all dependencies are installed
   - Check the console output for detailed error messages

6. **Poor text quality**
   - Install TrueType fonts on your system (see Installation section)
   - The system will fall back to bitmap fonts if no TrueType fonts are found

### Logs

The application logs to both console and `app.log` file. Check the logs for detailed error information and API call details.

## Development

The codebase uses:
- **FastAPI** for the REST API
- **SQLite3** for lightweight database operations
- **Pillow (PIL)** for image processing
- **OpenAI SDK** for GPT-4o integration
- **Google GenAI** for Imagen integration

The negative prompting system automatically queries the database for recent quotes to maintain variety in generated content.
