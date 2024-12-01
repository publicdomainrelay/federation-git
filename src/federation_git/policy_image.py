# cat src/federation_git/policy_image.py | python -u src/federation_git/policy_image.py > policy_image.png
import sys
import zipfile
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Create a zip archive containing the internal files
def create_zip_of_files(file_name, file_contents):
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(file_name, file_contents)
    zip_buffer.seek(0)
    return zip_buffer.read()

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

def main():
    text_content = sys.stdin.read()

    # Create zip archive of internal files
    zip_data = create_zip_of_files(sys.argv[-1], text_content)

    # Create PNG with embedded zip and rendered text
    png_zip_data = create_png_with_zip(zip_data, text_content)

    # Write out image
    sys.stdout.buffer.write(png_zip_data)

if __name__ == "__main__":
    main()
