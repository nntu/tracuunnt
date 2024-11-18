import os
from pathlib import Path
import tensorflow as tf
from check_re import CaptchaPredictor
predictor = CaptchaPredictor()

def predict( image_path):
     
    
    solved_captcha = predictor.predict(image_path)
    print(f"Predicted text: {solved_captcha}")
    return solved_captcha

print(predict('E:/python3/Captcha_Tracuuthue/captcha/capcha_error/[UNK]e7wd.png'))