# ruff: noqa: I001

import gzip
import re

def read_ft3(filename):
    with open(filename, "rb") as f:
        magic = f.read(2)  # читаем первые два байта
        f.seek(0)  # возвращаем указатель в начало

        if magic == b'\x1F\x8B':  # это gzip
            with gzip.open(filename, "rb") as gz:
                return gz.read()
        else:
            return f.read()

def extract_text(data, marker):
    pos = data.find(marker)
    if pos == -1:
        return None, None
    pos += len(marker)
    length = data[pos]
    text = data[pos + 1: pos + 1 + length].decode('utf-8', errors='ignore')
    return text, pos + 1 + length


def parse_bar(bar_data):
    bar = {
        "notes": []
    }
    
    ptr = 32  # Начало нот в такте
    while ptr + 9 <= len(bar_data):
        if not at_next_note(bar_data[ptr], bar_data[ptr + 1]):
            ptr += 1
            continue
        
        note = {
            "string": None,
            "fret": None
        }
        
        if bar_data[ptr] < 8:
            note["string"] = bar_data[ptr] - 1  # Струны 2-7 -> 1-6
            note["fret"] = bar_data[ptr + 1] - 0x30  # Лады a-p
        elif bar_data[ptr] == 8:
            if bar_data[ptr + 4] == 0x00:
                note["string"] = 7
                note["fret"] = bar_data[ptr + 1] - 0x61  # Лады a-f
            elif bar_data[ptr + 4] == 0x20:
                note["string"] = bar_data[ptr + 1] - 0x30 + 7  # Открытые басовые
                note["fret"] = 0
            elif bar_data[ptr + 4] == 0x48:
                note["string"] = 8
                note["fret"] = bar_data[ptr + 1] - 0x61
        
        bar["notes"].append(note)
        ptr += 5  # Смещаемся к следующей ноте
    
    return bar


def at_next_note(s, f):
    on_fret = 0x30 <= f <= 0x3E  # Фреты a-p
    on_diapason = 0x61 <= f <= 0x66  # Фреты a-f на басах
    on_string = 0x02 <= s <= 0x08  # Струны 2-8
    
    return on_string and (on_fret or on_diapason)


def parse_ft3(filename):
    data = read_ft3(filename)
    
    # Extract metadata
    title, pos = extract_text(data, b'CPiece')
    author, pos = extract_text(data[pos:], b'') if pos else (None, None)
    composer, _ = extract_text(data[pos:], b'') if pos else (None, None)
    
    print(f"Title: {title}\nAuthor: {author}\nComposer: {composer}")
    
    # Extract bars (rough approach)
    bars = re.split(b'\x03\x80', data)
    print(f"Bars found: {len(bars)}")
    
    for i, bar in enumerate(bars[:10]):  # Show first 5 bars
        print(f"Bar {i+1}: {parse_bar(bar)}")

parse_ft3("example.ft3.gz")
