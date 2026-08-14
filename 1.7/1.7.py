import os
import re
import zlib
import sys
import heapq
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


def find_aligned_delimiter(bitstring):
    """
    Search for CRC32_DELIMITER, but ONLY at 6-bit-aligned offsets
    (0, 6, 12, 18, ...). This is critical: str.find() searches at
    every bit position, and '!' (Baudot 11111, flag=0) can appear as
    ordinary message content. When '!' -- or any character ending in
    several 1 bits -- sits next to another character with matching
    leading 1 bits, the raw sequence '111111' can occur BY ACCIDENT
    across a character boundary, even though no single 6-bit unit is
    actually the reserved delimiter. Restricting the search to aligned
    offsets guarantees we only match a genuine flag=1 + Baudot-11111
    unit, never a coincidental straddle across two unrelated chars.
    """
    i = 0
    while i + 6 <= len(bitstring):
        if bitstring[i:i+6] == CRC32_DELIMITER:
            return i
        i += 6
    return -1

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
# HEADER BYTE  (new in 1.7)
#
# The first byte of every 1.7+ file is a header byte:
#   bits 7-6 : compression method tag
#       00 = none     (raw 6-bit content bytes, unmodified)
#       01 = zlib      (content bytes passed through zlib.compress)
#       10 = huffman   (content bits re-encoded with the static Huffman table)
#       11 = reserved
#   bits 5-0 : unused, always 0
#
# Only the MESSAGE + STOP WORD content is compressed/encoded per the tag.
# The CRC32 delimiter, CRC nibbles, and "endoffile" trailer always follow
# in plain, uncompressed 6-bit form -- see build_encoded_bytes().
#
# Files with no recognised header (pre-1.7) are still readable: the
# decoder falls back to the old try-zlib-else-raw guessing method.
# =============================================================================

HEADER_TAG_NONE = 0b00
HEADER_TAG_ZLIB = 0b01
HEADER_TAG_HUFFMAN = 0b10


def make_header_byte(tag):
    return bytes([tag << 6])


def read_header_tag(byte_data):
    """
    Returns (tag, is_new_format).
    is_new_format is False if the file doesn't look like it has a
    recognised 1.7 header (used to trigger the legacy fallback path).
    """
    if len(byte_data) < 1:
        return None, False
    header = byte_data[0]
    tag = (header >> 6) & 0b11
    low_bits = header & 0b00111111
    if low_bits != 0 or tag == 0b11:
        return None, False
    return tag, True


# =============================================================================
# STATIC HUFFMAN TABLE  (new in 1.7)
#
# Built once, at import time, from approximate English letter frequency.
# Both encoder and decoder use this exact table -- it is never stored in
# the file, so the "huffman" method costs nothing beyond the header byte.
#
# IMPORTANT: Huffman symbols are the 6-BIT UNITS themselves -- i.e. each
# symbol is a (flag, char) pair, e.g. (0, 'e') for a plain 'e' and
# (1, 'e') for an abbreviation-flagged 'e'. This ensures the Huffman
# path round-trips through the EXACT SAME content_bits as the "none"
# and "zlib" paths, so CRC32 (computed over content_bits) matches
# regardless of which compression method was used.
#
# Flag=1 symbols are given a much lower weight than their flag=0
# counterpart, since abbreviation characters are far less common than
# plain characters in typical text -- but they still need a code, since
# any character COULD appear as part of an abbreviation.
# =============================================================================

ENGLISH_FREQ_PLAIN = {
    'e': 12.7, 't': 9.1, 'a': 8.2, 'o': 7.5, 'i': 7.0, 'n': 6.7,
    's': 6.3, 'h': 6.1, 'r': 6.0, 'd': 4.3, 'l': 4.0, 'c': 2.8,
    'u': 2.8, 'm': 2.4, 'w': 2.4, 'f': 2.2, 'g': 2.0, 'y': 2.0,
    'p': 1.9, 'b': 1.5, 'v': 1.0, 'k': 0.8, 'j': 0.15, 'x': 0.15,
    'q': 0.10, 'z': 0.07,
    ' ': 18.0,
    '.': 1.0, '-': 0.3, '!': 0.3,
}

