# Changelog

## Version 1.7

### New Header Byte
- Every file now starts with 1 header byte identifying how it was encoded
- Top 2 bits are a compression tag:
  - `00` = none (raw content bytes)
  - `01` = zlib (existing DEFLATE compression)
  - `10` = huffman (new static Huffman table)
  - `11` = reserved
- The decoder reads this tag directly instead of guessing via
  try/except zlib.decompress() as in 1.6 and earlier
- Files with no valid 1.7 header are still readable: the decoder
  automatically falls back to the old 1.6-style guessing method

### Huffman Compression (New Method)
- Added a static Huffman table built from approximate English letter
  frequency, covering the full 6-bit symbol space (every letter/space/
  punctuation combined with both abbreviation flag states)
- The table is baked into the program on both the encoding and decoding
  side, so no table needs to be stored in the file -- the huffman method
  costs nothing beyond the 1-byte header
- Huffman re-encodes the exact same underlying 6-bit content used by
  the "none" and "zlib" methods, so CRC32 verification is identical
  and interchangeable across all three methods

### Compression Menu Overhaul
- The old single yes/no compression prompt has been replaced with:
  ```
  1 = None
  2 = Zlib
  3 = Huffman
  4 = Auto (compare all three, recommend smallest)
  ```
- Choosing a method directly (1-3) encodes and saves immediately
- Choosing Auto (4) builds all three candidates, shows their sizes
  side by side, marks the smallest, and still asks for confirmation
  before saving -- matching the "ask before saving" behaviour from 1.6

### CRC32 Trailer Placement
- The CRC32 delimiter, CRC nibbles, and "endoffile" trailer are now
  always stored uncompressed, after the (possibly compressed) content
  payload -- regardless of which compression method was used
- This keeps the trailer readable/verifiable independent of the
  compression method, and means CRC32 always verifies the same
  underlying message content

### CRC32 Check Menu (Option 3) -- Updated for 1.7
- Now recognises the new header byte and reports which compression
  method (none/zlib/huffman) was used for the file being checked
- Still falls back cleanly to the old legacy detection method for
  pre-1.7 files

### Backward Compatibility
- 1.6 and earlier `.bin` files (no header byte, single-method
  compression) continue to decode correctly through the legacy
  fallback path in both the Decode and CRC32 Check menus

---

## Version 1.6

### Baudot Table Changes
- Replaced `'1': '00010'` with `'.': '00010'` (period / full stop)
- Replaced `'2': '11011'` with `'-': '11011'` (hyphen / dash)
- Replaced `'3': '11111'` with `'!': '11111'` (exclamation mark)

### 6-bit Encoding
- Each character is now stored as 6 bits instead of 5
- Bit 5 (leftmost / MSB) is a flag bit:
  - `0` = normal literal character
  - `1` = character is part of an abbreviation shortcode
- Bits 4-0 (rightmost 5) remain the standard 5-bit Baudot code

### Abbreviation Support
- Added `abv.txt` lookup system (format: `shortcode=fullword`, one per line)
- Encoder tokenises input and replaces known full words with their shortcode
- Shortcode characters are marked with flag bit = 1 in the bitstream
- Decoder reads flag=1 runs as abbreviation tokens and expands them back
- Abbreviation expansion can be toggled on or off at decode time
- Unrecognised shortcodes are shown as `[ABV:shortcode]` markers

### Reserved CRC32 Delimiter
- The 6-bit pattern `111111` (flag=1 + Baudot bits `11111`) is reserved
- This pattern cannot appear naturally in user content:
  - Users cannot set the flag bit themselves
  - Abbreviation shortcodes only contain letters `a-z`, never `!`
- The delimiter marks the boundary between encoded content and the CRC32 trailer

### CRC32 Integrity Checking
- A CRC32 checksum is computed over the encoded content bytes (message + STOP word)
- The 32-bit CRC value is stored as 8 nibble-letters (`a`-`p`) after the delimiter:
  - Nibble 0-15 maps to letters `a`-`p` (avoids needing digits 0-9 in the Baudot table)
  - Stored most-significant nibble first
- The word `endoffile` is appended after the CRC nibbles as a closing tag
- File structure in the bitstream:
  ```
  [encoded message] [stop] [111111] [8 nibble-letters] [endoffile]
  ```
- On decode, CRC32 is recomputed and compared against the stored value
- PASS/FAIL result is printed before the message is shown
- If CRC fails the user is asked whether to decode anyway

### Encoder Preview
- Before saving, the encoder prints a table of all abbreviation replacements
  that will be applied to the message

### Example Files
- `test.bin` — a pre-encoded `.bin` file demonstrating the 1.6 format in action
- `text.txt` — the plain text file used to generate `test.bin`
- These can be used to verify the encoder and decoder are working correctly

### Backward Compatibility
- If a file has no `111111` delimiter the decoder falls back to the old
  STOP-word-only method with a warning, allowing older files to still be read

### CRC32 Check Menu (Option 3)
- Added a dedicated CRC32 Check option to the main menu
- User enters a .bin filename to inspect
- If no CRC32 delimiter is found the program reports the file is pre-1.6 and returns to the main menu
- If the delimiter is found a full integrity check is performed and results are displayed:
  - CRC PASS: displays a summary box showing the CRC32 value, file size on disk, whether the file is compressed, decompressed size, compression ratio, content bit count, and character count
  - CRC FAIL: displays the stored CRC32 vs the computed CRC32 and gives the user the option to return to the main menu or exit the program

---

## Version 1.54

- Added CRC32 trailer using `111111` in-stream delimiter (nibble-letter encoding a-p)
- Updated Baudot character table

## Version 1.53

- Abbreviation support added (abv.txt lookup)
- Improved encoding pipeline

## Version 1.52

- Bug fixes and encoding stability improvements

## Version 1.51

- Initial 1.5x series: text file input support added

## Version 1.4

- Compression statistics added (original vs compressed size, space saved/lost)

## Version 1.3

- Optional zlib lossless compression added
- Transparent decompression on decode

## Version 1.2

- Initial public version
- Basic 5-bit Baudot encode and decode
- STOP word framing
- Text file input with character validation
