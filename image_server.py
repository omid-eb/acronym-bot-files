from flask import Flask, request, jsonify
from PIL import Image, ImageOps
import os
import requests
import threading
import signal

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    print("HEIC support enabled")
except ImportError:
    print("pillow-heif not installed, HEIC files may not work")

app = Flask(__name__)

LOGO_PATH = "/root/acronym_bot/Logo.png"
DOCKER_PATH = "/acronym_files"
HOST_PATH = "/root/acronym_bot"

def fix_path(p):
    return p.replace(DOCKER_PATH, HOST_PATH)

def open_image(path):
    img = Image.open(path).convert("RGB")
    return img

def add_logo_to_cover(cover_path, output_path, rotation='none'):
    cover = open_image(cover_path)
    cover = ImageOps.exif_transpose(cover)

    if rotation == 'cw':
        cover = cover.rotate(-90, expand=True)
    elif rotation == 'ccw':
        cover = cover.rotate(90, expand=True)
    elif rotation == '180':
        cover = cover.rotate(180, expand=True)

    cw, ch = cover.size
    banner_h = max(int(ch * 0.13), 80)
    logo = Image.open(LOGO_PATH).convert("RGBA")
    logo_aspect = logo.width / logo.height
    logo_w = min(int(banner_h * logo_aspect), cw)
    logo_h = int(logo_w / logo_aspect)
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
    banner = Image.new("RGB", (cw, banner_h), color=(21, 101, 192))
    paste_x = (cw - logo_w) // 2
    paste_y = (banner_h - logo_h) // 2
    banner.paste(logo, (paste_x, paste_y), mask=logo.split()[3])
    result = Image.new("RGB", (cw, ch + banner_h), color=(255, 255, 255))
    result.paste(cover, (0, 0))
    result.paste(banner, (0, ch))
    result.save(output_path, format="JPEG", quality=95)
    return output_path

def process_other_image(img_path, output_path):
    img = open_image(img_path)
    img = ImageOps.exif_transpose(img)
    img.save(output_path, format="JPEG", quality=95)
    return output_path

@app.route('/process', methods=['POST'])
def process_images():
    try:
        data = request.json
        output_dir = fix_path(data['output_dir'])
        cover_path = fix_path(data['cover_path'])
        other_paths = [fix_path(p) for p in data.get('other_paths', [])]
        cover_rotation = data.get('cover_rotation', 'none')
        os.makedirs(output_dir, exist_ok=True)
        cover_out = os.path.join(output_dir, 'cover.jpg')
        add_logo_to_cover(cover_path, cover_out, cover_rotation)
        other_outs = []
        for i, path in enumerate(other_paths):
            out_path = os.path.join(output_dir, 'photo_' + str(i + 1) + '.jpg')
            process_other_image(path, out_path)
            other_outs.append(out_path)
        return jsonify({'success': True, 'cover': cover_out, 'others': other_outs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/send_photo', methods=['POST'])
def send_photo():
    try:
        data = request.json
        file_path = fix_path(data['file_path'])
        caption = data['caption']
        chat_id = data['chat_id']
        bot_token = data['bot_token']
        with open(file_path, 'rb') as f:
            response = requests.post(
                'https://api.telegram.org/bot' + bot_token + '/sendPhoto',
                data={'chat_id': chat_id, 'caption': caption},
                files={'photo': f}
            )
        return jsonify({'success': True, 'result': response.json()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/reload', methods=['POST'])
def reload():
    def kill_me():
        import time
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)
    threading.Thread(target=kill_me).start()
    return jsonify({'success': True, 'message': 'reloading'})

if __name__ == '__main__':
    print("Image processing server running on http://localhost:5679")
    app.run(host='0.0.0.0', port=5679, debug=False)