# Build the full 6-bit symbol frequency table: (flag, char) pairs.
# flag=0 symbols keep their normal English frequency.
# flag=1 symbols (abbreviation characters) get a small flat weight so
# they still get a valid (if longer) code, without dominating the tree.
_ABV_FLAG_WEIGHT = 0.5

SIXBIT_SYMBOL_FREQ = {}
for _ch, _weight in ENGLISH_FREQ_PLAIN.items():
    SIXBIT_SYMBOL_FREQ[(0, _ch)] = _weight
    SIXBIT_SYMBOL_FREQ[(1, _ch)] = _ABV_FLAG_WEIGHT


def _build_huffman_codes(freq_table):
    """Standard Huffman tree build. Returns {symbol: bitstring}."""
    heap = [[weight, [sym, ""]] for sym, weight in freq_table.items()]
    heapq.heapify(heap)

    if len(heap) == 1:
        only = heap[0][1][0]
        return {only: "0"}

    while len(heap) > 1:
        lo = heapq.heappop(heap)
        hi = heapq.heappop(heap)
        for pair in lo[1:]:
            pair[1] = "0" + pair[1]
        for pair in hi[1:]:
            pair[1] = "1" + pair[1]
        merged = [lo[0] + hi[0]] + lo[1:] + hi[1:]
        heapq.heappush(heap, merged)

    return {sym: code for sym, code in heap[0][1:]}


HUFFMAN_CODES = _build_huffman_codes(SIXBIT_SYMBOL_FREQ)
HUFFMAN_REVERSE = {v: k for k, v in HUFFMAN_CODES.items()}


def huffman_encode_content_bits(content_bits):
    """
    Re-encode a 6-bit content bitstring (flag+baudot units, as produced
    by build_message_content_bits) using the static Huffman table.
    This is a straight re-encoding: same logical content, different
    physical bit layout, so decoding it back gives the identical
    content_bits used everywhere else (and thus the identical CRC32).
    """
    bits = ""
    i = 0
    while i + 6 <= len(content_bits):
        chunk = content_bits[i:i + 6]
        i += 6
        flag_bit = chunk[0]
        baudot_bits = chunk[1:]
        if baudot_bits not in REVERSE_TABLE:
            continue
        char = REVERSE_TABLE[baudot_bits]
        flag = 1 if flag_bit == "1" else 0
        symbol = (flag, char)
        if symbol not in HUFFMAN_CODES:
            raise ValueError("Symbol {} not in Huffman table.".format(symbol))
        bits += HUFFMAN_CODES[symbol]
    return bits


def huffman_decode_to_content_bits(bitstring, expected_symbol_count=None):
    """
    Decode a Huffman bitstring back into the ORIGINAL 6-bit content_bits
    format (flag+baudot units), reversing huffman_encode_content_bits.
    Returns (content_bits, bits_consumed).

    If expected_symbol_count is given, decoding stops after that many
    symbols. Otherwise decoding continues until the bitstring is
    exhausted or an incomplete trailing code is hit.
    """
    content_bits = ""
    buf = ""
    symbols_decoded = 0
    bits_consumed = 0

    for idx, bit in enumerate(bitstring):
        buf += bit
        if buf in HUFFMAN_REVERSE:
            flag, char = HUFFMAN_REVERSE[buf]
            content_bits += ("1" if flag else "0") + BAUDOT_TABLE[char]
            symbols_decoded += 1
            bits_consumed = idx + 1
            buf = ""
            if expected_symbol_count is not None and symbols_decoded >= expected_symbol_count:
                break

    return content_bits, bits_consumed


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


def build_message_content_bits(message, full_to_short):
    """
    Builds just the message + STOP word portion as a 6-bit bitstring.
    This is the part that gets compressed/Huffman-coded -- the CRC
    trailer is built separately and always stays uncompressed.
    """
    stream = build_6bit_stream(message, full_to_short)
    for ch in STOP_WORD:
        stream.append((ch, False))
    return encode_stream_to_bits(stream)


