import os

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

WORD_SHORTCUTS = {
    "dispose": "dpo",
}

REVERSE_SHORTCUTS = {v: k for k, v in WORD_SHORTCUTS.items()}


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


# Improved validation with line + column tracking
def validate_message(message):
    errors = []
    line = 1
    column = 1

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


def read_text_file(filename):
    if not os.path.exists(filename):
        print("Text file not found.")
        return None

    with open(filename, "r", encoding="ascii", errors="strict") as f:
        return f.read()


def encode_to_file_from_text(txt_filename, output_filename):
    message = read_text_file(txt_filename)
    if message is None:
        return

    message = message.rstrip("\n")
    message = apply_shortcuts_encode(message)

    errors = validate_message(message)

    if errors:
        if len(errors) > 10:
            print(f"\nFile contains {len(errors)} errors. Too many to display individually.")
        else:
            print(f"\nFound {len(errors)} error(s):\n")
            for line, column, char, reason in errors:
                print(f"Line {line}, Column {column}: '{char}' -> {reason}")
        return

    # Check if output file exists
    if os.path.exists(output_filename):
        overwrite = input(f"\nFile '{output_filename}' already exists. Overwrite? (y/n): ").strip().lower()
        if overwrite != "y":
            print("Operation cancelled. File was not overwritten.")
            return

    bitstring = ""

    for char in message:
        bitstring += BAUDOT_TABLE[char]

    for char in STOP_WORD:
        bitstring += BAUDOT_TABLE[char]

    byte_data = bits_to_bytes(bitstring)

    with open(output_filename, "wb") as f:
        f.write(byte_data)

    # Show full absolute path
    full_path = os.path.abspath(output_filename)

    print("\nEncoded successfully.")
    print(f".bin file saved to:\n{full_path}")


def decode_from_file(filename):
    if not os.path.exists(filename):
        print("File not found.")
        return

    with open(filename, "rb") as f:
        byte_data = f.read()

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


def main():
    print("1 = Encode from .txt to .bin")
    print("2 = Decode from .bin")
    choice = input("Choose option: ")

    if choice == "1":
        txt_filename = input("Enter input .txt file name: ").strip()

        if not txt_filename.endswith(".txt"):
            txt_filename += ".txt"

        output_filename = input("Enter output file name (example: message.bin): ").strip()

        if not output_filename.endswith(".bin"):
            output_filename += ".bin"

        encode_to_file_from_text(txt_filename, output_filename)

    elif choice == "2":
        filename = input("Enter .bin file name to decode: ").strip()

        if not filename.endswith(".bin"):
            filename += ".bin"

        decode_from_file(filename)

    else:
        print("Invalid option.")


if __name__ == "__main__":
    main()
