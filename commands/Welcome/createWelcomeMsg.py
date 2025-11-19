from PIL import Image, ImageDraw, ImageFont

### ------ WELCOME IMAGE CARD ------ ###
async def createWelcomeMsg(user, bg="./assets/bg.png", filename="./assets/welcome.png"):
    try:
        await user.avatar.with_static_format("png").with_size(256).save(filename)
        im1 = Image.open(bg)
        im2 = Image.open(filename)
    except Exception:
        im1 = Image.open(bg)
        im2 = Image.open("./assets/DefaultIcon.png")

    bigsize = (im2.size[0] * 3, im2.size[1] * 3)
    mask = Image.new('L', bigsize, 0)
    draw = ImageDraw.Draw(mask) 
    draw.ellipse((0, 0) + bigsize, fill=255)
    mask = mask.resize(im2.size, Image.LANCZOS)
    im2.putalpha(mask)

    im1.paste(im2, (384, 50), im2.convert("RGBA"))
    color = (255, 255, 255)
    font = ImageFont.truetype("./assets/ja-jp.ttf", 75)
    d1 = ImageDraw.Draw(im1)
    d1.text((325, 320), "Welcome", font=font, fill=color)
    im1.save(filename)
    font = ImageFont.truetype("./assets/ja-jp.ttf", 35)
    text = f"{user.name}"
    textLen = len(text)
    d2 = ImageDraw.Draw(im1)
    d2.text((((1024/2)-(20*(textLen/2))),410), text, font=font, fill=color)
    im1.save(filename)
    return filename

async def setup(bot):
    pass