def build_crc_trailer_bits(content_bits):
    """
    Builds the CRC32 trailer as plain 6-bit chars:
        [111111] [8 nibble-letters] [endoffile]
    Always uncompressed, computed over the raw (pre-compression) content.
    """
    content_bytes = bits_to_bytes(content_bits)
    crc_value = zlib.crc32(content_bytes) & 0xFFFFFFFF
    crc_encoded = crc32_to_nibble_string(crc_value)

    trailer_bits = CRC32_DELIMITER
    for ch in crc_encoded:
        trailer_bits += "0" + BAUDOT_TABLE[ch]
    for ch in "endoffile":
        trailer_bits += "0" + BAUDOT_TABLE[ch]
    return trailer_bits


def build_candidate_payloads(message, full_to_short):
    """
    Builds all three compression candidates for the message content.
    Returns a dict: {"none": bytes, "zlib": bytes, "huffman": bytes}
    plus the raw content_bits (needed for the CRC trailer).

    Note: for "none", the returned bytes are the content-only portion;
    callers must remember that content+trailer get packed TOGETHER (no
    padding gap) in the real file, so the true "none" file size is
    len(header) + ceil((len(content_bits)+len(trailer_bits))/8), not
    simply 1 + len(none_bytes) + len(trailer_bytes) as separate pieces.
    See build_encoded_bytes() for the authoritative packing logic used
    when actually saving.
    """
    content_bits = build_message_content_bits(message, full_to_short)
    content_bytes = bytes(bits_to_bytes(content_bits))

    # --- none: content bytes as-is ---
    none_bytes = content_bytes

    # --- zlib: compress the content bytes ---
    zlib_bytes = zlib.compress(content_bytes, level=9)

    # --- huffman: re-encode the SAME content_bits (flag+baudot units)
    # using the static Huffman table, so it round-trips through the
    # identical content_bits as the other two methods (needed for CRC32
    # to match regardless of which method was chosen).
    huff_bits = huffman_encode_content_bits(content_bits)
    huffman_bytes = bytes(bits_to_bytes(huff_bits))

    candidates = {
        "none": none_bytes,
        "zlib": zlib_bytes,
        "huffman": huffman_bytes,
    }
    return candidates, content_bits


def build_encoded_bytes(message, full_to_short, method="none"):
    """
    Full pipeline for a SPECIFIC method (used by the non-auto encode path).
    method: "none", "zlib", or "huffman"

    Returns the complete file bytes: [header][payload][trailer, plain 6-bit].

    IMPORTANT (none method): content_bits and trailer_bits must be packed
    into bytes TOGETHER as one continuous bitstream, not separately.
    Each is a multiple of 6 bits but not necessarily a multiple of 8, so
    packing them independently would insert padding bits between them --
    breaking 6-bit alignment for the decoder's aligned delimiter search.
    Zlib and Huffman payloads don't have this problem: their payload is
    a different byte representation entirely, and the trailer always
    starts at a fresh byte boundary right after the payload ends.
    """
    content_bits = build_message_content_bits(message, full_to_short)
    trailer_bits = build_crc_trailer_bits(content_bits)

    if method == "none":
        tag = HEADER_TAG_NONE
        # Pack content + trailer together so no padding gap breaks alignment
        combined_bits = content_bits + trailer_bits
        combined_bytes = bits_to_bytes(combined_bits)
        header = make_header_byte(tag)
        return bytes(header) + bytes(combined_bytes)

    elif method == "zlib":
        tag = HEADER_TAG_ZLIB
        payload = zlib.compress(bytes(bits_to_bytes(content_bits)), level=9)
        trailer_bytes = bits_to_bytes(trailer_bits)
    elif method == "huffman":
        tag = HEADER_TAG_HUFFMAN
        huff_bits = huffman_encode_content_bits(content_bits)
        payload = bits_to_bytes(huff_bits)
        trailer_bytes = bits_to_bytes(trailer_bits)
    else:
        raise ValueError("Unknown method: {}".format(method))

    header = make_header_byte(tag)
    return bytes(header) + bytes(payload) + bytes(trailer_bytes)


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

