#!/usr/bin/env python3

from math import pi
from PIL import Image, ImageDraw, ImageFont
import colorsys
import os
import random
import subprocess
import sys
import time


#RESOLUTION = (3840, 2160)  # 4K UHD
#RESOLUTION = (1920, 1080)  # easier to work with
RESOLUTION = (960, 540)  # much easier to work with
MARGIN = 50
FILENAME_FORMAT_FORMAT = 'img_%s_{}.png'
FEEDBACK_INTERVAL = 10
DEBUG_OUTLINES = False
GAMMA = 1.3  # 1 = symmetric around "0 % 1"; higher = skew towards 1.0
LUMINANCE_INVERSION_CHANCE = 0.8  # 0.5 = perfect independence; higher = more anti-correlation (flickering)
LUMINANCE_STDDEV = 0.11  # 0 = black-white-only; higher = more colors of "intermediate" luminance
SATURATION_STDDEV = 0.08  # 0 = full-saturation-only; higher = permit gray-ish colors
NUM_FILES = 1145
OUTPUT_FRAMERATE = '2.97333'  # wtf
OUTPUT_FILENAME_FORMAT = 'stimulating_%s.mp4'
INCLUDE_MUSIC = os.environ.get('EMIT_MUSIC_FILE')  # '/path/to/my/music_file.mp3'
DO_VIDEO = INCLUDE_MUSIC
DO_CLEANUP = not DO_VIDEO

WORDS = [
    # x and y are the centers of each object, 0 <= x,y < 1
    # angle is in degrees
    # fontsize, x, y, and angle have two values each: avg and stddev

    # phrase     fontsize  ----x-----  ----y-----  angle
    ('✓',        800, 100, 0.50, 0.08, 0.30, 0.02, 0,  7),
    ('STIMULUS', 100,  50, 0.48, 0.10, 0.70, 0.01, 0,  3),
    ('CHECK',    100,  50, 0.52, 0.08, 0.85, 0.01, 0,  3),
    ('✓',        400, 130, 0.25, 0.08, 0.60, 0.20, 0, 25),
    ('✓',        400, 130, 0.75, 0.08, 0.60, 0.20, 0, 25),
]

USABLE_FONTS = [
    # Hand-picked from `locate *.ttf`:
    # - Some are cut off by their bounding box (?!)
    # - The vast majority doesn't support the '✓' glyph
    '/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSerif.ttf',
    '/usr/share/fonts/truetype/unifont/unifont.ttf',
    '/usr/share/fonts/truetype/vlgothic/VL-PGothic-Regular.ttf',
    # Lessen the probability of "unifont" by duplicating all other fonts:
    '/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSerif.ttf',
    # … except unifont: '/usr/share/fonts/truetype/unifont/unifont.ttf',
    '/usr/share/fonts/truetype/vlgothic/VL-PGothic-Regular.ttf',
]


def check_fonts():
    global USABLE_FONTS
    actually_usable_fonts = []
    for font in USABLE_FONTS:
        try:
            ImageFont.truetype(font)
        except OSError:
            print('Missing/broken font: {}'.format(font), file=sys.stderr)
        else:
            actually_usable_fonts.append(font)
    if len(actually_usable_fonts) != len(USABLE_FONTS):
        print('WARNING: Could find only {} out of {} known fonts!'.format(len(actually_usable_fonts), len(USABLE_FONTS)), file=sys.stderr)
    USABLE_FONTS = actually_usable_fonts


def pick_any_font(fontsize):
    assert USABLE_FONTS
    fontname = random.choice(USABLE_FONTS)
    return ImageFont.truetype(fontname, fontsize)


class PreprocessedDistrib:
    def __init__(self, avg, stddev, clamp=None):
        self.avg = avg
        self.stddev = stddev
        self.clamp = clamp

    def sample(self):
        value = random.gauss(self.avg, self.stddev)
        if self.clamp is not None:
            value = max(self.clamp[0], min(value, self.clamp[1]))
        return value


def pick_clashing_color(old_color):
    # Luminance needs to (anti-)correlate with old color to create "flickering" effect.
    new_luminance = abs(random.gauss(0, LUMINANCE_STDDEV)) % 1
    old_luminance = colorsys.rgb_to_hls(*((c / 255) ** GAMMA for c in old_color))[1]
    should_be_high = old_luminance >= 0.5
    if random.random() < LUMINANCE_INVERSION_CHANCE:
        should_be_high = not should_be_high
    if should_be_high:
        new_luminance = 1 - new_luminance

    # Hue and saturation can be independent:
    hue = random.random()
    saturation = 1 - abs(random.gauss(0, SATURATION_STDDEV))

    # Put it all together:
    hls01 = (hue, new_luminance, saturation)
    rgb01 = colorsys.hls_to_rgb(*hls01)
    return tuple(max(0, min(round((c ** (1 / GAMMA)) * 255), 255)) for c in rgb01)


