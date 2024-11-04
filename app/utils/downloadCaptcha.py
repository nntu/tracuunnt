
from datetime import datetime
from pathlib import Path
from PIL import Image
 
import ssl
import urllib.request
from io import BytesIO

from check_re import CaptchaPredictor
 


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
        timestamp = datetime.now().strftime('%d%m%Y_%H%M%S')
        captchar =  f"{tempdir}/captcha_{timestamp}.jpg"
        
        
        new_image.convert('RGB').save(captchar, "JPEG")  # Save as JPEG
        # Initialize the predictor
        predictor = CaptchaPredictor('captcha.keras')

        # Single image prediction
        text = predictor.predict(captchar)
                
        
    return text
    
# im = Image.open("Ba_b_do8mag_c6_big.png")
# rgb_im = im.convert('RGB')
# rgb_im.save('colors.jpg')