def handle_compression(message, full_to_short, final_filename):
    """
    New 1.7 compression flow. Lets the user pick a specific method,
    or 'Auto' to compare all three and confirm before saving.
    """
    print("\nCompression options:")
    print("  1 = None")
    print("  2 = Zlib")
    print("  3 = Huffman")
    print("  4 = Auto (compare all three, recommend smallest)")
    choice = input("Choose option: ").strip()

    method_map = {"1": "none", "2": "zlib", "3": "huffman"}

    if choice in method_map:
        method = method_map[choice]
        file_bytes = build_encoded_bytes(message, full_to_short, method=method)
        with open(final_filename, "wb") as f:
            f.write(file_bytes)
        print("Saved using '{}' ({} bytes).".format(method, len(file_bytes)))
        return

    if choice != "4":
        print("Invalid option. Defaulting to None.")
        file_bytes = build_encoded_bytes(message, full_to_short, method="none")
        with open(final_filename, "wb") as f:
            f.write(file_bytes)
        print("Saved using 'none' ({} bytes).".format(len(file_bytes)))
        return

    # --- Auto: build all three, compare, ask before saving ---
    candidates, content_bits = build_candidate_payloads(message, full_to_short)
    trailer_bits = build_crc_trailer_bits(content_bits)
    trailer_bytes = bytes(bits_to_bytes(trailer_bits))

    sizes = {name: len(data) for name, data in candidates.items()}

    # "none" packs content+trailer bits together with no padding gap,
    # so its true total size must be computed from the combined bit
    # length, not content-bytes + trailer-bytes added separately.
    none_total = 1 + len(bits_to_bytes(content_bits + trailer_bits))
    zlib_total = 1 + sizes["zlib"] + len(trailer_bytes)
    huffman_total = 1 + sizes["huffman"] + len(trailer_bytes)

    total_sizes = {"none": none_total, "zlib": zlib_total, "huffman": huffman_total}

    best_method = min(total_sizes, key=total_sizes.get)

    print("\nCompression comparison (full file size, incl. header + CRC trailer):")
    for name in ("none", "zlib", "huffman"):
        marker = "  <- smallest" if name == best_method else ""
        print("  {:<10} {} bytes{}".format(name, total_sizes[name], marker))

    save = input("\nSave using '{}'? (y/n): ".format(best_method)).strip().lower()
    chosen_method = best_method if save == "y" else "none"

    if chosen_method != best_method:
        print("Saving with 'none' instead.")

    file_bytes = build_encoded_bytes(message, full_to_short, method=chosen_method)
    with open(final_filename, "wb") as f:
        f.write(file_bytes)
    print("Saved using '{}' ({} bytes).".format(chosen_method, len(file_bytes)))


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
        raw_file_bytes = f.read()

    tag, is_new_format = read_header_tag(raw_file_bytes)

    if is_new_format:
        payload_and_trailer = raw_file_bytes[1:]
        _decode_new_format(payload_and_trailer, tag, short_to_full, expand_abbreviations)
    else:
        _decode_legacy_format(raw_file_bytes, short_to_full, expand_abbreviations)


