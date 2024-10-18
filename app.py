from flask import Flask, render_template, request, jsonify, send_file
from rembg import remove
from PIL import Image
import io
import base64
import cachetools
import threading
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=4)
cache = cachetools.TTLCache(maxsize=100, ttl=3600)
cache_lock = threading.Lock()

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
application = app

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image(input_image):
    try:
        if input_image.mode in ('RGBA', 'LA'):
            input_image = input_image.convert('RGBA')
        else:
            input_image = input_image.convert('RGB')

        output_image = remove(input_image)
        return output_image
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return None

def apply_background(image, background_color=None, background_image=None):
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    # Create a transparent base image
    base_image = Image.new('RGBA', image.size, (0, 0, 0, 0))
    
    # Extract the alpha channel from the original image
    _, _, _, alpha = image.split()
    
    # Create the new background
    if background_image:
        # Resize background image to match the dimensions of the input image
        background_image = background_image.resize(image.size, Image.LANCZOS)
        # Ensure background image is in RGBA mode
        if background_image.mode != 'RGBA':
            background_image = background_image.convert('RGBA')
        base_image = background_image
    elif background_color:
        if background_color.startswith('#'):
            background_color = tuple(int(background_color[i:i+2], 16) for i in (1, 3, 5)) + (255,)
        base_image = Image.new('RGBA', image.size, background_color)
    
    # Create a new image using the background
    result = Image.new('RGBA', image.size, (0, 0, 0, 0))
    result.paste(base_image, (0, 0))
    
    # Paste the original image using its alpha channel as mask
    result.paste(image, (0, 0), mask=alpha)
    
    return result

def compress_image(image, quality=85):
    buffer = io.BytesIO()
    if image.mode == 'RGBA':
        image.save(buffer, format='PNG', optimize=True)
    else:
        image.save(buffer, format='JPEG', quality=quality, optimize=True)
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
        return jsonify({'error': 'Invalid file'}), 400

    try:
        # Read file content once
        image_bytes = file.read()
        cache_key = hash(image_bytes)
        
        with cache_lock:
            if cache_key in cache:
                return jsonify({'image': cache[cache_key]})
        
        # Create BytesIO object from image bytes
        input_image = Image.open(io.BytesIO(image_bytes))
        
        future = executor.submit(process_image, input_image)
        output_image = future.result()
        
        if output_image is None:
            return jsonify({'error': 'Failed to process image'}), 500
        
        buffered = io.BytesIO()
        output_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        with cache_lock:
            cache[cache_key] = img_str
        
        return jsonify({'image': img_str})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/apply_background', methods=['POST'])
def apply_new_background():
    try:
        data = request.json
        if not data.get('image'):
            return jsonify({'error': 'No image provided'}), 400

        # Handle the base64 image string properly
        image_data = data['image']
        if ',' in image_data:  # Handle data URL format
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
        else:
            result = apply_background(image, background_color=background_color)
        
        compressed = compress_image(result)
        img_str = base64.b64encode(compressed).decode()
        
        return jsonify({'image': img_str})
    
    except Exception as e:
        print(f"Error in apply_background: {str(e)}")  # Add debugging
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_image():
    try:
        data = request.json
        if not data.get('image'):
            return jsonify({'error': 'No image provided'}), 400

        # Handle the base64 image string properly
        image_data = data['image']
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        
        if 'backgroundColor' in data or 'backgroundImage' in data:
            image = Image.open(io.BytesIO(image_bytes))
            background_color = data.get('backgroundColor')
            background_image_data = data.get('backgroundImage')
            
            if background_image_data:
                if ',' in background_image_data:
                    background_image_data = background_image_data.split(',')[1]
                background_bytes = base64.b64decode(background_image_data)
                background_image = Image.open(io.BytesIO(background_bytes))
                result = apply_background(image, background_image=background_image)
            else:
                result = apply_background(image, background_color=background_color)
            
            output = compress_image(result)
        else:
            output = image_bytes
        
        return send_file(
            io.BytesIO(output),
            mimetype='image/png',
            as_attachment=True,
            download_name='processed_image.png'
        )
    
    except Exception as e:
        print(f"Error in download: {str(e)}")  # Add debugging
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False)