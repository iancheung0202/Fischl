import io
import os

from PIL import Image, ImageDraw, ImageFont, ImageSequence

from commands.Events.config import FRAMES_DIRECTORY, DEFAULT_BG_PATH, FONT_PATH, PROFILE_CARD_PATH, CURRENCY_ICON_PATH

async def createProfileCard(
    user,
    num: str,
    rank: str,
    bg: str = DEFAULT_BG_PATH,
    filename: str = PROFILE_CARD_PATH,
    profile_frame: str = None
):
    # Avatar
    if user.avatar is None:
        im_avatar = Image.open("assets/DefaultIcon.png").convert("RGBA").resize((128, 128))
    else:
        avatar_bytes = await user.avatar.with_static_format("png").with_size(128).read()
        im_avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    mask = Image.new("L", im_avatar.size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0) + im_avatar.size, fill=255)
    im_avatar.putalpha(mask)

    # Fonts
    font_display = ImageFont.truetype(FONT_PATH, 45)
    font_username = ImageFont.truetype(FONT_PATH, 25)
    font_mora = ImageFont.truetype(FONT_PATH, 40)
    font_rank = ImageFont.truetype(FONT_PATH, 35)
    
    # Helper function for animated images
    def load_image_frames(path):
        if not os.path.exists(path):
            return None, None, None
        try:
            im = Image.open(path)
            frames = []
            durations = []
            disposals = []
            if path.lower().endswith('.gif'):
                for frame in ImageSequence.Iterator(im):
                    frames.append(frame.convert('RGBA'))
                    durations.append(frame.info.get('duration', 100))
                    disposals.append(frame.info.get('disposal', 2))
                return frames, durations, disposals
            else:
                return [im.convert('RGBA')], [100], [2]
        except Exception as e:
            print(f"Error loading {path}: {e}")
            return None, None, None

    bg_animated = bg and bg.lower().endswith('.gif') and os.path.exists(bg)
    frame_animated = profile_frame and profile_frame.lower().endswith('.gif') and os.path.exists(f"{FRAMES_DIRECTORY}/{profile_frame}")

    # Create an animated profile card
    if bg_animated or frame_animated:  
        bg_frames, bg_durations, bg_disposals = load_image_frames(bg) or ([Image.new('RGBA', (720, 256), (0, 0, 0, 255))], [100], [2])
        frame_path = f"{FRAMES_DIRECTORY}/{profile_frame}" if profile_frame else None
        frame_frames, frame_durations, frame_disposals = load_image_frames(frame_path) or ([None], [100], [2])
        
        if len(bg_frames) > 1:
            total_frames = len(bg_frames)
            durations = bg_durations
            disposals = bg_disposals
            if len(frame_frames) == 1:
                frame_frames = frame_frames * total_frames
            else:
                frame_frames = [frame_frames[i % len(frame_frames)] for i in range(total_frames)]
        else:
            total_frames = len(frame_frames)
            durations = frame_durations
            disposals = frame_disposals
            bg_frames = bg_frames * total_frames
        
        output_frames = []
        for i in range(total_frames):
            frame = bg_frames[i].copy()

            # Avatar
            frame.paste(im_avatar, (40, 30), im_avatar)
            
            # Mora icon
            try:
                im_mora_icon = Image.open(CURRENCY_ICON_PATH).convert("RGBA")
                icon_mask = Image.new("L", im_mora_icon.size, 0)
                d_icon = ImageDraw.Draw(icon_mask)
                d_icon.ellipse((0, 0) + im_mora_icon.size, fill=255)
                im_mora_icon.putalpha(icon_mask)
                frame.paste(im_mora_icon, (38, 190), im_mora_icon)
            except FileNotFoundError:
                pass
            
            # Profile frame
            if frame_frames[i]:
                frame_img = frame_frames[i]
                x = 40 + (128 - frame_img.width) // 2
                y = 30 + (128 - frame_img.height) // 2
                frame.paste(frame_img, (x, y), frame_img)

            # Draw text
            draw = ImageDraw.Draw(frame)
            draw.text((200, 45), user.display_name, font=font_display, fill=(255, 255, 255))
            draw.text((200, 100), user.name, font=font_username, fill=(225, 225, 225))
            draw.text((89, 185), num.split(".")[0], font=font_mora, fill=(233, 253, 255))
            if rank != "N/A":
                draw.text((400, 190), f"Guild Rank: {rank}", font=font_rank, fill=(203, 254, 196))
            
            output_frames.append(frame)
        
        # Save animated GIF
        if not filename.lower().endswith('.gif'):
            filename = filename.rsplit(".", 1)[0] + ".gif"

        output_frames[0].save(
            filename,
            save_all=True,
            append_images=output_frames[1:],
            duration=durations,
            loop=0,
            disposal=disposals,
            optimize=False,
        )
        return filename

    # Create a static profile card
    try:
        im_bg = Image.open(bg).convert("RGBA")
    except Exception:
        im_bg = Image.open(DEFAULT_BG_PATH).convert("RGBA")

    # Avatar
    im_bg.paste(im_avatar, (40, 30), im_avatar)
    im_profile_frame = Image.open(f"{FRAMES_DIRECTORY}/{profile_frame}").convert("RGBA") if profile_frame else None

    # Mora icon
    try:
        im_mora_icon = Image.open(CURRENCY_ICON_PATH).convert("RGBA")
        icon_mask = Image.new("L", im_mora_icon.size, 0)
        d_icon = ImageDraw.Draw(icon_mask)
        d_icon.ellipse((0, 0) + im_mora_icon.size, fill=255)
        im_mora_icon.putalpha(icon_mask)
        im_bg.paste(im_mora_icon, (38, 190), im_mora_icon)
    except FileNotFoundError:
        pass

    # Profile frame
    if im_profile_frame:
        frame_w, frame_h = im_profile_frame.size
        avatar_w, avatar_h = im_avatar.size
        center_x = 40 + avatar_w // 2
        center_y = 30 + avatar_h // 2
        paste_x = center_x - frame_w // 2
        paste_y = center_y - frame_h // 2
        im_bg.paste(im_profile_frame, (paste_x, paste_y), im_profile_frame)
        
    # Draw text
    draw = ImageDraw.Draw(im_bg)
    draw.text((200, 45), user.display_name, font=font_display, fill=(255, 255, 255))
    draw.text((200, 100), user.name, font=font_username, fill=(225, 225, 225))
    draw.text((89, 185), num.split(".")[0], font=font_mora, fill=(233, 253, 255))
    if rank != "N/A":
        draw.text((400, 190), f"Guild Rank: {rank}", font=font_rank, fill=(203, 254, 196))

    # Save static image
    im_bg.save(filename)
    return filename

async def setup(bot):
    pass