def _decode_new_format(payload_and_trailer, tag, short_to_full, expand_abbreviations):
    """
    1.7+ format. The trailer (CRC delimiter + nibbles + endoffile) is
    always plain 6-bit and uncompressed, so we locate it by finding
    CRC32_DELIMITER in the bitstring -- but only AFTER decompressing/
    decoding the payload portion, since huffman payloads don't share
    the same bit-width as the trailer.

    Because "none" and "zlib" payloads are 6-bit-aligned like the
    trailer, we can find the delimiter directly in their combined
    bitstream. "huffman" payloads use a different bit format, so we
    decode the huffman portion first (it's self-terminating via the
    STOP_WORD marker) and then treat the remaining bytes as the trailer.
    """
    if tag == HEADER_TAG_NONE:
        bitstring = bytes_to_bits(payload_and_trailer)
        _finish_decode_from_6bit_stream(bitstring, short_to_full, expand_abbreviations,
                                          method_label="none")

    elif tag == HEADER_TAG_ZLIB:
        # We don't know where compressed payload ends and trailer begins
        # by byte offset alone, so we decompress incrementally: zlib
        # streams can be decompressed with a Decompress object that
        # reports unused/leftover bytes after the compressed block ends.
        decompressor = zlib.decompressobj()
        try:
            content_bytes = decompressor.decompress(payload_and_trailer)
            leftover = decompressor.unused_data
        except zlib.error:
            print("Error: could not decompress zlib payload -- file may be corrupted.")
            return

        content_bits = bytes_to_bits(content_bytes)
        trailer_bits = bytes_to_bits(leftover)
        _finish_decode_with_trailer(content_bits, trailer_bits, short_to_full,
                                      expand_abbreviations, method_label="zlib")

    elif tag == HEADER_TAG_HUFFMAN:
        # Decode Huffman symbols one at a time, rebuilding content_bits
        # (the same flag+baudot 6-bit format used everywhere else), and
        # stop once the decoded TEXT ends with STOP_WORD.
        bitstring = bytes_to_bits(payload_and_trailer)
        content_bits, bits_consumed = _huffman_decode_until_stop_word(bitstring, short_to_full)

        if content_bits is None:
            print("Warning: STOP word not found in Huffman payload -- file may be corrupted.")
            return

        # Trailer starts at the next byte boundary after bits_consumed
        trailer_start_byte = (bits_consumed + 7) // 8
        trailer_bytes = payload_and_trailer[trailer_start_byte:]
        trailer_bits = bytes_to_bits(trailer_bytes)

        raw = decode_6bit_chars(content_bits, short_to_full, expand_abbreviations)
        message_only = raw[:-len(STOP_WORD)] if raw.endswith(STOP_WORD) else raw

        _print_crc_and_message(content_bits, trailer_bits, message_only, method_label="huffman")

    else:
        print("Error: unrecognised compression tag in header.")


def _huffman_decode_until_stop_word(bitstring, short_to_full):
    """
    Decode Huffman-coded bits (6-bit flag+baudot symbols) one at a time,
    rebuilding content_bits, stopping once the DECODED TEXT (with
    abbreviations expanded, since STOP_WORD is always literal/unflagged)
    ends with STOP_WORD. Returns (content_bits, bits_consumed) or
    (None, 0) if STOP_WORD is never reached.
    """
    content_bits = ""
    buf = ""
    bits_consumed = 0
    plain_text_check = ""   # tracks literal (flag=0) chars only, for STOP_WORD detection

    for idx, bit in enumerate(bitstring):
        buf += bit
        if buf in HUFFMAN_REVERSE:
            flag, char = HUFFMAN_REVERSE[buf]
            content_bits += ("1" if flag else "0") + BAUDOT_TABLE[char]
            bits_consumed = idx + 1
            buf = ""

            if flag == 0:
                plain_text_check += char
            else:
                plain_text_check = ""  # abbreviation char breaks any pending STOP_WORD match... 
                # (STOP_WORD is always flag=0, so an abbreviation char can't be part of it,
                # but we don't want a partial match to falsely trigger either)

            if plain_text_check.endswith(STOP_WORD):
                return content_bits, bits_consumed

    return None, 0


def _finish_decode_from_6bit_stream(bitstring, short_to_full, expand_abbreviations, method_label):
    """For 'none' payloads: find the CRC delimiter directly in the bitstring."""
    delim_pos = find_aligned_delimiter(bitstring)

    if delim_pos == -1:
        print("Warning: CRC32 delimiter not found -- file may be corrupted.")
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
    _finish_decode_with_trailer(content_bits, trailer_bits, short_to_full,
                                  expand_abbreviations, method_label)


def _finish_decode_with_trailer(content_bits, trailer_bits, short_to_full,
                                  expand_abbreviations, method_label):
    raw = decode_6bit_chars(content_bits, short_to_full, expand_abbreviations)
    message_only = raw[:-len(STOP_WORD)] if raw.endswith(STOP_WORD) else raw
    _print_crc_and_message(content_bits, trailer_bits, message_only, method_label,
                             short_to_full=short_to_full,
                             expand_abbreviations=expand_abbreviations)


