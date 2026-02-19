import os
import re
import zlib
import sys
import unicodedata

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
# TEXT FILE READER WITH HIGHLIGHTING
# =============================

def read_text_file_with_diagnostics(filename):
    if not os.path.exists(filename):
        print("Text file not found.")
        return None

    with open(filename, "r", encoding="utf-8") as f:
        lines = f.readlines()

    errors_found = False

    for line_number, line in enumerate(lines, start=1):
        for column, char in enumerate(line.rstrip("\n"), start=1):

            issue = None
            codepoint = ord(char)

            if codepoint > 127:
                try:
                    name = unicodedata.name(char)
                except ValueError:
                    name = "Unknown Unicode character"
                issue = f"Non-ASCII | U+{codepoint:04X} | {name}"

            elif unicodedata.category(char)[0] == "C":
                issue = "Control / Invisible character"

            elif char.isupper():
                issue = "Uppercase not allowed"

            elif char not in BAUDOT_TABLE:
                issue = "Not supported in Baudot table"

            if issue:
                errors_found = True
                print(f"\nLine {line_number}, Column {column}")
                print(line.rstrip("\n"))
                print(" " * (column - 1) + "^")
                print(f"Character: '{char}'")
                print(f"Issue: {issue}")

    if errors_found:
        print("\nFix file and try again.\n")
        return None

    return "".join(lines).rstrip("\n")

# =============================
# CORE FUNCTIONS
# =============================

def bits_to_bytes(bitstring):
    while len(bitstring) % 8 != 0:
        bitstring += "0"
    return bytearray(int(bitstring[i:i+8], 2) for i in range(0, len(bitstring), 8))

def bytes_to_bits(byte_data):
    return ''.join(f'{byte:08b}' for byte in byte_data)

def validate_output_filename(name):
    if not name:
        print("File name cannot be empty.")
        return False
    if "." in name:
        print("Do NOT include '.' or extension.")
        return False
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        print("Only letters, numbers, underscores, hyphens allowed.")
        return False
    return True

def build_encoded_bytes(message):
    bitstring = ""
    for char in message:
        bitstring += BAUDOT_TABLE[char]
    for char in STOP_WORD:
        bitstring += BAUDOT_TABLE[char]
    return bits_to_bytes(bitstring)

# =============================
# COMPRESSION WITH STATS
# =============================

def handle_compression(byte_data, final_filename):
    original_size = len(byte_data)

    use_compression = input("Apply lossless compression? (y/n): ").strip().lower()

    if use_compression != "y":
        with open(final_filename, "wb") as f:
            f.write(byte_data)
        print(f"Saved uncompressed ({original_size} bytes).")
        return

    compressed_data = zlib.compress(byte_data)
    compressed_size = len(compressed_data)

    ratio = (compressed_size / original_size) * 100

    print("\nCompression statistics:")
    print(f"Original size: {original_size} bytes")
    print(f"Compressed size: {compressed_size} bytes")
    print(f"Compression ratio: {ratio:.2f}%")

    if compressed_size < original_size:
        print(f"Space saved: {original_size - compressed_size} bytes")
    elif compressed_size > original_size:
        print(f"File grew by: {compressed_size - original_size} bytes")

    compare = input("Save compressed version? (y/n): ").strip().lower()

    data = compressed_data if compare == "y" else byte_data

    with open(final_filename, "wb") as f:
        f.write(data)

    print("Saved.")

# =============================
# DECODE
# =============================

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
            print("\nDecoded message:")
            print(decoded[:-len(STOP_WORD)])
            return

    print("Stop word not found.")

# =============================
# MENU
# =============================

def submenu(action_type):
    while True:
        print(f"\n--- {action_type} Submenu ---")
        print("1 = Proceed")
        print("2 = Return")
        print("3 = Exit")
        choice = input("Choose option: ").strip()
        if choice == "1":
            return True
        elif choice == "2":
            return False
        elif choice == "3":
            sys.exit()
        else:
            print("Invalid option.")

def main():
    while True:
        print("\n=== BAUDOT ENCODER / DECODER ===")
        print("1 = Encode")
        print("2 = Decode")
        print("3 = Exit")

        choice = input("Choose option: ").strip()

        if choice == "1":
            print("\n1 = Encode typed message")
            print("2 = Encode from .txt file")
            mode = input("Choose mode: ").strip()

            if not submenu("Encode"):
                continue

            if mode == "1":
                message = input("Enter message: ").strip()
            elif mode == "2":
                filename = input("Enter .txt file name: ").strip()
                if not filename.endswith(".txt"):
                    filename += ".txt"
                message = read_text_file_with_diagnostics(filename)
                if message is None:
                    continue
            else:
                print("Invalid mode.")
                continue

            output_name = input("Enter output file name (no extension): ").strip()
            if not validate_output_filename(output_name):
                continue

            byte_data = build_encoded_bytes(message)
            handle_compression(byte_data, output_name + ".bin")

        elif choice == "2":
            if not submenu("Decode"):
                continue
            filename = input("Enter .bin file name: ").strip()
            if not filename.endswith(".bin"):
                filename += ".bin"
            decode_from_file(filename)

        elif choice == "3":
            break

        else:
            print("Invalid option.")

if __name__ == "__main__":
    main()
