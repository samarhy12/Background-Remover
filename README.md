# Raydex BG Remover

AI-powered background removal web app. Free, fast, no watermarks.

## Stack

- **Backend:** Python / Flask + rembg (U2-Net AI model) + Pillow
- **Frontend:** Vanilla HTML/CSS/JS — no framework dependency
- **Serving:** Gunicorn (production)

## Features

- Drag & drop or file picker upload
- Mobile: gallery pick or live camera capture
- Background editor: solid colours, gradients, custom image
- Download as PNG (transparent), WEBP, or JPG
- Clipboard copy
- Paste-from-clipboard support
- Server-side caching (TTL 2h)
- PWA manifest + full SEO

## Setup

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Production

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:application
```

## Supported formats

Upload: PNG, JPG, JPEG, WEBP, BMP, TIFF, GIF (up to 20MB)  
Download: PNG, WEBP, JPG
