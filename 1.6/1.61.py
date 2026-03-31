import os
import re
import zlib
import sys
import unicodedata

# =============================================================================
# 5-bit Baudot table (modified ITA2 Letters Mode)
#
# Changes from original:
#   '1' (00010) -> '.'   period / full stop
#   '2' (11011) -> '-'   hyphen / dash
#   '3' (11111) -> '!'   exclamation mark (user-typeable form)
#
# '!' maps to Baudot bits 11111. Users MAY type '!' in messages;
# it is encoded as the 6-bit pattern  0 11111  (flag=0).
#
# The RESERVED CRC32 DELIMITER is the 6-bit pattern  1 11111
# (flag=1 + Baudot 11111). This pattern CANNOT appear naturally:
#   - Users cannot set flag=1 themselves.
#   - Abbreviation shortcodes only contain [a-z], never '!'.
# So 111111 in the raw bitstream always and only means
# "end of content, CRC32 follows".
# =============================================================================

BAUDOT_TABLE = {
    'a': '00011', 'b': '11001', 'c': '01110', 'd': '01001',
    'e': '00001', 'f': '01101', 'g': '11010', 'h': '10100',
    'i': '00110', 'j': '01011', 'k': '01111', 'l': '10010',
    'm': '11100', 'n': '01100', 'o': '11000', 'p': '10110',
    'q': '10111', 'r': '01010', 's': '00101', 't': '10000',
    'u': '00111', 'v': '11110', 'w': '10011', 'x': '11101',
    'y': '10101', 'z': '10001', ' ': '00100',
    '.': '00010', '-': '11011', '!': '11111'
}

REVERSE_TABLE = {v: k for k, v in BAUDOT_TABLE.items()}
STOP_WORD = "stop"

# 6-bit pattern that marks the boundary between content and CRC32.
# flag=1 (bit5) + Baudot 11111 ('!') = 111111.
CRC32_DELIMITER = "111111"

# =============================================================================
# 6-bit encoding layout
#
# Each character is stored as 6 bits:
#   bit 5 (MSB, leftmost): flag
#     0 = normal literal character (including user-typed '!')
#     1 = this character is part of an abbreviation shortcode,
#         OR the special CRC32 delimiter (1 11111 = 111111)
#   bits 4-0 (rightmost 5): standard 5-bit Baudot code
#
# File structure (raw bitstream before byte-packing):
#   [6-bit chars of encoded message]
#   [6-bit chars of STOP word, flag=0]
#   [111111]                        <- CRC32_DELIMITER
#   [8 nibble-letters, flag=0]      <- CRC32 encoded as 'a'-'p'
#   [6-bit chars of "endoffile", flag=0]
#
# Abbreviation framing:
#   A run of consecutive flag=1 characters (whose Baudot code is a
#   letter a-z) forms one abbreviation shortcode token.
#   The run ends when the next character has flag=0.
# =============================================================================

ABV_FILE = "abv.txt"

# =============================================================================
# CRC32 nibble encoding
#
# The CRC32 value is a 32-bit integer. We store it as 8 nibbles
# (4 bits each, values 0-15) encoded as Baudot letters 'a'-'p':
#   nibble 0  -> 'a'
#   nibble 1  -> 'b'
#   ...
#   nibble 15 -> 'p'
#
# This avoids adding digit characters (0-9) to the Baudot table.
# The 8 nibble-letters are written most-significant nibble first.
# =============================================================================

NIBBLE_TO_CHAR = [chr(ord('a') + i) for i in range(16)]
CHAR_TO_NIBBLE = {ch: i for i, ch in enumerate(NIBBLE_TO_CHAR)}


def crc32_to_nibble_string(crc_value):
    """Encode a 32-bit CRC as 8 Baudot-safe letters ('a'-'p')."""
    chars = []
    for shift in range(28, -1, -4):
        nibble = (crc_value >> shift) & 0xF
        chars.append(NIBBLE_TO_CHAR[nibble])
    return "".join(chars)


def nibble_string_to_crc32(s):
    """Decode 8 nibble-letters back to a 32-bit CRC integer."""
    value = 0
    for ch in s[:8]:
        value = (value << 4) | CHAR_TO_NIBBLE[ch]
    return value


