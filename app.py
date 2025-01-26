from flask import Flask, request, render_template, redirect, url_for, send_from_directory # type: ignore
import os
import torch
from PIL import Image
import torchvision.transforms as tfs # type: ignore
from torchvision.utils import save_image # type: ignore
from FFA import FFA  # Import your FFA model

# Flask app setup
app = Flask(__name__, static_folder='samples')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
app.config['MODEL_PATH'] = 'tti.pk'

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Load the model
gps = 3
blocks = 19
device = 'cuda' if torch.cuda.is_available() else 'cpu'
net = FFA(gps=gps, blocks=blocks).to(device)
net = torch.nn.DataParallel(net)

# Load model checkpoint
model_path = app.config['MODEL_PATH']
if not os.path.exists(model_path):
    raise FileNotFoundError(f"Model checkpoint not found at {model_path}")
checkpoint = torch.load(model_path, map_location=device)
net.load_state_dict(checkpoint['model'])
net.eval()


# Function to process images
def process_image(image_path, output_path):
    """Process a single image and save the output."""
    try:
        # Load and preprocess image
        haze_img = Image.open(image_path).convert("RGB")
        haze_tensor = tfs.Compose([
            tfs.ToTensor(),
            tfs.Normalize(mean=[0.64, 0.6, 0.58], std=[0.14, 0.15, 0.152])
        ])(haze_img).unsqueeze(0).to(device)

        # Generate prediction
        with torch.no_grad():
            pred = net(haze_tensor)

        # Save the output image
        pred_clamped = pred.clamp(0, 1).cpu()
        save_image(pred_clamped, output_path)
        return True, None
    except Exception as e:
        return False, str(e)


# Routes
@app.route('/')
def index():
    """Render the upload page."""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file uploads and return the processed image."""
    if 'file' not in request.files:
        return "No file uploaded", 400

    file = request.files['file']
    if file.filename == '':
        return "No file selected", 400

    # Save uploaded file
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], file.filename)
    file.save(input_path)

    # Process the image
    success, error = process_image(input_path, output_path)
    if not success:
        return f"Error processing image: {error}", 500

    # Return the processed image
    return send_from_directory(app.config['OUTPUT_FOLDER'], file.filename)




@app.route('/download/<filename>')
def download_file(filename):
    """Provide the processed image for download."""
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)


# Start the Flask app
if __name__ == '__main__':
    app.run(debug=True)
