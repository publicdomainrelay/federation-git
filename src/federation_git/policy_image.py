# cat ~/Documents/publicdomainrelay/gitatp/src/gitatp/update_profile.js | python -u src/federation_git/policy_image.py | tee policy_image.png | python -u src/federation_git/policy_image.py
import sys
import zipfile
from io import BytesIO

import magic
from PIL import Image, ImageDraw, ImageFont

# Create a zip archive containing the internal files
def create_zip_of_files(file_contents, file_name: str = "manifest"):
    zip_buffer = BytesIO()
    mimetype = magic.from_buffer(file_contents, mime=True)
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(mimetype, file_contents)
    zip_buffer.seek(0)
    return mimetype, zip_buffer.read()

def create_png_with_zip(zip_data, text_content):
    """
    Create a PNG image that contains rendered text and append zip data
    to create a polyglot PNG/zip file.

    Args:
        zip_data (bytes): The binary data of the zip file.
        text_content (str): The text content to render inside the PNG.

    Returns:
        bytes: The combined PNG and zip data.
    """
    # Font configuration
    font_size = 14
    try:
        # Attempt to use a monospaced font
        font = ImageFont.truetype("DejaVuSansMono.ttf", font_size)
    except IOError:
        # Fallback to default font
        font = ImageFont.load_default()

    # Calculate the size of the rendered text
    lines = text_content.split('\n')
    max_line_width = max(font.getbbox(line)[2] for line in lines)  # Use getbbox()[2] for width
    line_height = font.getbbox("A")[3]  # Use getbbox()[3] for height
    total_height = line_height * len(lines)

    # Create an image with a white background
    img = Image.new('RGB', (max_line_width + 20, total_height + 20), color='white')
    draw = ImageDraw.Draw(img)

    # Draw the text onto the image
    y_text = 10
    for line in lines:
        draw.text((10, y_text), line, font=font, fill='black')
        y_text += line_height

    # Save the image to a BytesIO object
    img_buffer = BytesIO()
    img.save(img_buffer, format='PNG')
    img_data = img_buffer.getvalue()
    img_buffer.close()

    # Combine the PNG image data and the zip data
    png_zip_data = img_data + zip_data

    return png_zip_data

def encode(input_data):
    text_content = input_data.decode()

    # Create zip archive of internal files
    mimetype, zip_data = create_zip_of_files(text_content)

    # Create PNG with embedded zip and rendered text
    png_zip_data = create_png_with_zip(zip_data, text_content)

    # Write out image
    return mimetype, png_zip_data

def decode(data):
    # Attempt to open the data as a zip file
    with zipfile.ZipFile(BytesIO(data)) as zipf:
        # Iterate through the files in the zip archive
        for file_info in zipf.infolist():
            with zipf.open(file_info) as file:
                # Output the contents of each file to stdout
                return file_info.orig_filename, file.read()

def main():
    input_data = sys.stdin.buffer.read()
    if input_data.startswith(b"\x89PNG"):
        mimetype, output_bytes = decode(input_data)
    else:
        mimetype, output_bytes = encode(input_data)
    print(f"{mimetype}", file=sys.stderr)
    sys.stdout.buffer.write(output_bytes)

if __name__ == "__main__":
    main()
