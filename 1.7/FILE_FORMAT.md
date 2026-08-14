# Baudot 1.7 -- File Format Specification

This document describes the `.bin` file format produced and read by
`1.7.py`, independent of any specific test case. For real, verified
examples of every part of this format in action, see `TEST_CASES.md`.

---

## 1. Overview

Every `.bin` file is built from three logical pieces, laid out back to
back:

```
+--------------+------------------------------+----------------------+
| HEADER BYTE  |  PAYLOAD                      |  TRAILER             |
| (1 byte)     |  (compressed/encoded content) |  (plain 6-bit, always|
|              |                                |  uncompressed)       |
+--------------+------------------------------+----------------------+
```

- **Header byte** -- tells the decoder which of three methods was used
  to store the payload: none, zlib, or Huffman.
- **Payload** -- the actual message (plus a literal `stop` marker),
  encoded according to whichever method the header byte specifies.
- **Trailer** -- a CRC32 checksum of the message, always stored in
  plain, uncompressed 6-bit units, regardless of which method was used
  for the payload. This lets the file's integrity be verified
  independently of how the payload itself was packed.

Files made by version 1.6 and earlier have **no header byte** at all
-- the decoder detects this and falls back to the old "try zlib, else
assume raw" guessing method. See Section 7.

---

## 2. The Baudot Character Table

The format uses a modified 5-bit ITA2 ("Baudot") letters-mode table.
Three of the original digit codes have been repurposed as punctuation:

| Char | Baudot (5 bits) | Char | Baudot (5 bits) | Char | Baudot (5 bits) |
|---|---|---|---|---|---|
| `a` | `00011` | `k` | `01111` | `u` | `00111` |
| `b` | `11001` | `l` | `10010` | `v` | `11110` |
| `c` | `01110` | `m` | `11100` | `w` | `10011` |
| `d` | `01001` | `n` | `01100` | `x` | `11101` |
| `e` | `00001` | `o` | `11000` | `y` | `10101` |
| `f` | `01101` | `p` | `10110` | `z` | `10001` |
| `g` | `11010` | `q` | `10111` | `(space)` | `00100` |
| `h` | `10100` | `r` | `01010` | `.` | `00010` |
| `i` | `00110` | `s` | `00101` | `-` | `11011` |
| `j` | `01011` | `t` | `10000` | `!` | `11111` |

**Note on `.`, `-`, and `!`:** these replaced the original digit codes
`1`, `2`, `3`. As a consequence, the modified table has **no way to
encode digits** -- messages containing `0-9` will be rejected by the
input validator.

**Note on `!`:** the Baudot bits for `!` (`11111`) are the same 5 bits
used by the reserved CRC32 delimiter (Section 5) -- but the delimiter
is only ever matched with its flag bit set to `1`, while a user-typed
`!` always has flag `0`. These are different 6-bit units even though
they share the same last 5 bits. See Section 5 for why this can never
collide.

---

## 3. The 6-Bit Unit

Every character in the message content is stored as **6 bits**, not
5. The extra bit is a flag used for abbreviation marking:

```
   bit 5         bits 4-0
 +-------+---------------------+
 | FLAG  |    BAUDOT CODE      |
 +-------+---------------------+
   1 bit         5 bits
```

- **Flag = 0**: this is a normal, literal character.
- **Flag = 1**: this character is part of an abbreviation shortcode
  (see Section 4).

### Example: the letter `h`, plain

```
Flag: 0
Baudot: 10100  (h)
6-bit unit: 010100
```

### Example: the letter `h`, as part of an abbreviation

```
Flag: 1
Baudot: 10100  (h)
6-bit unit: 110100
```

Both units decode to the character `h` -- the flag bit is what tells
the decoder whether to treat it as literal text or as part of a
shortcode lookup.

---

## 4. Abbreviations

The program can optionally load a `abv.txt` file (format:
`shortcode=fullword`, one per line) to substitute common full words
with shorter codes before encoding.

### How substitution works

1. The message is tokenised into words and non-words (spaces,
   punctuation).
2. Each word is checked against the abbreviation table. If a match is
   found, the word is replaced with its shortcode.
3. Every character of a substituted shortcode is encoded with
   **flag = 1**. Everything else (unmatched words, spaces,
   punctuation) is encoded with **flag = 0**.

### Example

If `abv.txt` contains `ab=about`, the word "about" in a message
becomes the two characters `a` `b`, both flagged:

```
"about" (5 chars, flag=0 each)  -->  "ab" (2 chars, flag=1 each)

  a         b
100011    111001
 ^                    ^
 flag=1 (abv)          flag=1 (abv)
 baudot for 'a'         baudot for 'b'
```

### Decoding abbreviations

The decoder reads flag bits as it goes. A **run of consecutive
flag=1 characters** is treated as one shortcode token. The run ends
as soon as a flag=0 character appears. The collected shortcode is
then looked up in the abbreviation table:

