import os
import re
import zlib
import unicodedata
import sys

# 5-bit Baudot (ITA2 Letters Mode)
BAUDOT_TABLE = {
    'a': '00011','b': '11001','c': '01110','d': '01001',
    'e': '00001','f': '01101','g': '11010','h': '10100',
    'i': '00110','j': '01011','k': '01111','l': '10010',
    'm': '11100','n': '01100','o': '11000','p': '10110',
    'q': '10111','r': '01010','s': '00101','t': '10000',
    'u': '00111','v': '11110','w': '10011','x': '11101',
    'y': '10101','z': '10001',' ': '00100',
    '1': '00010','2': '11011','3': '11111'
}

REVERSE_TABLE = {v: k for k, v in BAUDOT_TABLE.items()}
STOP_WORD = "stop"

# =============================
# LOAD SHORTCUTS FROM abv.txt
# =============================
def load_shortcuts(filename="abv.txt"):
    if not os.path.exists(filename):
        print("ERROR: abv.txt not found in program directory.")
        return {}

    shortcuts = {}
    allowed_chars = set(BAUDOT_TABLE.keys())

    with open(filename, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip().replace("\r", "")

            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                print(f"Invalid format in abv.txt line {line_number}: '{line}'")
                continue

            full, short = line.split("=", 1)
            full = full.strip().replace(" ", "")
            short = short.strip().replace(" ", "")

            if not full.islower() or not short.islower():
                print(f"Line {line_number}: Only lowercase words allowed.")
                continue

            if not all(c in allowed_chars for c in full):
                print(f"Line {line_number}: Invalid characters in full word.")
                continue

            if not all(c in allowed_chars for c in short):
                print(f"Line {line_number}: Invalid characters in shortcut.")
                continue

            if full in shortcuts:
                print(f"Duplicate full word on line {line_number}.")
                continue

            if short in shortcuts.values():
                print(f"Duplicate shortcut on line {line_number}.")
                continue

            shortcuts[full] = short

    return shortcuts

WORD_SHORTCUTS = load_shortcuts()
REVERSE_SHORTCUTS = {v: k for k, v in WORD_SHORTCUTS.items()}

# =============================
# FILE READER WITH FULL UNICODE DIAGNOSTICS
# =============================
def read_text_file(filename):
    if not os.path.exists(filename):
        print("Text file not found.")
        return None

    with open(filename, "r", encoding="utf-8") as f:
        text = f.read()

    unicode_errors = []
    line, column = 1, 1

    for char in text:
        if char == "\n":
            line += 1
            column = 1
            continue

        codepoint = ord(char)
        # Detect non-ASCII or invisible/control characters
        if codepoint > 127 or unicodedata.category(char)[0] == "C":
            try:
                name = unicodedata.name(char)
            except ValueError:
                name = "Unknown Unicode character"
            unicode_errors.append((line, column, repr(char), f"U+{codepoint:04X}", name))

        column += 1

    if unicode_errors:
        print("\nUnicode / Invisible character errors detected:\n")
        for err in unicode_errors:
            print(
                f"Line {err[0]}, Column {err[1]} | "
                f"Character: {err[2]} | "
                f"Code: {err[3]} | "
                f"Name: {err[4]}"
            )
        print("\nPlease fix the file to contain ASCII-only visible characters.\n")
        return None

    return text

# =============================
# CORE FUNCTIONS
# =============================
def bits_to_bytes(bitstring):
    while len(bitstring) % 8 != 0:
        bitstring += "0"
    byte_array = bytearray()
    for i in range(0, len(bitstring), 8):
        byte_array.append(int(bitstring[i:i+8], 2))
    return byte_array

def bytes_to_bits(byte_data):
    return ''.join(f'{byte:08b}' for byte in byte_data)

def apply_shortcuts_encode(message):
    words = message.split()
    return " ".join(WORD_SHORTCUTS.get(word, word) for word in words)

def apply_shortcuts_decode(message):
    words = message.split()
    return " ".join(REVERSE_SHORTCUTS.get(word, word) for word in words)

def validate_message(message):
    errors = []
    line, column = 1, 1
    for char in message:
        if char == "\n":
            line += 1
            column = 1
            continue
        if char.isupper():
            errors.append((line, column, char, "Uppercase character not allowed"))
        elif char not in BAUDOT_TABLE:
            errors.append((line, column, char, "Invalid character"))
        column += 1
    return errors

def validate_output_filename(name):
    if not name:
        print("Error: File name cannot be empty.")
        return False
    if "." in name:
        print("Error: Do NOT include '.' or '.bin' in the file name.")
        return False
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        print("Error: File name may only contain letters, numbers, underscores, and hyphens.")
        return False
    return True

def build_encoded_bytes(message):
    bitstring = ""
    for char in message:
        bitstring += BAUDOT_TABLE[char]
    for char in STOP_WORD:
        bitstring += BAUDOT_TABLE[char]
    return bits_to_bytes(bitstring)

def handle_compression(byte_data, final_filename):
    use_compression = input("Apply lossless compression? (y/n): ").strip().lower()
    if use_compression != "y":
        with open(final_filename, "wb") as f:
            f.write(byte_data)
        print("Saved uncompressed.")
        return
    compare = input("Check if compressed file is larger before saving? (y/n): ").strip().lower()
    compressed_data = zlib.compress(byte_data)
    if compare == "y" and len(compressed_data) > len(byte_data):
        print("Compressed file is larger than uncompressed.")
        choice = input("Save compressed anyway? (y = compressed / n = uncompressed): ").strip().lower()
        data = compressed_data if choice == "y" else byte_data
    else:
        data = compressed_data
    with open(final_filename, "wb") as f:
        f.write(data)
    print("Saved.")

def encode_to_file_from_text(txt_filename, output_filename):
    message = read_text_file(txt_filename)
    if message is None:
        return
    message = message.rstrip("\n")
    message = apply_shortcuts_encode(message)
    errors = validate_message(message)
    if errors:
        print(f"\nFound {len(errors)} Baudot validation errors:\n")
        for err in errors:
            print(f"Line {err[0]}, Column {err[1]} | Character: '{err[2]}' | Cause: {err[3]}")
        print("\nReturning to main menu.\n")
        return
    byte_data = build_encoded_bytes(message)
    handle_compression(byte_data, output_filename)
    print(f"\nSaved to: {os.path.abspath(output_filename)}\n")

def decode_from_file(filename):
    if not os.path.exists(filename):
        print("File not found.")
        return
    with open(filename, "rb") as f:
        byte_data = f.read()
    try:
        byte_data = zlib.decompress(byte_data)
    except:
        pass
    bitstring = bytes_to_bits(byte_data)
    decoded = ""
    stop_buffer = ""
    for i in range(0, len(bitstring), 5):
        chunk = bitstring[i:i+5]
        if len(chunk) < 5:
            break
        if chunk not in REVERSE_TABLE:
            continue
        char = REVERSE_TABLE[chunk]
        decoded += char
        stop_buffer += char
        if len(stop_buffer) > len(STOP_WORD):
            stop_buffer = stop_buffer[-len(STOP_WORD):]
        if stop_buffer == STOP_WORD:
            decoded_message = decoded[:-len(STOP_WORD)]
            decoded_message = apply_shortcuts_decode(decoded_message)
            print("\nDecoded message:")
            print(decoded_message)
            return
    print("Stop word not found.")

# =============================
# SUBMENU HANDLER
# =============================
def submenu(action_type):
    while True:
        print(f"\n--- {action_type} Submenu ---")
        print("1 = Proceed")
        print("2 = Return to main menu")
        print("3 = Exit program immediately")
        choice = input("Choose option: ").strip()
        if choice == "1":
            return True
        elif choice == "2":
            return False
        elif choice == "3":
            print("Shutting down program...")
            sys.exit()
        else:
            print("Invalid option. Choose 1, 2, or 3.")

# =============================
# MAIN LOOP
# =============================
def main():
    while True:
        print("\n=== BAUDOT ENCODER / DECODER ===")
        print("1 = Encode from .txt to .bin")
        print("2 = Decode from .bin")
        print("3 = Exit")
        choice = input("Choose option: ").strip()

        if choice == "1":
            if not submenu("Encode"):
                continue
            txt_filename = input("Enter input .txt file name: ").strip()
            if not txt_filename.endswith(".txt"):
                txt_filename += ".txt"
            output_name = input("Enter output file name (no extension): ").strip()
            if not validate_output_filename(output_name):
                continue
            output_filename = output_name + ".bin"
            encode_to_file_from_text(txt_filename, output_filename)

        elif choice == "2":
            if not submenu("Decode"):
                continue
            filename = input("Enter .bin file name to decode: ").strip()
            if not filename.endswith(".bin"):
                filename += ".bin"
            decode_from_file(filename)

        elif choice == "3":
            print("Exiting program.")
            break

        else:
            print("Invalid option. Please choose 1, 2, or 3.")

if __name__ == "__main__":
    main()
