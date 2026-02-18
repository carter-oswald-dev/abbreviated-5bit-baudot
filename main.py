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


# Convert bitstring to real bytes
def bits_to_bytes(bitstring):
    # Pad to multiple of 8 bits
    while len(bitstring) % 8 != 0:
        bitstring += "0"

    byte_array = bytearray()
    for i in range(0, len(bitstring), 8):
        byte = bitstring[i:i+8]
        byte_array.append(int(byte, 2))

    return byte_array


# Convert bytes back to full bitstring
def bytes_to_bits(byte_data):
    return ''.join(f'{byte:08b}' for byte in byte_data)


def encode_to_file(message, filename="output.bin"):
    bitstring = ""

    # Encode message
    for char in message:
        if char not in BAUDOT_TABLE:
            raise ValueError(f"Invalid character: {char}")
        bitstring += BAUDOT_TABLE[char]

    # Append stop word
    for char in STOP_WORD:
        bitstring += BAUDOT_TABLE[char]

    byte_data = bits_to_bytes(bitstring)

    with open(filename, "wb") as f:
        f.write(byte_data)

    print(f"Encoded and written to {filename}")


def decode_from_file(filename="output.bin"):
    with open(filename, "rb") as f:
        byte_data = f.read()

    bitstring = bytes_to_bits(byte_data)

    decoded = ""
    stop_buffer = ""

    # Read in 5-bit chunks
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
            print("Decoded message:")
            print(decoded[:-len(STOP_WORD)])
            return

    print("Stop word not found.")


def main():
    print("1 = Encode to .bin")
    print("2 = Decode from .bin")
    choice = input("Choose option: ")

    if choice == "1":
        user_input = input("Enter lowercase text (letters, space, 1-3 only): ")
        encode_to_file(user_input)

    elif choice == "2":
        decode_from_file()

    else:
        print("Invalid option.")


if __name__ == "__main__":
    main()