- If **expansion is enabled** and the shortcode is recognised, it's
  replaced with the full word.
- If expansion is disabled, or the shortcode isn't recognised, it's
  shown as `[ABV:shortcode]` so the raw data is still visible.

---

## 5. The Reserved CRC32 Delimiter

The 6-bit unit `111111` (flag=1 + Baudot `11111`) is **reserved** and
marks the boundary between the message content and the CRC32 trailer.

### Why this pattern can never appear in real content

- Abbreviation shortcodes only ever contain the letters `a`-`z`
  (never `!`), so a flag=1 unit can never have Baudot bits `11111`.
- A user-typed `!` always has flag=0, giving the unit `011111` --
  different from the reserved `111111`.

So no legitimate 6-bit unit, at a proper 6-bit-aligned position, can
ever equal `111111` by accident.

### A subtlety: aligned vs. unaligned search

Searching for the bit pattern `111111` **anywhere** in a raw
bitstream (not just at 6-bit-aligned offsets) is unsafe: two adjacent,
completely ordinary characters can coincidentally produce the sequence
`111111` spanning across their shared boundary, even though neither
character is the reserved unit. For example, a character ending in
`11` followed by a character starting with `1111` would create a false
positive if searched byte-by-byte or bit-by-bit without regard to
alignment.

**The decoder must only test for the delimiter at positions that are
multiples of 6 bits from the start of the payload.** At those aligned
positions, the delimiter is unambiguous, because it is only ever
written by the encoder at an aligned position in the first place.

---

## 6. The Trailer

Immediately after the delimiter, the trailer always contains, in
plain uncompressed 6-bit units:

```
[111111]  [8 nibble-letters]  [e][n][d][o][f][f][i][l][e]
 delim      CRC32, as letters       literal word "endoffile"
            'a'-'p'
```

### CRC32 nibble encoding

The CRC32 value is a 32-bit integer. Rather than adding digit
characters (`0`-`9`) to the Baudot table just to store it as hex, the
value is split into 8 nibbles (4 bits each) and each nibble (0-15) is
written as a letter `a`-`p`:

| Nibble value | Letter | Nibble value | Letter |
|---|---|---|---|
| 0 | a | 8 | i |
| 1 | b | 9 | j |
| 2 | c | 10 | k |
| 3 | d | 11 | l |
| 4 | e | 12 | m |
| 5 | f | 13 | n |
| 6 | g | 14 | o |
| 7 | h | 15 | p |

The 8 letters are written most-significant nibble first. For example,
a CRC32 of `0x7e3828db` becomes:

```
0x7 0xe 0x3 0x8 0x2 0x8 0xd 0xb
 h   o   d   i   c   i   n   l
```
`hodicinl`

Each of these letters is then written as a normal flag=0, 6-bit unit,
just like any other literal character.

### What the CRC32 covers

The CRC32 is computed over the **content bytes** -- the message plus
the literal word `stop` appended at the end, packed into bytes --
**before** any compression is applied. This is the same value
regardless of which of the three payload methods (none/zlib/huffman)
was used, which means:

- CRC32 verification works identically no matter how the payload was
  stored.
- Switching between methods never changes what the CRC32 is checking.

---

## 7. The Header Byte and the Three Payload Methods

The very first byte of a 1.7 file identifies the compression method:

```
   bit 7   bit 6    bits 5-0
 +-------+-------+------------------+
 |  tag  |  tag  |   unused (0)     |
 +-------+-------+------------------+
```

| Tag (binary) | Tag (decimal) | Method |
|---|---|---|
| `00` | 0 | none |
| `01` | 1 | zlib |
| `10` | 2 | huffman |
| `11` | 3 | *(reserved, unused)* |

If the low 6 bits of the header byte are **not** all zero, or the tag
is `11`, the decoder treats the file as **not having a valid 1.7
header** and falls back to the legacy detection method (Section 9).

### Method 0: None

The content bits (message + `stop`, all as flag+Baudot 6-bit units)
are packed directly into bytes, **together with the trailer bits**, as
one continuous bitstream, then written as-is.

```
[header=0x00] [content_bits + trailer_bits, packed together as bytes]
```

**Important:** content and trailer must be packed together, not
separately. Since each 6-bit unit is a multiple of 6 bits but not
necessarily a multiple of 8, packing content and trailer into bytes
independently would insert padding bits between them -- breaking the
6-bit alignment the decoder relies on to safely find the delimiter
(see Section 5). Packing them as one combined bitstream avoids this.

### Method 1: Zlib

The content bytes (message + `stop`, packed to bytes on their own)
are compressed with `zlib.compress()`. The trailer is packed to bytes
separately and appended after the compressed payload.

```
[header=0x40] [zlib.compress(content_bytes)] [trailer_bytes]
```

To decode, the decoder uses `zlib.decompressobj()`, which can report
exactly how many bytes were consumed by the compressed stream via its
`unused_data` attribute -- the leftover bytes are the trailer, with no
ambiguity about where the payload ends.

