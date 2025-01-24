# -*- coding: utf-8 -*-
# Converted from mriam.ttf using:
#     ./font2bitmap.py mriam.ttf -s 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#°{ }$%&'"'"'()*+,-:./אבגדהוזחטיכךלמםנןסעפףצץקרשת' 20

MAP = (
    'abcdefghijklmnopqrstuvwxyzABCDEF'
    'GHIJKLMNOPQRSTUVWXYZ0123456789!#'
    '°{ }$%&\'()*+,-:./אבגדהוזחטיכךלמ'
    'םנןסעפףצץקרשת'
)

BPP = 1
HEIGHT = 19
MAX_WIDTH = 17
_WIDTHS = \
    b'\x0a\x0a\x09\x0a\x0a\x05\x0a\x0a\x04\x05\x09\x04\x0f\x0a\x0a\x0a'\
    b'\x0a\x06\x09\x05\x0a\x09\x0d\x09\x09\x09\x0c\x0c\x0d\x0d\x0c\x0b'\
    b'\x0e\x0d\x05\x09\x0c\x0a\x0f\x0d\x0e\x0c\x0e\x0d\x0c\x0b\x0d\x0c'\
    b'\x11\x0c\x0c\x0b\x09\x09\x09\x09\x09\x09\x09\x09\x09\x09\x06\x09'\
    b'\x08\x0a\x06\x0a\x09\x0e\x0d\x06\x06\x06\x0a\x0c\x06\x06\x06\x06'\
    b'\x08\x0c\x0b\x08\x09\x0c\x07\x06\x0b\x0b\x07\x0b\x09\x0b\x0b\x0b'\
    b'\x07\x06\x0b\x0b\x0b\x0a\x0b\x0a\x0b\x09\x0d\x0c'

OFFSET_WIDTH = 2
_OFFSETS = \
    b'\x00\x00\x00\xbe\x01\x7c\x02\x27\x02\xe5\x03\xa3\x04\x02\x04\xc0'\
    b'\x05\x7e\x05\xca\x06\x29\x06\xd4\x07\x20\x08\x3d\x08\xfb\x09\xb9'\
    b'\x0a\x77\x0b\x35\x0b\xa7\x0c\x52\x0c\xb1\x0d\x6f\x0e\x1a\x0f\x11'\
    b'\x0f\xbc\x10\x67\x11\x12\x11\xf6\x12\xda\x13\xd1\x14\xc8\x15\xac'\
    b'\x16\x7d\x17\x87\x18\x7e\x18\xdd\x19\x88\x1a\x6c\x1b\x2a\x1c\x47'\
    b'\x1d\x3e\x1e\x48\x1f\x2c\x20\x36\x21\x2d\x22\x11\x22\xe2\x23\xd9'\
    b'\x24\xbd\x26\x00\x26\xe4\x27\xc8\x28\x99\x29\x44\x29\xef\x2a\x9a'\
    b'\x2b\x45\x2b\xf0\x2c\x9b\x2d\x46\x2d\xf1\x2e\x9c\x2f\x47\x2f\xb9'\
    b'\x30\x64\x30\xfc\x31\xba\x32\x2c\x32\xea\x33\x95\x34\x9f\x35\x96'\
    b'\x36\x08\x36\x7a\x36\xec\x37\xaa\x38\x8e\x39\x00\x39\x72\x39\xe4'\
    b'\x3a\x56\x3a\xee\x3b\xd2\x3c\xa3\x3d\x3b\x3d\xe6\x3e\xca\x3f\x4f'\
    b'\x3f\xc1\x40\x92\x41\x63\x41\xe8\x42\xb9\x43\x64\x44\x35\x45\x06'\
    b'\x45\xd7\x46\x5c\x46\xce\x47\x9f\x48\x70\x49\x41\x49\xff\x4a\xd0'\
    b'\x4b\x8e\x4c\x5f\x4d\x0a\x4e\x01'