def _print_crc_and_message(content_bits, trailer_bits, message_only, method_label,
                             short_to_full=None, expand_abbreviations=False):
    content_bytes = bits_to_bytes(content_bits)
    computed_crc = zlib.crc32(content_bytes) & 0xFFFFFFFF
    computed_display = "{:08x}".format(computed_crc)

    # trailer_bits may or may not include the leading CRC32_DELIMITER
    # (6 bits) depending on the caller -- strip it if present so the
    # nibble/tag decode always starts from the right offset.
    if trailer_bits.startswith(CRC32_DELIMITER):
        trailer_bits = trailer_bits[6:]

    trailer_text = decode_6bit_chars(trailer_bits, {}, False)
    stored_nibbles = trailer_text[:8]
    trailer_tag = trailer_text[8:]

    if all(ch in CHAR_TO_NIBBLE for ch in stored_nibbles):
        stored_crc = nibble_string_to_crc32(stored_nibbles)
        stored_display = "{:08x}".format(stored_crc)
    else:
        stored_crc = None
        stored_display = "(invalid nibbles: '{}')".format(stored_nibbles)

    print("\nCompression method: {}".format(method_label))
    print("CRC32 check:")
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

    # For huffman path, message_only is already the final text (abbreviations
    # were substituted before Huffman coding, so there's nothing further to expand).
    print("\nDecoded message:")
    print(message_only)


def _decode_legacy_format(raw_file_bytes, short_to_full, expand_abbreviations):
    """Fallback for pre-1.7 files with no header byte (old try-zlib-else-raw)."""
    byte_data = raw_file_bytes
    try:
        byte_data = zlib.decompress(byte_data)
    except Exception:
        pass

    bitstring = bytes_to_bits(byte_data)
    delim_pos = find_aligned_delimiter(bitstring)

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
    _finish_decode_with_trailer(content_bits, trailer_bits, short_to_full,
                                  expand_abbreviations, method_label="legacy (pre-1.7)")


# =============================================================================
# CRC32 CHECK MENU FUNCTION
# =============================================================================

