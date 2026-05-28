# Google Gemini Chatbot Starter

This project demonstrates a minimal Python chatbot using Google Gemini / Gemini model access.

## Setup

1. Create a Google Cloud service account with access to Vertex AI / Generative AI.
2. Download the JSON credentials file.
3. Set environment variables:
   - `GOOGLE_APPLICATION_CREDENTIALS` to the path of your credentials file
   - `GOOGLE_CLOUD_PROJECT` to your GCP project ID
   - optionally `GEMINI_MODEL` to the Gemini model name (default: `gemini-1.5-pro`)

You can also create a `.env` file in the project root with:

```env
GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\credentials.json
GOOGLE_CLOUD_PROJECT=your-project-id
GEMINI_MODEL=gemini-1.5-pro
```

## Install dependencies

```bash
pip install -r requirements.txt
```

## Run the chatbot

```bash
python chatbot.py
```

## Notes

- The code uses the Google Generative Language API package.
- If your environment or package names differ, update `chatbot.py` accordingly.
- Use a supported Gemini model name based on your Google Cloud access.