_BITMAPS =\
    b'\x00\x00\x00\x00\x00\x00\x00\x01\xf0\xc6\x61\x87\xe7\x19\x86\x61'\
    b'\x98\xe3\xd8\x00\x00\x00\x00\x00\x00\x00\x18\x06\x01\x80\x60\x1b'\
    b'\x87\x31\x86\x61\x98\x66\x19\x86\x73\x1b\x80\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x07\x86\x66\x13\x01\x80\xc0\x61\x19\x87'\
    b'\x80\x00\x00\x00\x00\x00\x00\x00\x30\x0c\x03\x00\xc3\xb1\x9c\xc3'\
    b'\x30\xcc\x33\x0c\xc3\x19\xc3\xb0\x00\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x0f\x06\x63\x0c\xc3\x3f\xcc\x03\x0c\x66\x0f\x00'\
    b'\x00\x00\x00\x00\x00\x01\xd8\xc6\x7d\x8c\x63\x18\xc6\x30\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x76\x33\x98\x66\x19\x86\x61\x98'\
    b'\x63\x38\x76\x01\x90\x66\x30\xf8\x00\x00\x06\x01\x80\x60\x18\x06'\
    b'\xf1\xc6\x61\x98\x66\x19\x86\x61\x98\x66\x18\x00\x00\x00\x00\x00'\
    b'\x01\x98\x01\x99\x99\x99\x99\x80\x00\x00\x03\x18\x00\x31\x8c\x63'\
    b'\x18\xc6\x31\x8c\x6e\x00\x00\x0c\x06\x03\x01\x80\xc6\x66\x36\x1e'\
    b'\x0c\x86\x63\x11\x8c\xc3\x00\x00\x00\x00\x00\x06\x66\x66\x66\x66'\
    b'\x66\x66\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1b'\
    b'\xce\x38\xe6\x61\x8c\xc3\x19\x86\x33\x0c\x66\x18\xcc\x31\x98\x63'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x37'\
    b'\x8e\x73\x0c\xc3\x30\xcc\x33\x0c\xc3\x30\xc0\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x3c\x19\x8c\x33\x0c\xc3\x30\xcc\x31'\
    b'\x98\x3c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x70'\
    b'\xe6\x30\xcc\x33\x0c\xc3\x30\xce\x63\x70\xc0\x30\x0c\x03\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x03\xb1\x9c\xc3\x30\xcc\x33\x0c\xc3\x19'\
    b'\xc3\xb0\x0c\x03\x00\xc0\x30\x00\x00\x00\x00\x36\xe3\x0c\x30\xc3'\
    b'\x0c\x30\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\xf1\x8c\xc0\x7c'\
    b'\x0f\x80\xc8\x66\x31\xf0\x00\x00\x00\x00\x00\x00\x11\x8c\xfb\x18'\
    b'\xc6\x31\x8c\x38\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x0c\xc3'\
    b'\x30\xcc\x33\x0c\xc3\x30\xcc\x71\xec\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x06\x0d\x8e\xc6\x63\x1b\x0d\x82\x81\xc0\x60\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc3\x1e\x18'\
    b'\xd9\xcc\xcf\x66\x5b\x1e\xf0\xf3\x87\x1c\x18\xc0\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc3\x33\x0f\x07\x01\x81\xe0'\
    b'\x90\xcc\xc3\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x30\x6c'\
    b'\x36\x33\x18\xcc\x64\x1e\x0f\x03\x01\x80\xc0\xc1\xc0\x00\x00\x00'\
    b'\x00\x00\x00\x03\xf8\x0c\x0c\x0c\x0e\x06\x06\x06\x03\xf8\x00\x00'\
    b'\x00\x00\x00\x00\x00\x01\x80\x38\x02\xc0\x24\x06\x60\x46\x0c\x20'\
    b'\xff\x0f\xf1\x81\x98\x19\x01\xb0\x0c\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x01\xfe\x1f\xf1\x81\x98\x19\x81\x9f\xf1\xff\x18\x39\x81\x98'\
    b'\x19\x83\x9f\xf1\xfe\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf8'\
    b'\x0f\xf0\xe1\xce\x06\x60\x03\x00\x18\x00\xc0\x06\x00\x18\x18\xe1'\
    b'\xc3\xfc\x0f\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0f\xf0\x7f'\
    b'\xc3\x07\x18\x1c\xc0\x66\x03\x30\x19\x80\xcc\x06\x60\x73\x07\x1f'\
    b'\xf0\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x7f\xe7\xfe\x60'\
    b'\x06\x00\x60\x07\xf8\x7f\x86\x00\x60\x06\x00\x60\x07\xfe\x7f\xe0'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x1f\xf3\xfe\x60\x0c\x01\x80\x3f'\
    b'\x87\xf0\xc0\x18\x03\x00\x60\x0c\x01\x80\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x03\xe0\x3f\xe1\xc0\xc6\x01\x30\x00\xc0\x03\x07\xcc'\
    b'\x1f\x30\x0c\x60\x31\xc1\xc3\xfe\x03\xe0\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x30\x19\x80\xcc\x06\x60\x33\x01\x9f\xfc\xff\xe6'\
    b'\x03\x30\x19\x80\xcc\x06\x60\x33\x01\x80\x00\x00\x00\x00\x00\x00'\
    b'\x00\x31\x8c\x63\x18\xc6\x31\x8c\x63\x00\x00\x00\x00\x00\x06\x03'\
    b'\x01\x80\xc0\x60\x30\x18\x0c\x06\x43\x31\x9f\x87\x80\x00\x00\x00'\
    b'\x00\x00\x00\x00\x60\x66\x0c\x61\x86\x30\x66\x06\xe0\x7e\x07\x30'\
    b'\x61\x86\x18\x60\xc6\x06\x60\x70\x00\x00\x00\x00\x00\x00\x00\x00'\
    b'\x60\x18\x06\x01\x80\x60\x18\x06\x01\x80\x60\x18\x06\x01\xfe\x7f'\
    b'\x80\x00\x00\x00\x00\x00\x00\x00\x00\x70\x1c\xe0\x39\xe0\xf3\xc1'\
    b'\xe6\x82\xcd\x8d\x99\x1b\x32\x26\x66\x4c\xc5\x19\x8a\x33\x1c\x66'\
    b'\x10\xc0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x30\x19\xc0\xcf'\
    b'\x06\x68\x33\x21\x99\x0c\xc4\x66\x13\x30\x99\x82\xcc\x1e\x60\x73'\
    b'\x01\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\xe0\x1f\xe0\xe1'\
    b'\xc3\x03\x18\x06\x60\x19\x80\x66\x01\x98\x06\x30\x30\xe1\xc1\xfe'\
    b'\x01\xe0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x7f\x87\xfc\x60'\
    b'\xe6\x06\x60\x66\x0e\x7f\xc7\xf8\x60\x06\x00\x60\x06\x00\x60\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0f\xc0\x7f\x83\x87\x0c\x0c'\
    b'\x60\x19\x80\x66\x01\x98\x06\x60\x18\xc2\xc3\x87\x07\xf8\x0f\xb8'\
    b'\x00\x20\x00\x00\x00\x00\x00\x00\x00\x00\x7f\xc3\xff\x18\x1c\xc0'\
    b'\x66\x03\x30\x39\xff\x8f\xf0\x61\x83\x06\x18\x18\xc0\x66\x01\x80'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\xfc\x1f\xe3\x83\x30\x03\x80'\
    b'\x1f\x80\xfe\x00\xf0\x03\x30\x33\x87\x1f\xe0\xfc\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x7f\x8f\xf0\x30\x06\x00\xc0\x18\x03\x00\x60'\
    b'\x0c\x01\x80\x30\x06\x00\xc0\x00\x00\x00\x00\x00\x00\x00\x00\x06'\
    b'\x03\x30\x19\x80\xcc\x06\x60\x33\x01\x98\x0c\xc0\x66\x03\x30\x19'\
    b'\xc1\x87\xfc\x0f\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x60\x1b'\
    b'\x03\x30\x33\x03\x18\x61\x86\x18\x60\xcc\x0c\xc0\x48\x07\x80\x78'\
    b'\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x81\x83\xc1\xc1'\
    b'\xa0\xe1\x98\x58\xcc\x6c\x66\x32\x63\x11\x30\x98\x98\x6c\x68\x3c'\
    b'\x3c\x1e\x0e\x07\x06\x03\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x60\x63\x0c\x19\x81\x98\x0f\x00\x60\x06\x00\xf0\x0b'\
    b'\x01\x98\x30\xc3\x0c\x60\x60\x00\x00\x00\x00\x00\x00\x00\x00\x06'\
    b'\x03\x30\x63\x0c\x18\xc1\x98\x0f\x00\xf0\x06\x00\x60\x06\x00\x60'\
    b'\x06\x00\x60\x00\x00\x00\x00\x00\x00\x00\x00\x01\xff\x3f\xe0\x0c'\
    b'\x03\x00\xc0\x30\x0e\x01\x80\x60\x18\x06\x00\xff\x9f\xf0\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\xe0\x88\xc2\x41\x20\x90\x48\x24'\
    b'\x13\x08\x88\x38\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\x0c\x0e'\
    b'\x05\x00\x80\x40\x20\x10\x08\x04\x02\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x01\xc1\x11\x08\x84\x06\x06\x06\x06\x02\x02\x01\xf8\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x01\xf8\x0c\x0c\x0c\x07\x06\x40\x10'\
    b'\x08\x04\xc4\x3c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x07\x02\x82'\
    b'\x41\x20\x90\xc8\x44\x7f\x01\x00\x80\x40\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x03\xf1\x00\x80\xc0\x7e\x21\x80\x40\x24\x13\x10\xf0\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x1c\x18\x10\x10\x0b\x86\x22\x09'\
    b'\x04\x82\x22\x0e\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1f\xc0\x20'\
    b'\x20\x10\x10\x08\x08\x04\x04\x02\x01\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x01\xf1\x8c\x82\x41\x11\x07\x04\x44\x12\x09\x8c\x7c\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x1c\x11\x10\x48\x24\x11\x18\x74'\
    b'\x02\x02\x06\x0e\x00\x00\x00\x00\x00\x00\x00\x10\x41\x04\x10\x41'\
    b'\x04\x00\x01\x04\x00\x00\x00\x00\x00\x00\x00\x00\x48\x24\x12\xff'\
    b'\x89\x04\x9f\xf2\x41\x21\x20\x90\x00\x00\x00\x00\x00\x00\x03\xc6'\
    b'\x64\x24\x26\x63\xc0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x10\x08\x02\x00\x80\x20\x08\x02\x00\x80\xc0\x08\x02\x00\x80'\
    b'\x20\x08\x02\x00\x80\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x20\x04\x01\x00\x40\x10\x04\x01\x00'\
    b'\x40\x0c\x04\x01\x00\x40\x10\x04\x01\x00\x40\x20\x00\x00\x00\x00'\
    b'\x00\x40\xf0\xd6\x49\x24\x0a\x03\x80\xb0\x4a\x24\x96\x3e\x04\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x41\xc2\x08\x88\x22\x40\x8b'\
    b'\x01\xc8\x00\x40\x03\x38\x09\x10\x44\x41\x11\x08\x38\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x38\x03\x20\x11\x00\x88\x04'\
    b'\x5c\x14\x40\xc4\x1b\x41\x1a\x08\x60\x63\x91\xe7\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x10\x42\x08\x00\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x01\x08\x41\x08\x20\x82\x08\x20\x41\x02\x04\x00\x00'\
    b'\x00\x04\x08\x10\x40\x82\x08\x20\x82\x10\x42\x18\x00\x00\x81\x20'\
    b'\x6b\x07\x01\xc1\xac\x08\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80'\
    b'\x08\x00\x80\x08\x0f\xf8\x08\x00\x80\x08\x00\x80\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc2\x18\x40\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x01\xe0\x00\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x03\x0c\x00\x00\x00\x30\xc0\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x0c\x30\x00\x00\x00\x00\x08\x10\x10\x10'\
    b'\x20\x20\x20\x40\x40\x80\x80\x81\x01\x01\x02\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x87\x04\x10\x21\x02\x10\x51\x08\xa0\x8c\x08\x40'\
    b'\x82\x08\x20\xf1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01'\
    b'\xf8\x00\x80\x10\x02\x00\x40\x08\x01\x00\x20\x04\x00\x87\xf8\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x07\x80\x80\x80\x80\x80\x80\x81'\
    b'\x82\x84\x88\x80\x00\x00\x00\x00\x00\x00\x00\x00\xff\x02\x01\x00'\
    b'\x80\x40\x20\x10\x08\x04\x02\x01\x00\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\xff\x00\x10\x01\x08\x10\x81\x08\x10\x81\x08\x10\x81'\
    b'\x08\x10\x81\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\xe0\x40\x81'\
    b'\x02\x04\x08\x10\x20\x40\x80\x00\x00\x00\x00\x00\x01\xf1\x04\x10'\
    b'\x41\x04\x10\x41\x04\x00\x00\x00\x00\x00\x00\x00\x00\x03\xfc\x20'\
    b'\x84\x10\x82\x10\x42\x08\x41\x08\x21\x04\x20\x84\x10\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x01\x9c\x14\x42\x88\x51\x08\x21\x04'\
    b'\x20\x84\x10\x82\x10\x41\xf0\x00\x00\x00\x00\x00\x00\x00\x00\x00'\
    b'\xf0\x20\x40\x81\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x03\xf0\x01\x00\x20\x04\x00\x80\x10\x02\x00\x40\x08\x01'\
    b'\x0f\xc0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\xf0\x08\x04\x02'\
    b'\x01\x00\x80\x40\x20\x10\x08\x04\x02\x01\x00\x00\x00\x00\x00\x10'\
    b'\x02\x00\x7f\x80\x10\x02\x00\x40\x18\x06\x01\x80\x60\x18\x02\x00'\
    b'\x40\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x77\x83\x08\x41'\
    b'\x08\x21\x04\x20\x84\x10\x82\x10\x42\x08\x4f\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x1f\xf1\x02\x20\x44\x08\x81\x10\x22\x04'\
    b'\x40\x88\x11\x02\x3f\xc0\x00\x00\x00\x00\x00\x00\x00\x00\x07\x02'\
    b'\x04\x08\x10\x20\x40\x81\x02\x3c\x00\x00\x00\x00\x00\x00\x0e\x08'\
    b'\x20\x82\x08\x20\x82\x08\x20\x82\x00\x00\x00\x00\x00\x00\x00\x1f'\
    b'\xe1\x04\x20\x84\x10\x82\x10\x42\x08\x41\x08\x21\x8c\x1f\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1c\x70\x82\x10\x42\x08\x41'\
    b'\x08\x21\x04\x20\x84\x10\x84\x7f\x00\x00\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x07\xf0\x82\x10\x42\x08\x41\x0f\x20\x04\x00\x80\x10'\
    b'\x02\x1f\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x3f\x88\x22'\
    b'\x08\x82\x20\x88\x23\x88\x02\x00\x80\x20\x08\x02\x00\x80\x00\x00'\
    b'\x00\x00\x00\x00\x00\x0e\x38\x41\x08\x21\x08\x11\x01\x40\x18\x00'\
    b'\x80\x08\x01\x3f\xe0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xe3'\
    b'\x88\x22\x08\x84\x22\x0f\x02\x00\x80\x20\x08\x02\x00\x80\x20\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x1f\xf0\x02\x00\x44\x08\x81\x10\x42'\
    b'\x18\x42\x08\x81\x10\x22\x04\x00\x80\x00\x00\x00\x00\x00\x00\x00'\
    b'\x0f\xe0\x10\x08\x04\x02\x01\x00\x80\x40\x20\x10\x08\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x00\x00\xc9\x84\x44\x22\x21\x11\x08\x88'\
    b'\x44\x42\x22\x11\x10\x88\x84\x44\x1f\xc0\x00\x00\x00\x00\x00\x00'\
    b'\x00\x00\x00\x00\x00\x00\x3f\xe0\x82\x08\x20\x82\x08\x20\x82\x08'\
    b'\x20\x82\x08\x20\x82\x38\x20\x00\x00\x00\x00\x00\x00'

WIDTHS = memoryview(_WIDTHS)
OFFSETS = memoryview(_OFFSETS)
BITMAPS = memoryview(_BITMAPS)

