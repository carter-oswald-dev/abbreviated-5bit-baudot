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

# 🔹 Word compression dictionary
WORD_SHORTCUTS = {
    "dispose": "dpo",
}

REVERSE_SHORTCUTS = {v: k for k, v in WORD_SHORTCUTS.items()}


def bits_to_bytes(bitstring):
    while len(bitstring) % 8 != 0:
        bitstring += "0"

    byte_array = bytearray()
    for i in range(0, len(bitstring), 8):
        byte = bitstring[i:i+8]
        byte_array.append(int(byte, 2))

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

    for index, char in enumerate(message):
        if char.isalpha() and char.isupper():
            errors.append((index, char, "Uppercase character not allowed"))
        elif char not in BAUDOT_TABLE:
            errors.append((index, char, "Invalid character"))

    return errors


def encode_to_file(message, filename):
    bitstring = ""

    message = apply_shortcuts_encode(message)

    while True:
        errors = validate_message(message)

        if not errors:
            break

        print(f"\nFound {len(errors)} error(s):\n")

        for index, char, reason in errors:
            print(message)
            print(" " * index + "^")
            print(f"{reason} at position {index}: '{char}'\n")

        message = input("Please re-enter text using lowercase letters only: ")
        message = apply_shortcuts_encode(message)

    for char in message:
        bitstring += BAUDOT_TABLE[char]

    for char in STOP_WORD:
        bitstring += BAUDOT_TABLE[char]

    byte_data = bits_to_bytes(bitstring)

    with open(filename, "wb") as f:
        f.write(byte_data)

    print(f"\nEncoded and written to {filename}")


def decode_from_file(filename):
    if not os.path.exists(filename):
        print("File not found in current directory.")
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
    print("1 = Encode to .bin")
    print("2 = Decode from .bin")
    choice = input("Choose option: ")

    if choice == "1":
        user_input = input("Enter text (letters, space, 1-3 only): ")

        filename = input("Enter output file name (example: message.bin): ")

        if not filename.endswith(".bin"):
            filename += ".bin"

        encode_to_file(user_input, filename)

    elif choice == "2":
        filename = input("Enter .bin file name to decode: ")

        if not filename.endswith(".bin"):
            filename += ".bin"

        decode_from_file(filename)

    else:
        print("Invalid option.")


if __name__ == "__main__":
    main()
