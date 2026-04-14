from flask import Flask, render_template, request, jsonify, send_file
from rembg import remove, new_session
from PIL import Image, ImageEnhance, ImageFilter
import io
import base64
import cachetools
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import hashlib

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=4)
cache = cachetools.TTLCache(maxsize=200, ttl=7200)
cache_lock = threading.Lock()

# Initialize rembg session once (avoids re-loading model on each request)
_session = None
_session_lock = threading.Lock()

app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB limit
application = app

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff', 'gif'}

def get_session():
    global _session
    with _session_lock:
        if _session is None:
            _session = new_session("u2net")
    return _session

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image(input_image, model="u2net"):
    try:
        if input_image.mode in ('RGBA', 'LA'):
            input_image = input_image.convert('RGBA')
        else:
            input_image = input_image.convert('RGB')

        session = get_session()
        output_image = remove(input_image, session=session)
        return output_image
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return None

def apply_background(image, background_color=None, background_image=None):
    if image.mode != 'RGBA':
        image = image.convert('RGBA')

    if background_image:
        background_image = background_image.resize(image.size, Image.LANCZOS)
        if background_image.mode != 'RGBA':
            background_image = background_image.convert('RGBA')
        result = Image.new('RGBA', image.size, (0, 0, 0, 0))
        result.paste(background_image, (0, 0))
        result.paste(image, (0, 0), mask=image.split()[3])
    elif background_color:
        if isinstance(background_color, str) and background_color.startswith('#'):
            r = int(background_color[1:3], 16)
            g = int(background_color[3:5], 16)
            b = int(background_color[5:7], 16)
            background_color = (r, g, b, 255)
        result = Image.new('RGBA', image.size, background_color)
        result.paste(image, (0, 0), mask=image.split()[3])
    else:
        result = image

    return result

def compress_image(image, output_format='PNG', quality=90):
    buffer = io.BytesIO()
    if output_format.upper() == 'PNG':
        image.save(buffer, format='PNG', optimize=True)
    elif output_format.upper() in ('JPG', 'JPEG'):
        if image.mode == 'RGBA':
            # Flatten alpha on white background for JPG
            bg = Image.new('RGB', image.size, (255, 255, 255))
            bg.paste(image, mask=image.split()[3])
            image = bg
        image.save(buffer, format='JPEG', quality=quality, optimize=True)
    elif output_format.upper() == 'WEBP':
        image.save(buffer, format='WEBP', quality=quality, lossless=(image.mode == 'RGBA'))
    else:
        image.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/remove_background', methods=['POST'])
def remove_background():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    file = request.files['image']

    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Supported: PNG, JPG, JPEG, WEBP, BMP, TIFF, GIF'}), 400

    try:
        image_bytes = file.read()
        cache_key = hashlib.md5(image_bytes).hexdigest()

        with cache_lock:
            if cache_key in cache:
                return jsonify({'image': cache[cache_key], 'cached': True})

        input_image = Image.open(io.BytesIO(image_bytes))
        original_size = input_image.size

        future = executor.submit(process_image, input_image)
        output_image = future.result(timeout=60)

        if output_image is None:
            return jsonify({'error': 'Failed to process image. Please try again.'}), 500

        buffered = io.BytesIO()
        output_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        with cache_lock:
            cache[cache_key] = img_str

        return jsonify({
            'image': img_str,
            'cached': False,
            'original_size': original_size,
            'output_size': output_image.size
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/apply_background', methods=['POST'])
def apply_new_background():
    try:
        data = request.json
        if not data.get('image'):
            return jsonify({'error': 'No image provided'}), 400

        image_data = data['image']
        if ',' in image_data:
            image_data = image_data.split(',')[1]

        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        background_color = data.get('backgroundColor')
        background_image_data = data.get('backgroundImage')

        if background_image_data:
            if ',' in background_image_data:
                background_image_data = background_image_data.split(',')[1]
            background_bytes = base64.b64decode(background_image_data)
            background_image = Image.open(io.BytesIO(background_bytes))
            result = apply_background(image, background_image=background_image)
        elif background_color:
            result = apply_background(image, background_color=background_color)
        else:
            result = image

        output_format = data.get('format', 'PNG')
        quality = data.get('quality', 90)
        compressed = compress_image(result, output_format, quality)
        img_str = base64.b64encode(compressed).decode()

        return jsonify({'image': img_str})

    except Exception as e:
        print(f"Error in apply_background: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_image():
    try:
        data = request.json
        if not data.get('image'):
            return jsonify({'error': 'No image provided'}), 400

        image_data = data['image']
        if ',' in image_data:
            image_data = image_data.split(',')[1]

        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        output_format = data.get('format', 'PNG').upper()
        quality = int(data.get('quality', 90))
        filename = data.get('filename', 'raydex-removed-bg')

        background_color = data.get('backgroundColor')
        background_image_data = data.get('backgroundImage')

        if background_color or background_image_data:
            if background_image_data:
                if ',' in background_image_data:
                    background_image_data = background_image_data.split(',')[1]
                bg_bytes = base64.b64decode(background_image_data)
                bg_image = Image.open(io.BytesIO(bg_bytes))
                image = apply_background(image, background_image=bg_image)
            elif background_color:
                image = apply_background(image, background_color=background_color)

        output = compress_image(image, output_format, quality)

        mime_map = {
            'PNG': 'image/png',
            'JPG': 'image/jpeg',
            'JPEG': 'image/jpeg',
            'WEBP': 'image/webp'
        }
        mime = mime_map.get(output_format, 'image/png')
        ext = output_format.lower() if output_format != 'JPG' else 'jpg'

        return send_file(
            io.BytesIO(output),
            mimetype=mime,
            as_attachment=True,
            download_name=f'{filename}.{ext}'
        )

    except Exception as e:
        print(f"Error in download: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Pre-warm the model
    get_session()
    app.run(debug=False, host='0.0.0.0', port=5000)
