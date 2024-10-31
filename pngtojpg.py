from PIL import Image

from pathlib import Path


# Path to the data directory
data_dir = Path("./captcha_images/")


for path in data_dir.glob("*.png"): 
    
    filename = path.name.replace(".png",".jpg")
    print(filename)
    image = Image.open(path)
    new_image = Image.new("RGBA", image.size, "WHITE") 
    new_image.paste(image, (0, 0), image)
    new_image.convert('RGB').save(f'./jpg/{filename}', "JPEG")
    

# image = Image.open('test.png')
# new_image = Image.new("RGBA", image.size, "WHITE") # Create a white rgba background
# new_image.paste(image, (0, 0), image)              # Paste the image on the background. Go to the links given below for details.
# new_image.convert('RGB').save('test.jpg', "JPEG")  # Save as JPEG