# =============================================================================
# Abbreviation table loader
# =============================================================================

def load_abbreviations(filepath=ABV_FILE):
    """
    Load abv.txt. Format: shortcode=fullword (one per line, lowercase).
    Returns two dicts:
        short_to_full  {"ab": "about", ...}
        full_to_short  {"about": "ab", ...}
    """
    short_to_full = {}
    full_to_short = {}

    if not os.path.exists(filepath):
        return short_to_full, full_to_short

    with open(filepath, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip().lower()
            if not line or "=" not in line:
                continue
            parts = line.split("=", 1)
            if len(parts) != 2:
                continue
            short, full = parts[0].strip(), parts[1].strip()
            if short and full:
                short_to_full[short] = full
                full_to_short[full] = short

    return short_to_full, full_to_short


# =============================================================================
# Text file reader — validates charset before encoding
# =============================================================================

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
                issue = "Non-ASCII | U+{:04X} | {}".format(codepoint, name)
            elif unicodedata.category(char)[0] == "C":
                issue = "Control / Invisible character"
            elif char.isupper():
                issue = "Uppercase not allowed"
            elif char not in BAUDOT_TABLE:
                issue = "Not supported in Baudot table"

            if issue:
                errors_found = True
                print("\nLine {}, Column {}".format(line_number, column))
                print(line.rstrip("\n"))
                print(" " * (column - 1) + "^")
                print("Character: '{}'".format(char))
                print("Issue: {}".format(issue))

    if errors_found:
        print("\nFix file and try again.\n")
        return None

    return "".join(lines).rstrip("\n")


# =============================================================================
# Helpers
# =============================================================================

def bits_to_bytes(bitstring):
    """Pack a bitstring (any length) into bytes, zero-padding the last byte."""
    while len(bitstring) % 8 != 0:
        bitstring += "0"
    return bytearray(int(bitstring[i:i + 8], 2) for i in range(0, len(bitstring), 8))


def bytes_to_bits(byte_data):
    return "".join("{:08b}".format(byte) for byte in byte_data)


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


# =============================================================================
# ENCODER — tokenise -> replace abbreviations -> emit 6-bit stream
# =============================================================================

def tokenise(message):
    """
    Split message into a list of (token, is_word) pairs.
      is_word=True  : the token is a run of [a-z] letters
      is_word=False : spaces, punctuation — emitted verbatim
    """
    tokens = []
    i = 0
    while i < len(message):
        if message[i].isalpha():
            j = i
            while j < len(message) and message[j].isalpha():
                j += 1
            tokens.append((message[i:j], True))
            i = j
        else:
            tokens.append((message[i], False))
            i += 1
    return tokens


def build_6bit_stream(message, full_to_short):
    """
    Returns a list of (char, abv_flag) tuples.
    abv_flag=True  -> char is part of an abbreviation shortcode
    abv_flag=False -> normal literal character
    """
    tokens = tokenise(message)
    stream = []

    for token, is_word in tokens:
        if is_word and token in full_to_short:
            shortcode = full_to_short[token]
            for ch in shortcode:
                stream.append((ch, True))
        else:
            for ch in token:
                stream.append((ch, False))

    return stream


def encode_stream_to_bits(stream):
    """
    Convert a (char, abv_flag) stream to a bitstring using 6-bit encoding:
        bit5 = abv_flag (1 or 0)
        bits4-0 = 5-bit Baudot code
    """
    bitstring = ""
    for char, flag in stream:
        if char not in BAUDOT_TABLE:
            raise ValueError("Character '{}' not in Baudot table.".format(char))
        flag_bit = "1" if flag else "0"
        bitstring += flag_bit + BAUDOT_TABLE[char]
    return bitstring


def build_encoded_bytes(message, full_to_short):
    """
    Full pipeline: message -> 6-bit stream -> byte array.

    File structure in the bitstream:
        [encoded message chars, 6-bit each]
        [STOP word chars, flag=0]
        [111111]                    <- CRC32_DELIMITER
        [8 nibble-letters, flag=0]  <- CRC32 encoded as 'a'-'p'
        ['endoffile' chars, flag=0]
    """
    stream = build_6bit_stream(message, full_to_short)

    for ch in STOP_WORD:
        stream.append((ch, False))

    content_bits = encode_stream_to_bits(stream)
    content_bytes = bits_to_bytes(content_bits)
    crc_value = zlib.crc32(content_bytes) & 0xFFFFFFFF
    crc_encoded = crc32_to_nibble_string(crc_value)

    full_bits = content_bits
    full_bits += CRC32_DELIMITER
    for ch in crc_encoded:
        full_bits += "0" + BAUDOT_TABLE[ch]
    for ch in "endoffile":
        full_bits += "0" + BAUDOT_TABLE[ch]

    return bits_to_bytes(full_bits)


def show_encoding_preview(message, full_to_short):
    tokens = tokenise(message)
    replacements = []
    for token, is_word in tokens:
        if is_word and token in full_to_short:
            replacements.append((token, full_to_short[token]))

    if not replacements:
        print("  (no abbreviations found in message)")
        return

    print("  {:<30} -> shortcode".format("Full word"))
    print("  {}   {}".format("-" * 30, "-" * 10))
    for full, short in replacements:
        print("  {:<30} -> {}".format(full, short))


# =============================================================================
# COMPRESSION
# =============================================================================

def handle_compression(byte_data, final_filename):
    original_size = len(byte_data)
    use_compression = input("Apply lossless compression? (y/n): ").strip().lower()

    if use_compression != "y":
        with open(final_filename, "wb") as f:
            f.write(byte_data)
        print("Saved uncompressed ({} bytes).".format(original_size))
        return

    compressed_data = zlib.compress(byte_data)
    compressed_size = len(compressed_data)
    ratio = (compressed_size / original_size) * 100

    print("\nCompression statistics:")
    print("  Original size:    {} bytes".format(original_size))
    print("  Compressed size:  {} bytes".format(compressed_size))
    print("  Ratio:            {:.2f}%".format(ratio))

    if compressed_size < original_size:
        print("  Space saved:      {} bytes".format(original_size - compressed_size))
    else:
        print("  File grew by:     {} bytes".format(compressed_size - original_size))

    save = input("Save compressed version? (y/n): ").strip().lower()
    data = compressed_data if save == "y" else byte_data

    with open(final_filename, "wb") as f:
        f.write(data)
    print("Saved.")


# =============================================================================
# DECODER — 6-bit stream -> reconstruct original text
# =============================================================================

def decode_6bit_chars(bitstring, short_to_full, expand_abbreviations):
    """
    Walk a 6-bit bitstring, decode characters, expand abbreviations.
    Returns the decoded string.
    """
    decoded_chars = []
    abv_buffer = ""
    in_abbreviation = False

    i = 0
    while i + 6 <= len(bitstring):
        chunk = bitstring[i:i + 6]
        i += 6

        flag_bit = chunk[0]
        baudot_bits = chunk[1:]

        if baudot_bits not in REVERSE_TABLE:
            continue

        char = REVERSE_TABLE[baudot_bits]
        is_abv = (flag_bit == "1")

        if is_abv:
            if not in_abbreviation:
                in_abbreviation = True
                abv_buffer = ""
            abv_buffer += char
        else:
            if in_abbreviation:
                in_abbreviation = False
                if expand_abbreviations and abv_buffer in short_to_full:
                    decoded_chars.extend(list(short_to_full[abv_buffer]))
                else:
                    decoded_chars.extend(list("[ABV:{}]".format(abv_buffer)))
                abv_buffer = ""
            decoded_chars.append(char)

    if in_abbreviation and abv_buffer:
        if expand_abbreviations and abv_buffer in short_to_full:
            decoded_chars.extend(list(short_to_full[abv_buffer]))
        else:
            decoded_chars.extend(list("[ABV:{}]".format(abv_buffer)))

    return "".join(decoded_chars)


def decode_from_file(filename, short_to_full, expand_abbreviations=True):
    if not os.path.exists(filename):
        print("File not found.")
        return

    with open(filename, "rb") as f:
        byte_data = f.read()

    try:
        byte_data = zlib.decompress(byte_data)
    except Exception:
        pass

    bitstring = bytes_to_bits(byte_data)

    delim_pos = bitstring.find(CRC32_DELIMITER)

    if delim_pos == -1:
        print("Warning: CRC32 delimiter (111111) not found.")
        print("File may be from an older version. Attempting decode without CRC check...")
        raw = decode_6bit_chars(bitstring, short_to_full, expand_abbreviations)
        stop_idx = raw.find(STOP_WORD)
        if stop_idx != -1:
            print("\nDecoded message:")
            print(raw[:stop_idx])
        else:
            print("STOP word not found either. Partial output:")
            print(raw)
        return

    content_bits = bitstring[:delim_pos]
    trailer_bits = bitstring[delim_pos + 6:]

    content_bytes = bits_to_bytes(content_bits)
    computed_crc = zlib.crc32(content_bytes) & 0xFFFFFFFF

    trailer_text = decode_6bit_chars(trailer_bits, {}, False)
    stored_nibbles = trailer_text[:8]
    trailer_tag = trailer_text[8:]

    if all(ch in CHAR_TO_NIBBLE for ch in stored_nibbles):
        stored_crc = nibble_string_to_crc32(stored_nibbles)
        stored_display = "{:08x}".format(stored_crc)
    else:
        stored_crc = None
        stored_display = "(invalid nibbles: '{}')".format(stored_nibbles)

    computed_display = "{:08x}".format(computed_crc)

    print("\nCRC32 check:")
    print("  Stored:   {}".format(stored_display))
    print("  Computed: {}".format(computed_display))

    if stored_crc is not None and stored_crc == computed_crc:
        print("  PASS - file integrity verified.")
    else:
        print("  FAIL - file may be corrupted or tampered with!")
        proceed = input("Decode anyway? (y/n): ").strip().lower()
        if proceed != "y":
            return

    if trailer_tag != "endoffile":
        print("  Note: expected trailer 'endoffile', got '{}'".format(trailer_tag))

    raw = decode_6bit_chars(content_bits, short_to_full, expand_abbreviations)

    if raw.endswith(STOP_WORD):
        raw = raw[:-len(STOP_WORD)]
    elif STOP_WORD in raw:
        raw = raw[:raw.index(STOP_WORD)]
    else:
        print("Warning: STOP word not found in content.")

    print("\nDecoded message:")
    print(raw)


# =============================================================================
# CRC32 CHECK MENU FUNCTION
# =============================================================================

def crc32_check():
    filename = input("Enter .bin file name: ").strip()
    if not filename.endswith(".bin"):
        filename += ".bin"

    if not os.path.exists(filename):
        print("File not found.")
        return

    # Read raw file and check for compression
    with open(filename, "rb") as f:
        raw_bytes = f.read()

    raw_size = len(raw_bytes)

    try:
        decompressed_bytes = zlib.decompress(raw_bytes)
        is_compressed = True
        decompressed_size = len(decompressed_bytes)
        byte_data = decompressed_bytes
    except Exception:
        is_compressed = False
        decompressed_size = raw_size
        byte_data = raw_bytes

    bitstring = bytes_to_bits(byte_data)

    # Check for CRC32 delimiter
    delim_pos = bitstring.find(CRC32_DELIMITER)

    if delim_pos == -1:
        print("\nNo CRC32 delimiter found in this file.")
        print("This file was likely made with a version older than 1.6.")
        print("Returning to main menu.")
        return

    print("\nCRC32 delimiter found.")

    content_bits = bitstring[:delim_pos]
    trailer_bits = bitstring[delim_pos + 6:]

    # Compute CRC32 over content bytes
    content_bytes = bits_to_bytes(content_bits)
    computed_crc = zlib.crc32(content_bytes) & 0xFFFFFFFF
    computed_display = "{:08x}".format(computed_crc)

    # Decode trailer to get stored CRC nibbles
    trailer_text = decode_6bit_chars(trailer_bits, {}, False)
    stored_nibbles = trailer_text[:8]
    trailer_tag = trailer_text[8:]

    if all(ch in CHAR_TO_NIBBLE for ch in stored_nibbles):
        stored_crc = nibble_string_to_crc32(stored_nibbles)
        stored_display = "{:08x}".format(stored_crc)
    else:
        stored_crc = None
        stored_display = "INVALID ({})".format(stored_nibbles)

    # Count content characters (excluding STOP word)
    content_decoded = decode_6bit_chars(content_bits, {}, False)
    if content_decoded.endswith(STOP_WORD):
        content_decoded = content_decoded[:-len(STOP_WORD)]
    char_count = len(content_decoded)
    bit_count = delim_pos

    # ---- CRC PASS -----------------------------------------------------------
    if stored_crc is not None and stored_crc == computed_crc:
        print("\n+------------------------------------------------+")
        print("|           CRC32 CHECK PASSED                   |")
        print("+------------------------------------------------+")
        print("  File:               {}".format(filename))
        print("  CRC32 (stored):     {}".format(stored_display))
        print("  CRC32 (computed):   {}".format(computed_display))
        print("  Trailer tag:        {}".format(trailer_tag))
        print("  File on disk:       {} bytes".format(raw_size))
        if is_compressed:
            ratio = (raw_size / decompressed_size) * 100
            print("  Compressed:         yes")
            print("  Decompressed size:  {} bytes".format(decompressed_size))
            print("  Compression ratio:  {:.2f}%".format(ratio))
        else:
            print("  Compressed:         no")
        print("  Content bits:       {}".format(bit_count))
        print("  Content chars:      {}".format(char_count))
        print("+------------------------------------------------+")

    # ---- CRC FAIL -----------------------------------------------------------
    else:
        print("\n+------------------------------------------------+")
        print("|           CRC32 CHECK FAILED                   |")
        print("+------------------------------------------------+")
        print("  File:               {}".format(filename))
        print("  CRC32 (stored):     {}".format(stored_display))
        print("  CRC32 (computed):   {}".format(computed_display))
        print("  The file may be corrupted or tampered with.")
        print("+------------------------------------------------+")
        print("\n1 = Return to main menu")
        print("2 = Exit program")
        while True:
            choice = input("Choose option: ").strip()
            if choice == "1":
                return
            elif choice == "2":
                sys.exit()
            else:
                print("Invalid option.")


# =============================================================================
# MENU
# =============================================================================

def submenu(action_type):
    while True:
        print("\n--- {} Submenu ---".format(action_type))
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
    short_to_full, full_to_short = load_abbreviations(ABV_FILE)

    if short_to_full:
        print("Loaded {} abbreviations from {}.".format(len(short_to_full), ABV_FILE))
    else:
        print("Note: {} not found or empty - abbreviation support disabled.".format(ABV_FILE))

    while True:
        print("\n=== BAUDOT 6-BIT ENCODER / DECODER ===")
        print("1 = Encode")
        print("2 = Decode")
        print("3 = CRC32 Check")
        print("4 = Exit")

        choice = input("Choose option: ").strip()

        if choice == "1":
            print("\n1 = Encode typed message")
            print("2 = Encode from .txt file")
            mode = input("Choose mode: ").strip()

            if not submenu("Encode"):
                continue

            if mode == "1":
                message = input("Enter message (lowercase): ").strip()
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

            if not message:
                print("Empty message - nothing to encode.")
                continue

            if full_to_short:
                print("\nAbbreviation replacements that will be applied:")
                show_encoding_preview(message, full_to_short)

            output_name = input("\nEnter output file name (no extension): ").strip()
            if not validate_output_filename(output_name):
                continue

            try:
                byte_data = build_encoded_bytes(message, full_to_short)
            except ValueError as e:
                print("Encoding error: {}".format(e))
                continue

            handle_compression(byte_data, output_name + ".bin")

        elif choice == "2":
            if not submenu("Decode"):
                continue

            filename = input("Enter .bin file name: ").strip()
            if not filename.endswith(".bin"):
                filename += ".bin"

            if short_to_full:
                expand = input("Expand abbreviations back to full words? (y/n): ").strip().lower()
                expand_flag = (expand == "y")
            else:
                expand_flag = False

            decode_from_file(filename, short_to_full, expand_abbreviations=expand_flag)

        elif choice == "3":
            crc32_check()

        elif choice == "4":
            break

        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()
