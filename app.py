from flask import Flask, render_template, request, jsonify, send_file
from rembg import remove
from PIL import Image
import io
import base64

app = Flask(__name__)
application = app

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/remove_background', methods=['POST'])
def remove_background():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    image_file = request.files['image']
    
    # Read the image file
    input_image = Image.open(image_file)
    
    # Remove the background
    output_image = remove(input_image)
    
    # Convert the output image to base64
    buffered = io.BytesIO()
    output_image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({'image': img_str})

from flask import Flask, render_template, request, jsonify, send_from_directory
from rembg import remove
from PIL import Image
import io
import base64

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/remove_background', methods=['POST'])
def remove_background():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    image_file = request.files['image']
    
    # Read the image file
    input_image = Image.open(image_file)
    
    # Remove the background
    output_image = remove(input_image)
    
    # Convert the output image to base64
    buffered = io.BytesIO()
    output_image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({'image': img_str})

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/service_worker.js')
def service_worker():
    return send_from_directory('', 'service_worker.js')

if __name__ == '__main__':
    app.run(debug=True)

if __name__ == '__main__':
    app.run(debug=True)