
import datetime
from pathlib import Path
from PIL import Image
 
import ssl
import urllib.request
from io import BytesIO
 


def downloadCaptcha(tempdir,url):
    # Set up SSL context to allow legacy TLS versions
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT

    # Use urllib to open the URL and read the content
    with urllib.request.urlopen(url, context=ctx) as response:        
        image_content = response.read()           
        im = Image.open(BytesIO(image_content))
        new_image = Image.new("RGBA", im.size, "WHITE") # Create a white rgba background
        new_image.paste(im, (0, 0), im)              # Paste the image on the background. Go to the links given below for details.
        captchar =  f"{tempdir}/captcha_{datetime.now().strftime("%Y-%m-%d_%I-%M-%S_%p")}.jpg"
        
        
        new_image.convert('RGB').save(captchar, "JPEG")  # Save as JPEG
    return captchar
    
# im = Image.open("Ba_b_do8mag_c6_big.png")
# rgb_im = im.convert('RGB')
# rgb_im.save('colors.jpg')