class PreprocessedWord:
    def __init__(self, phrase, font_avg, font_stddev, x_avg, x_stddev, y_avg, y_stddev, angle_avg, angle_stddev):
        self.phrase = phrase
        # By experiment: 2000pt is the largest reasonable fontsize on 4K
        self.font_distrib = PreprocessedDistrib(font_avg, font_stddev, (16, 2000))
        self.x_distrib = PreprocessedDistrib(x_avg * RESOLUTION[0], x_stddev * RESOLUTION[0], (MARGIN, RESOLUTION[0] - MARGIN))
        self.y_distrib = PreprocessedDistrib(y_avg * RESOLUTION[1], y_stddev * RESOLUTION[1], (MARGIN, RESOLUTION[1] - MARGIN))
        self.angle_distrib = PreprocessedDistrib(angle_avg, angle_stddev)
        self.last_color = pick_clashing_color((0, 0, 0))

    def sample_render(self):
        self.last_color = pick_clashing_color(self.last_color)
        font = pick_any_font(round(self.font_distrib.sample()))
        zerodegree_bbox = font.getsize(self.phrase)
        zerodegree_patch = Image.new('RGBA', zerodegree_bbox, (0, 0, 0, 0))
        d = ImageDraw.Draw(zerodegree_patch)
        if DEBUG_OUTLINES:
            d.rectangle((0, 0, zerodegree_bbox[0] - 1, zerodegree_bbox[1] - 1), outline=(128, 128, 128))
        # 'anchor' is a PIL 8.0.0 feature, and will silently fail on older versions.
        d.text((zerodegree_bbox[0] / 2, zerodegree_bbox[1] / 2), self.phrase, font=font, fill=self.last_color, anchor='mm')
        del d
        angle = self.angle_distrib.sample()
        min_patch = zerodegree_patch.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=(0, 0, 0, 0))
        full_patch = Image.new('RGBA', RESOLUTION, (0, 0, 0, 0))
        textpos = (round(self.x_distrib.sample() - min_patch.width / 2), round(self.y_distrib.sample() - min_patch.height / 2))
        full_patch.paste(min_patch, textpos)
        return full_patch


def sample_image(words, background_color):
    img = Image.new('RGBA', RESOLUTION, background_color)
    for w in words:
        img.alpha_composite(w.sample_render())
    return img


def gen_and_save_images():
    print('Writing {} images ..'.format(NUM_FILES), file=sys.stderr, end='')
    sys.stderr.flush()
    filename_format = time.strftime(FILENAME_FORMAT_FORMAT)
    color = pick_clashing_color((0, 0, 0))
    words = [PreprocessedWord(*w) for w in WORDS]
    for i in range(NUM_FILES):
        if i % 20 == 0:
            print('.', file=sys.stderr, end='')
            sys.stderr.flush()
        color = pick_clashing_color(color)
        img = sample_image(words, color)
        filename = filename_format.format(i)
        img.save(filename)
    print(' done.', file=sys.stderr)
    return filename_format


def gen_texttest_img(fontsize):
    teststring = '; '.join('{}: {}'.format(i, w[0]) for i, w in enumerate(WORDS))
    total_size = [0, 0]
    for fontname in USABLE_FONTS:
        font = ImageFont.truetype(fontname, fontsize)
        this_size = font.getsize(fontname + ': ' + teststring)
        total_size[0] = max(total_size[0], this_size[0])
        total_size[1] += this_size[1]
    total_size[0] += 30
    total_size[1] += 30
    img = Image.new('RGB', total_size, (0, 0, 0))
    d = ImageDraw.Draw(img)
    offset = 15
    for fontname in USABLE_FONTS:
        font = ImageFont.truetype(fontname, fontsize)
        this_size = font.getsize(fontname + ': ' + teststring)
        d.rectangle((15, offset, 15 + this_size[0], offset + this_size[1]), outline=(255, 0, 0))
        d.text((15, offset), fontname + ': ' + teststring, font=font, fill=(255, 255, 255))
        offset += this_size[1]
    del d
    return img


def run_show_texttest():
    check_fonts()
    gen_texttest_img(48).show()


def run_show_color():
    cpw, cph = 35, 35
    margin = 3
    ncw, nch = 25, 25
    img = Image.new('RGB', (cpw * ncw, cph * nch), (127, 127, 127))
    d = ImageDraw.Draw(img)
    color = (0, 0, 0)
    for y in range(nch):
        for x in range(ncw):
            offset_x = x * cpw + margin
            offset_y = y * cph + margin
            rect_w = cpw - 2 * margin
            rect_h = cph - 2 * margin
            d.rectangle((offset_x, offset_y, offset_x + rect_w, offset_y + rect_h), fill=color)
            color = pick_clashing_color(color)
    del d
    img.show()


def run_show_single():
    check_fonts()
    back_color = (0, 0, 0)
    back_color = pick_clashing_color(back_color)
    back_color = pick_clashing_color(back_color)
    sample_image([PreprocessedWord(*w) for w in WORDS], back_color).show()


def run_full():
    check_fonts()

    # Write images
    filename_format = gen_and_save_images()

    if DO_VIDEO:
        video_filename = time.strftime(OUTPUT_FILENAME_FORMAT)
        print('Concatenating into {} ...'.format(video_filename), file=sys.stderr, end='')
        sys.stderr.flush()
        ffmpeg_args = ['ffmpeg']
        if INCLUDE_MUSIC is not None:
            ffmpeg_args.extend(['-i', INCLUDE_MUSIC])
        ffmpeg_args.extend(['-f', 'image2', '-framerate', OUTPUT_FRAMERATE, '-i', filename_format.format('%d'), '-crf', '22', video_filename])
        subprocess.run(ffmpeg_args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print(' done.', file=sys.stderr)

        if DO_CLEANUP:
            print('Cleaning up ..', file=sys.stderr, end='')
            sys.stderr.flush()
            for i in range(NUM_FILES):
                if i % 20 == 0:
                    print('.', file=sys.stderr, end='')
                    sys.stderr.flush()
                filename = filename_format.format(i)
                os.remove(filename)
            print(' done.', file=sys.stderr)

        print('Output is at ', file=sys.stderr, end='')
        sys.stderr.flush()
        print(video_filename)
    else:
        print('Output is at ', file=sys.stderr, end='')
        sys.stderr.flush()
        print(filename_format)



if __name__ == '__main__':
    #run_show_texttest()
    #run_show_color()
    #run_show_single()
    run_full()