### Method 2: Huffman

Content bits are re-encoded using a **static Huffman table**, built
once at program start from approximate English letter frequency. The
Huffman symbols are the same 6-bit (flag, character) units used
everywhere else -- not plain characters -- so a message's abbreviation
flags are preserved through Huffman coding, and CRC32 (computed over
the original 6-bit content) matches regardless of whether Huffman was
used.

```
[header=0x80] [huffman-encoded content bits, packed to bytes] [trailer_bytes]
```

Because Huffman codes are variable-length, the decoder doesn't know
in advance how many bits the payload occupies. Instead, it decodes
symbol by symbol and watches the running decoded text for the
literal word `stop`. Once `stop` is seen, decoding stops, and the
trailer starts at the next byte boundary after that point.

**The Huffman table itself is never stored in the file.** Both the
encoder and decoder use an identical, hardcoded table, so the
"huffman" method costs nothing beyond the 1-byte header -- there's no
table transmission overhead the way there would be with a
per-message/adaptive table.

---

## 8. Choosing a Method: the Auto / Compare Flow

When saving, the program can either use a specific method directly,
or run "Auto" mode, which:

1. Builds all three candidate payloads for the same message.
2. Computes the true total file size for each (header + payload +
   trailer, accounting for the none-method's combined bit-packing).
3. Displays a comparison and recommends the smallest.
4. Still asks for confirmation before saving -- if declined, falls
   back to the "none" method.

No method is "best" in general -- it depends entirely on the message:

- **None** wins for short, non-repetitive, or letter-frequency-atypical
  messages (e.g. lots of rare letters like `q`, `z`, `x`, `j`).
- **Zlib** wins for long, highly repetitive text, where its LZ77
  dictionary matching can exploit repeated substrings.
- **Huffman** wins for typical English text of small-to-medium length,
  where zlib's fixed per-file overhead (roughly 8 bytes) outweighs
  what little repetition there is to exploit, but the letter
  frequency is close enough to "normal" English for the static table
  to pay off.

---

## 9. Backward Compatibility (Legacy Pre-1.7 Files)

Files made with version 1.6 or earlier have no header byte. Detecting
these:

1. Attempt `zlib.decompress()` on the raw file bytes.
   - If it succeeds, the file was zlib-compressed (1.6-style).
   - If it fails, assume the file is raw, uncompressed content.
2. Search for the CRC32 delimiter at 6-bit-aligned positions, exactly
   as with 1.7 files.
3. Decode content and trailer the same way as the "none" method.

This fallback means **any file made by 1.6 remains fully readable by
1.7** without modification.

---

## 10. Full Worked Example (Summary Diagram)

```
Message: "about the account"
Method:  huffman

Step 1 -- Abbreviation substitution (using abv.txt):
  "about"   -> "ab"    (flag=1 for both chars)
  "the"     -> "t"     (flag=1)
  "account" -> "acc"   (flag=1 for all three chars)
  (spaces stay flag=0)

Step 2 -- Build content_bits (6-bit units):
  a(1) b(1) _(0) t(1) _(0) a(1) c(1) c(1) s(0)t(0)o(0)p(0)
  [literal "stop" appended, always flag=0]

Step 3 -- Compute CRC32 over content_bits, packed to bytes.
  e.g. CRC32 = 0x3e523828
  -> nibble letters: "dfcfcdci" (example, not necessarily exact)

Step 4 -- Encode content_bits with the static Huffman table.
  Each (flag, char) symbol -> its Huffman code (variable length)

Step 5 -- Assemble the file:
  [header: 0x80 (huffman tag)]
  [huffman-encoded payload bytes]
  [trailer: 111111 + nibble letters + "endoffile", packed to bytes]

Result: a compact .bin file that is self-describing (header byte),
        integrity-checked (CRC32 trailer), and abbreviation-aware
        (flag bits preserved through compression).
```

---

## 11. Quick Reference Card

```
FILE = HEADER_BYTE + PAYLOAD + TRAILER

HEADER_BYTE (1 byte):
    bits 7-6 = method tag (00=none, 01=zlib, 10=huffman, 11=reserved)
    bits 5-0 = always 0

PAYLOAD (method-dependent):
    none:    content_bits, packed together WITH the trailer (no gap)
    zlib:    zlib.compress(content_bytes)
    huffman: static-table Huffman encoding of content_bits

TRAILER (always plain 6-bit, uncompressed):
    111111              <- reserved delimiter (6-bit aligned only)
    8 nibble-letters     <- CRC32, as letters 'a'-'p'
    "endoffile"          <- literal closing tag

CONTENT_BITS = message (with abbreviations substituted) + "stop",
               each character as a 6-bit (flag, baudot) unit

CRC32 = zlib.crc32() over content_bits packed to bytes,
        computed BEFORE compression, identical across all 3 methods
```
