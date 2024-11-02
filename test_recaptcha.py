
import tensorflow as tf
from check_re import CaptchaPredictor
predictor = CaptchaPredictor('captcha.keras')

def predict( image_path):
    capfile = "captcha_0.png"
    
    solved_captcha = predictor.predict(image_path)
    print(f"Predicted text: {solved_captcha}")

# Usage
for i in range(10):
    print(predict("captcha_0.png")  )