def crc32_check(short_to_full=None):
    if short_to_full is None:
        short_to_full = {}
    filename = input("Enter .bin file name: ").strip()
    if not filename.endswith(".bin"):
        filename += ".bin"

    if not os.path.exists(filename):
        print("File not found.")
        return

    with open(filename, "rb") as f:
        raw_bytes = f.read()

    raw_size = len(raw_bytes)
    tag, is_new_format = read_header_tag(raw_bytes)

    if is_new_format:
        method_names = {HEADER_TAG_NONE: "none", HEADER_TAG_ZLIB: "zlib", HEADER_TAG_HUFFMAN: "huffman"}
        method_label = method_names.get(tag, "unknown")
        payload_and_trailer = raw_bytes[1:]

        if tag == HEADER_TAG_NONE:
            bitstring = bytes_to_bits(payload_and_trailer)
            delim_pos = find_aligned_delimiter(bitstring)
            if delim_pos == -1:
                print("\nNo CRC32 delimiter found. File may be corrupted.")
                return
            content_bits = bitstring[:delim_pos]
            trailer_bits = bitstring[delim_pos + 6:]
            decompressed_size = len(payload_and_trailer)

        elif tag == HEADER_TAG_ZLIB:
            decompressor = zlib.decompressobj()
            try:
                content_bytes = decompressor.decompress(payload_and_trailer)
                leftover = decompressor.unused_data
            except zlib.error:
                print("\nError: could not decompress zlib payload -- file may be corrupted.")
                return
            content_bits = bytes_to_bits(content_bytes)
            trailer_bits = bytes_to_bits(leftover)
            decompressed_size = len(content_bytes) + len(leftover)

        elif tag == HEADER_TAG_HUFFMAN:
            bitstring = bytes_to_bits(payload_and_trailer)
            content_bits, bits_consumed = _huffman_decode_until_stop_word(bitstring, short_to_full)
            if content_bits is None:
                print("\nWarning: STOP word not found in Huffman payload.")
                return
            trailer_start_byte = (bits_consumed + 7) // 8
            trailer_bytes = payload_and_trailer[trailer_start_byte:]
            trailer_bits = bytes_to_bits(trailer_bytes)
            decompressed_size = len(content_bits) // 8

        else:
            print("\nUnrecognised compression tag.")
            return

        content_bytes = bits_to_bytes(content_bits)
        computed_crc = zlib.crc32(content_bytes) & 0xFFFFFFFF
        computed_display = "{:08x}".format(computed_crc)

        if trailer_bits.startswith(CRC32_DELIMITER):
            trailer_bits = trailer_bits[6:]

        trailer_text = decode_6bit_chars(trailer_bits, {}, False)
        stored_nibbles = trailer_text[:8]
        trailer_tag = trailer_text[8:]

        if all(ch in CHAR_TO_NIBBLE for ch in stored_nibbles):
            stored_crc = nibble_string_to_crc32(stored_nibbles)
            stored_display = "{:08x}".format(stored_crc)
        else:
            stored_crc = None
            stored_display = "INVALID ({})".format(stored_nibbles)

        content_decoded = decode_6bit_chars(content_bits, {}, False)
        if content_decoded.endswith(STOP_WORD):
            content_decoded = content_decoded[:-len(STOP_WORD)]
        char_count = len(content_decoded)

        if stored_crc is not None and stored_crc == computed_crc:
            print("\n+------------------------------------------------+")
            print("|           CRC32 CHECK PASSED                   |")
            print("+------------------------------------------------+")
            print("  File:               {}".format(filename))
            print("  Compression method: {}".format(method_label))
            print("  CRC32 (stored):     {}".format(stored_display))
            print("  CRC32 (computed):   {}".format(computed_display))
            print("  Trailer tag:        {}".format(trailer_tag))
            print("  File on disk:       {} bytes".format(raw_size))
            print("  Decoded content:    {} bytes".format(decompressed_size))
            print("  Content chars:      {}".format(char_count))
            print("+------------------------------------------------+")
        else:
            print("\n+------------------------------------------------+")
            print("|           CRC32 CHECK FAILED                   |")
            print("+------------------------------------------------+")
            print("  File:               {}".format(filename))
            print("  Compression method: {}".format(method_label))
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
        return

    # ---- Legacy (pre-1.7) format: old zlib-guess method ----------------------
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
    delim_pos = find_aligned_delimiter(bitstring)

    if delim_pos == -1:
        print("\nNo CRC32 delimiter found in this file.")
        print("This file was likely made with a version older than 1.6.")
        print("Returning to main menu.")
        return

    print("\nCRC32 delimiter found (legacy pre-1.7 format).")

    content_bits = bitstring[:delim_pos]
    trailer_bits = bitstring[delim_pos + 6:]

    content_bytes = bits_to_bytes(content_bits)
    computed_crc = zlib.crc32(content_bytes) & 0xFFFFFFFF
    computed_display = "{:08x}".format(computed_crc)

    trailer_text = decode_6bit_chars(trailer_bits, {}, False)
    stored_nibbles = trailer_text[:8]
    trailer_tag = trailer_text[8:]

    if all(ch in CHAR_TO_NIBBLE for ch in stored_nibbles):
        stored_crc = nibble_string_to_crc32(stored_nibbles)
        stored_display = "{:08x}".format(stored_crc)
    else:
        stored_crc = None
        stored_display = "INVALID ({})".format(stored_nibbles)

    content_decoded = decode_6bit_chars(content_bits, {}, False)
    if content_decoded.endswith(STOP_WORD):
        content_decoded = content_decoded[:-len(STOP_WORD)]
    char_count = len(content_decoded)
    bit_count = delim_pos

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

            handle_compression(message, full_to_short, output_name + ".bin")

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
            crc32_check(short_to_full)

        elif choice == "4":
            break

        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()
