# Baudot 1.7 -- Test Case Reference

This document walks through every file in `test_files/`, showing the exact bit-level structure, the header byte, the CRC32 trailer, and the decoded result for each one. It is generated directly from the outputs of `1.7.py`, so every value shown here is real, verified output -- not a hand-written example.

For a description of the file format itself (independent of these specific test cases), see **FILE_FORMAT.md**.

## Summary Table

| # | Case | Method | Message (truncated) | Size | CRC32 |
|---|---|---|---|---|---|
| 01 | `01_short_none` | none | hi there | 22 B | PASS |
| 02 | `02_short_zlib` | zlib | hi there | 30 B | PASS |
| 03 | `03_short_huffman` | huffman | hi there | 21 B | PASS |
| 04 | `04_abbreviations_none` | none | about the account and the abbreviation | 31 B | PASS |
| 05 | `05_abbreviations_huffman` | huffman | about the account and the abbreviation | 33 B | PASS |
| 06 | `06_punctuation_none` | none | wait - is this ok. really! yes. | 40 B | PASS |
| 07 | `07_long_repetitive_none` | none | the quick brown fox jumps over the la... | 239 B | PASS |
| 08 | `08_long_repetitive_zlib` | zlib | the quick brown fox jumps over the la... | 144 B | PASS |
| 09 | `09_long_repetitive_huffman` | huffman | the quick brown fox jumps over the la... | 214 B | PASS |
| 10 | `10_adversarial_none` | none | qzjxqzjxqzjx | 27 B | PASS |
| 11 | `11_adversarial_huffman` | huffman | qzjxqzjxqzjx | 33 B | PASS |
| 12 | `12_minimal_none` | none | a | 19 B | PASS |
| 13 | `13_skewed_huffman` | huffman | eeeeeeeeee teeeee | 24 B | PASS |
| 14 | `14_skewed_none` | none | eeeeeeeeee teeeee | 31 B | PASS |
| 15 | `15_mixed_none` | none | about the quick brown fox and the acc... | 67 B | PASS |
| 16 | `16_mixed_zlib` | zlib | about the quick brown fox and the acc... | 79 B | PASS |
| 17 | `17_mixed_huffman` | huffman | about the quick brown fox and the acc... | 65 B | PASS |
| 18 | `18_legacy_format` | legacy (pre-1.7, detected via fallback) | this is a legacy format file made bef... | 52 B | PASS |
| 19 | `19_corrupted_file` | none | this file will be deliberately corrup... | 48 B | **FAIL** |

## Size Comparison -- Same Message, Different Methods

These groups encode the *exact same message* with different compression methods, so you can see directly which method wins for each kind of input.

### Short everyday message

```
none      #############################...........   22 bytes
zlib      ########################################   30 bytes
huffman   ############################............   21 bytes
```

### Message with abbreviations

```
none      #####################################...   31 bytes
huffman   ########################################   33 bytes
```

### Long, highly repetitive text

```
none      ########################################  239 bytes
zlib      ########################................  144 bytes
huffman   ###################################.....  214 bytes
```

### Adversarial (rare letters: q, z, j, x)

```
none      ################################........   27 bytes
huffman   ########################################   33 bytes
```

### Skewed frequency (mostly 'e' and 't')

```
none      ########################################   31 bytes
huffman   ##############################..........   24 bytes
```

### Mixed: abbreviations + punctuation

```
none      #################################.......   67 bytes
zlib      ########################################   79 bytes
huffman   ################################........   65 bytes
```

---

## Detailed Case-by-Case Breakdown

### Case 01: Short message, no compression

**File:** `01_short_none.bin`  
**Message:** `hi there`  
**Method:** none  
**File size:** 22 bytes

> Simplest possible case: a short message with no abbreviations, stored with the 'none' method. Good starting point for reading the bit layout.

**Full hex dump:**
```
00506130a854185bf3065993c13cb04c
25834d192040
```

**Header byte:** `00000000` (binary) = `0x00` (hex)  
**Tag bits:** `00` -> **none**

**Payload encoding:** raw 6-bit units, byte-packed directly

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `010100` | 0 | `10100` | `h` |
| 6 | `000110` | 0 | `00110` | `i` |
| 12 | `000100` | 0 | `00100` | `(space)` |
| 18 | `110000` | **1** (abv) | `10000` | `t` |
| 24 | `101010` | **1** (abv) | `01010` | `r` |
| 30 | `000101` | 0 | `00101` | `s` |
| 36 | `010000` | 0 | `10000` | `t` |
| 42 | `011000` | 0 | `11000` | `o` |
| 48 | `010110` | 0 | `10110` | `p` |

**Content bits (raw, space-separated every 6 bits):**
```
010100 000110 000100 110000 101010 000101 010000 011000 010110
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 001100 000110 010110 011001 001111 000001 001111 001011 000001 001100 001001 011000 001101 001101 000110 010010 000001 000000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `nipbkekj`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `d8f1a4a9`
- Computed: `d8f1a4a9`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
hi there
```
**Decoded message (raw shortcodes, not expanded):**
```
hi [ABV:tr]
```

---

### Case 02: Short message, zlib compression

**File:** `02_short_zlib.bin`  
**Message:** `hi there`  
**Method:** zlib  
**File size:** 30 bytes

> Same message as case 01, but forced through zlib. Demonstrates zlib's fixed overhead making a short message LARGER than 'none'.

**Full hex dump:**
```
4078da0b48345811221101000991024e
fcc19664f04f2c130960d3464810
```

**Header byte:** `01000000` (binary) = `0x40` (hex)  
**Tag bits:** `01` -> **zlib**

**Payload encoding:** zlib.compress() over the raw 6-bit content bytes

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `010100` | 0 | `10100` | `h` |
| 6 | `000110` | 0 | `00110` | `i` |
| 12 | `000100` | 0 | `00100` | `(space)` |
| 18 | `110000` | **1** (abv) | `10000` | `t` |
| 24 | `101010` | **1** (abv) | `01010` | `r` |
| 30 | `000101` | 0 | `00101` | `s` |
| 36 | `010000` | 0 | `10000` | `t` |
| 42 | `011000` | 0 | `11000` | `o` |
| 48 | `010110` | 0 | `10110` | `p` |

**Content bits (raw, space-separated every 6 bits):**
```
010100 000110 000100 110000 101010 000101 010000 011000 010110 00
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 001100 000110 010110 011001 001111 000001 001111 001011 000001 001100 001001 011000 001101 001101 000110 010010 000001 0000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `nipbkekj`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `d8f1a4a9`
- Computed: `d8f1a4a9`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
hi there
```
**Decoded message (raw shortcodes, not expanded):**
```
hi [ABV:tr]
```

---

### Case 03: Short message, huffman compression

**File:** `03_short_huffman.bin`  
**Message:** `hi there`  
**Method:** huffman  
**File size:** 21 bytes

> Same message as case 01 and 02, but with the static Huffman table. Typically smaller than both 'none' and 'zlib' for short everyday text.

**Full hex dump:**
```
80f1d9290fe22afcc19664f04f2c1309
60d3464810
```

**Header byte:** `10000000` (binary) = `0x80` (hex)  
**Tag bits:** `10` -> **huffman**

**Payload encoding:** static Huffman table over 6-bit (flag,char) symbols

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `010100` | 0 | `10100` | `h` |
| 6 | `000110` | 0 | `00110` | `i` |
| 12 | `000100` | 0 | `00100` | `(space)` |
| 18 | `110000` | **1** (abv) | `10000` | `t` |
| 24 | `101010` | **1** (abv) | `01010` | `r` |
| 30 | `000101` | 0 | `00101` | `s` |
| 36 | `010000` | 0 | `10000` | `t` |
| 42 | `011000` | 0 | `11000` | `o` |
| 48 | `010110` | 0 | `10110` | `p` |

**Content bits (raw, space-separated every 6 bits):**
```
010100 000110 000100 110000 101010 000101 010000 011000 010110
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 001100 000110 010110 011001 001111 000001 001111 001011 000001 001100 001001 011000 001101 001101 000110 010010 000001 0000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `nipbkekj`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `d8f1a4a9`
- Computed: `d8f1a4a9`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
hi there
```
**Decoded message (raw shortcodes, not expanded):**
```
hi [ABV:tr]
```

---

### Case 04: Message using abbreviations

**File:** `04_abbreviations_none.bin`  
**Message:** `about the account and the abbreviation`  
**Method:** none  
**File size:** 31 bytes

> Uses several words that exist in abv.txt ('about'->'ab', 'the'->'t', 'account'->'acc', 'abbreviation'->'abbn', 'and'->'es'). Shows the abbreviation flag bit (bit 5 of each 6-bit unit) set to 1 for shortcode characters.

**Full hex dump:**
```
008f9130123bae121944c048f9e6c150
616fc960d38918e18130960d346481
```

**Header byte:** `00000000` (binary) = `0x00` (hex)  
**Tag bits:** `00` -> **none**

**Payload encoding:** raw 6-bit units, byte-packed directly

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `100011` | **1** (abv) | `00011` | `a` |
| 6 | `111001` | **1** (abv) | `11001` | `b` |
| 12 | `000100` | 0 | `00100` | `(space)` |
| 18 | `110000` | **1** (abv) | `10000` | `t` |
| 24 | `000100` | 0 | `00100` | `(space)` |
| 30 | `100011` | **1** (abv) | `00011` | `a` |
| 36 | `101110` | **1** (abv) | `01110` | `c` |
| 42 | `101110` | **1** (abv) | `01110` | `c` |
| 48 | `000100` | 0 | `00100` | `(space)` |
| 54 | `100001` | **1** (abv) | `00001` | `e` |
| 60 | `100101` | **1** (abv) | `00101` | `s` |
| 66 | `000100` | 0 | `00100` | `(space)` |
| 72 | `110000` | **1** (abv) | `10000` | `t` |
| 78 | `000100` | 0 | `00100` | `(space)` |
| 84 | `100011` | **1** (abv) | `00011` | `a` |
| 90 | `111001` | **1** (abv) | `11001` | `b` |
| 96 | `111001` | **1** (abv) | `11001` | `b` |
| 102 | `101100` | **1** (abv) | `01100` | `n` |
| 108 | `000101` | 0 | `00101` | `s` |
| 114 | `010000` | 0 | `10000` | `t` |
| 120 | `011000` | 0 | `11000` | `o` |
| 126 | `010110` | 0 | `10110` | `p` |

**Content bits (raw, space-separated every 6 bits):**
```
100011 111001 000100 110000 000100 100011 101110 101110 000100 100001 100101 000100 110000 000100 100011 111001 111001 101100 000101 010000 011000 010110
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 001001 011000 001101 001110 001001 000110 001110 000110 000001 001100 001001 011000 001101 001101 000110 010010 000001
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `dofcdici`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `3e523828`
- Computed: `3e523828`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
about the account and the abbreviation
```
**Decoded message (raw shortcodes, not expanded):**
```
[ABV:ab] [ABV:t] [ABV:acc] [ABV:es] [ABV:t] [ABV:abbn]
```

---

### Case 05: Abbreviations + huffman

**File:** `05_abbreviations_huffman.bin`  
**Message:** `about the account and the abbreviation`  
**Method:** huffman  
**File size:** 33 bytes

> Same message as case 04, compressed with Huffman. Demonstrates that the abbreviation flag bit survives Huffman re-encoding, since Huffman symbols are (flag, char) pairs, not just chars.

**Full hex dump:**
```
806f70b255bdc5c6b9c8d92adee0e0f9
fc4540fc960d38918e18130960d34648
10
```

**Header byte:** `10000000` (binary) = `0x80` (hex)  
**Tag bits:** `10` -> **huffman**

**Payload encoding:** static Huffman table over 6-bit (flag,char) symbols

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `100011` | **1** (abv) | `00011` | `a` |
| 6 | `111001` | **1** (abv) | `11001` | `b` |
| 12 | `000100` | 0 | `00100` | `(space)` |
| 18 | `110000` | **1** (abv) | `10000` | `t` |
| 24 | `000100` | 0 | `00100` | `(space)` |
| 30 | `100011` | **1** (abv) | `00011` | `a` |
| 36 | `101110` | **1** (abv) | `01110` | `c` |
| 42 | `101110` | **1** (abv) | `01110` | `c` |
| 48 | `000100` | 0 | `00100` | `(space)` |
| 54 | `100001` | **1** (abv) | `00001` | `e` |
| 60 | `100101` | **1** (abv) | `00101` | `s` |
| 66 | `000100` | 0 | `00100` | `(space)` |
| 72 | `110000` | **1** (abv) | `10000` | `t` |
| 78 | `000100` | 0 | `00100` | `(space)` |
| 84 | `100011` | **1** (abv) | `00011` | `a` |
| 90 | `111001` | **1** (abv) | `11001` | `b` |
| 96 | `111001` | **1** (abv) | `11001` | `b` |
| 102 | `101100` | **1** (abv) | `01100` | `n` |
| 108 | `000101` | 0 | `00101` | `s` |
| 114 | `010000` | 0 | `10000` | `t` |
| 120 | `011000` | 0 | `11000` | `o` |
| 126 | `010110` | 0 | `10110` | `p` |

**Content bits (raw, space-separated every 6 bits):**
```
100011 111001 000100 110000 000100 100011 101110 101110 000100 100001 100101 000100 110000 000100 100011 111001 111001 101100 000101 010000 011000 010110
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 001001 011000 001101 001110 001001 000110 001110 000110 000001 001100 001001 011000 001101 001101 000110 010010 000001 0000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `dofcdici`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `3e523828`
- Computed: `3e523828`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
about the account and the abbreviation
```
**Decoded message (raw shortcodes, not expanded):**
```
[ABV:ab] [ABV:t] [ABV:acc] [ABV:es] [ABV:t] [ABV:abbn]
```

---

### Case 06: All punctuation characters

**File:** `06_punctuation_none.bin`  
**Message:** `wait - is this ok. really! yes.`  
**Method:** none  
**File size:** 40 bytes

> Exercises all three punctuation characters added in the modified Baudot table: period (.), hyphen (-), and exclamation mark (!). Note '!' is Baudot bits 11111 with flag=0 -- distinct from the reserved CRC32 delimiter, which is the SAME Baudot bits but flag=1.

**Full hex dump:**
```
00cfd11b1061444141851183c210a043
49255f1150450854185bf30d19269c51
604c25834d192040
```

**Header byte:** `00000000` (binary) = `0x00` (hex)  
**Tag bits:** `00` -> **none**

**Payload encoding:** raw 6-bit units, byte-packed directly

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `110011` | **1** (abv) | `10011` | `w` |
| 6 | `111101` | **1** (abv) | `11101` | `x` |
| 12 | `000100` | 0 | `00100` | `(space)` |
| 18 | `011011` | 0 | `11011` | `-` |
| 24 | `000100` | 0 | `00100` | `(space)` |
| 30 | `000110` | 0 | `00110` | `i` |
| 36 | `000101` | 0 | `00101` | `s` |
| 42 | `000100` | 0 | `00100` | `(space)` |
| 48 | `010000` | 0 | `10000` | `t` |
| 54 | `010100` | 0 | `10100` | `h` |
| 60 | `000110` | 0 | `00110` | `i` |
| 66 | `000101` | 0 | `00101` | `s` |
| 72 | `000100` | 0 | `00100` | `(space)` |
| 78 | `011000` | 0 | `11000` | `o` |
| 84 | `001111` | 0 | `01111` | `k` |
| 90 | `000010` | 0 | `00010` | `.` |
| 96 | `000100` | 0 | `00100` | `(space)` |
| 102 | `001010` | 0 | `01010` | `r` |
| 108 | `000001` | 0 | `00001` | `e` |
| 114 | `000011` | 0 | `00011` | `a` |
| 120 | `010010` | 0 | `10010` | `l` |
| 126 | `010010` | 0 | `10010` | `l` |
| 132 | `010101` | 0 | `10101` | `y` |
| 138 | `011111` | 0 | `11111` | `!` |
| 144 | `000100` | 0 | `00100` | `(space)` |
| ... | *(8 more rows omitted)* | | | |

**Content bits (raw, space-separated every 6 bits):**
```
110011 111101 000100 011011 000100 000110 000101 000100 010000 010100 000110 000101 000100 011000 001111 000010 000100 001010 000001 000011 010010 010010 010101 011111 000100 010101 000001 000101 0000 ... (truncated)
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 001100 001101 000110 010010 011010 011100 010100 010110 000001 001100 001001 011000 001101 001101 000110 010010 000001 000000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `nfilgmhp`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `d58b6c7f`
- Computed: `d58b6c7f`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
wait - is this ok. really! yes.
```
**Decoded message (raw shortcodes, not expanded):**
```
[ABV:wx] - is this ok. really! yes.
```

---

### Case 07: Long repetitive message, none

**File:** `07_long_repetitive_none.bin`  
**Message:** `the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog`  
**Method:** none  
**File size:** 239 bytes

> A long, highly repetitive message. Included as the 'none' baseline for comparison with case 08 (zlib) and case 09 (huffman) -- see which method actually wins for this input.

**Full hex dump:**
```
00c04def1192984cc10d61d10b1dc585
118781284c0448345510961a130137bc
464a6133043587442c771614461e04a1
301120d1544258684c04def1192984cc
10d61d10b1dc585118781284c0448345
510961a130137bc464a6133043587442
c771614461e04a1301120d1544258684
c04def1192984cc10d61d10b1dc58511
8781284c0448345510961a130137bc46
4a6133043587442c771614461e04a130
1120d1544258684c04def1192984cc10
d61d10b1dc585118781284c044834551
0961a130137bc464a6133043587442c7
71614461e04a1301120d154425868541
85bf19c19a34e49c04c25834d19204
```

**Header byte:** `00000000` (binary) = `0x00` (hex)  
**Tag bits:** `00` -> **none**

**Payload encoding:** raw 6-bit units, byte-packed directly

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `110000` | **1** (abv) | `10000` | `t` |
| 6 | `000100` | 0 | `00100` | `(space)` |
| 12 | `110111` | **1** (abv) | `10111` | `q` |
| 18 | `101111` | **1** (abv) | `01111` | `k` |
| 24 | `000100` | 0 | `00100` | `(space)` |
| 30 | `011001` | 0 | `11001` | `b` |
| 36 | `001010` | 0 | `01010` | `r` |
| 42 | `011000` | 0 | `11000` | `o` |
| 48 | `010011` | 0 | `10011` | `w` |
| 54 | `001100` | 0 | `01100` | `n` |
| 60 | `000100` | 0 | `00100` | `(space)` |
| 66 | `001101` | 0 | `01101` | `f` |
| 72 | `011000` | 0 | `11000` | `o` |
| 78 | `011101` | 0 | `11101` | `x` |
| 84 | `000100` | 0 | `00100` | `(space)` |
| 90 | `001011` | 0 | `01011` | `j` |
| 96 | `000111` | 0 | `00111` | `u` |
| 102 | `011100` | 0 | `11100` | `m` |
| 108 | `010110` | 0 | `10110` | `p` |
| 114 | `000101` | 0 | `00101` | `s` |
| 120 | `000100` | 0 | `00100` | `(space)` |
| 126 | `011000` | 0 | `11000` | `o` |
| 132 | `011110` | 0 | `11110` | `v` |
| 138 | `000001` | 0 | `00001` | `e` |
| 144 | `001010` | 0 | `01010` | `r` |
| ... | *(274 more rows omitted)* | | | |

**Content bits (raw, space-separated every 6 bits):**
```
110000 000100 110111 101111 000100 011001 001010 011000 010011 001100 000100 001101 011000 011101 000100 001011 000111 011100 010110 000101 000100 011000 011110 000001 001010 000100 110000 000100 0100 ... (truncated)
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 000110 011100 000110 011010 001101 001110 010010 011100 000001 001100 001001 011000 001101 001101 000110 010010 000001 00
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `imigfclm`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `8c8652bc`
- Computed: `8c8652bc`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog
```
**Decoded message (raw shortcodes, not expanded):**
```
[ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog
```

---

### Case 08: Long repetitive message, zlib

**File:** `08_long_repetitive_zlib.bin`  
**Message:** `the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog`  
**Method:** zlib  
**File size:** 144 bytes

> Same message as case 07. Zlib's LZ77 dictionary matching should shine here because the phrase repeats many times -- this is the scenario zlib is actually good at.

**Full hex dump:**
```
4078da3be0fb5e70d20c9f83bc8917b9
658fb60ab6376af8b07898840a4c9312
6634dfe3e69568cc62daeea2532e26e2
26c7b2d04050e162885344860fcbbd8f
929a2d6704aec90a6cbc1311285121d4
72c0a5d935903371a18170f5919465c2
06ce11254ec70b135d121f7809330af1
8abaa8b6b51ca0ab75ad8ead0d005f67
4da6fc670668d39270130960d3464810
```

**Header byte:** `01000000` (binary) = `0x40` (hex)  
**Tag bits:** `01` -> **zlib**

**Payload encoding:** zlib.compress() over the raw 6-bit content bytes

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `110000` | **1** (abv) | `10000` | `t` |
| 6 | `000100` | 0 | `00100` | `(space)` |
| 12 | `110111` | **1** (abv) | `10111` | `q` |
| 18 | `101111` | **1** (abv) | `01111` | `k` |
| 24 | `000100` | 0 | `00100` | `(space)` |
| 30 | `011001` | 0 | `11001` | `b` |
| 36 | `001010` | 0 | `01010` | `r` |
| 42 | `011000` | 0 | `11000` | `o` |
| 48 | `010011` | 0 | `10011` | `w` |
| 54 | `001100` | 0 | `01100` | `n` |
| 60 | `000100` | 0 | `00100` | `(space)` |
| 66 | `001101` | 0 | `01101` | `f` |
| 72 | `011000` | 0 | `11000` | `o` |
| 78 | `011101` | 0 | `11101` | `x` |
| 84 | `000100` | 0 | `00100` | `(space)` |
| 90 | `001011` | 0 | `01011` | `j` |
| 96 | `000111` | 0 | `00111` | `u` |
| 102 | `011100` | 0 | `11100` | `m` |
| 108 | `010110` | 0 | `10110` | `p` |
| 114 | `000101` | 0 | `00101` | `s` |
| 120 | `000100` | 0 | `00100` | `(space)` |
| 126 | `011000` | 0 | `11000` | `o` |
| 132 | `011110` | 0 | `11110` | `v` |
| 138 | `000001` | 0 | `00001` | `e` |
| 144 | `001010` | 0 | `01010` | `r` |
| ... | *(275 more rows omitted)* | | | |

**Content bits (raw, space-separated every 6 bits):**
```
110000 000100 110111 101111 000100 011001 001010 011000 010011 001100 000100 001101 011000 011101 000100 001011 000111 011100 010110 000101 000100 011000 011110 000001 001010 000100 110000 000100 0100 ... (truncated)
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 000110 011100 000110 011010 001101 001110 010010 011100 000001 001100 001001 011000 001101 001101 000110 010010 000001 0000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `imigfclm`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `8c8652bc`
- Computed: `8c8652bc`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog
```
**Decoded message (raw shortcodes, not expanded):**
```
[ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog
```

---

### Case 09: Long repetitive message, huffman

**File:** `09_long_repetitive_huffman.bin`  
**Message:** `the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog`  
**Method:** huffman  
**File size:** 214 bytes

> Same message as case 07 and 08, using the static Huffman table. Huffman only exploits SYMBOL FREQUENCY, not repeated substrings, so it should NOT beat zlib on this input -- a useful contrast case.

**Full hex dump:**
```
8092afef377f5362ba26ef776e7557f5
168ed92ac8521ab345ec957f79bbfa9b
15d1377bbb73aabfa8b476c9564290d5
9a2f64abfbcddfd4d8ae89bbdddb9d55
fd45a3b64ab21486acd17b255fde6efe
a6c5744ddeeedceaafea2d1db25590a4
35668bd92afef377f5362ba26ef776e7
557f5168ed92ac8521ab345ec957f79b
bfa9b15d1377bbb73aabfa8b476c9564
290d59a2f64abfbcddfd4d8ae89bbddd
b9d55fd45a3b64ab21486acd17b255fd
e6efea6c5744ddeeedceaafea2d1db25
590a435668bff115fc670668d3927013
0960d3464810
```

**Header byte:** `10000000` (binary) = `0x80` (hex)  
**Tag bits:** `10` -> **huffman**

**Payload encoding:** static Huffman table over 6-bit (flag,char) symbols

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `110000` | **1** (abv) | `10000` | `t` |
| 6 | `000100` | 0 | `00100` | `(space)` |
| 12 | `110111` | **1** (abv) | `10111` | `q` |
| 18 | `101111` | **1** (abv) | `01111` | `k` |
| 24 | `000100` | 0 | `00100` | `(space)` |
| 30 | `011001` | 0 | `11001` | `b` |
| 36 | `001010` | 0 | `01010` | `r` |
| 42 | `011000` | 0 | `11000` | `o` |
| 48 | `010011` | 0 | `10011` | `w` |
| 54 | `001100` | 0 | `01100` | `n` |
| 60 | `000100` | 0 | `00100` | `(space)` |
| 66 | `001101` | 0 | `01101` | `f` |
| 72 | `011000` | 0 | `11000` | `o` |
| 78 | `011101` | 0 | `11101` | `x` |
| 84 | `000100` | 0 | `00100` | `(space)` |
| 90 | `001011` | 0 | `01011` | `j` |
| 96 | `000111` | 0 | `00111` | `u` |
| 102 | `011100` | 0 | `11100` | `m` |
| 108 | `010110` | 0 | `10110` | `p` |
| 114 | `000101` | 0 | `00101` | `s` |
| 120 | `000100` | 0 | `00100` | `(space)` |
| 126 | `011000` | 0 | `11000` | `o` |
| 132 | `011110` | 0 | `11110` | `v` |
| 138 | `000001` | 0 | `00001` | `e` |
| 144 | `001010` | 0 | `01010` | `r` |
| ... | *(274 more rows omitted)* | | | |

**Content bits (raw, space-separated every 6 bits):**
```
110000 000100 110111 101111 000100 011001 001010 011000 010011 001100 000100 001101 011000 011101 000100 001011 000111 011100 010110 000101 000100 011000 011110 000001 001010 000100 110000 000100 0100 ... (truncated)
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 000110 011100 000110 011010 001101 001110 010010 011100 000001 001100 001001 011000 001101 001101 000110 010010 000001 0000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `imigfclm`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `8c8652bc`
- Computed: `8c8652bc`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog
```
**Decoded message (raw shortcodes, not expanded):**
```
[ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog [ABV:t] [ABV:qk] brown fox jumps over [ABV:t] lazy dog
```

---

### Case 10: Adversarial rare-letter message, none

**File:** `10_adversarial_none.bin`  
**Message:** `qzjxqzjxqzjx`  
**Method:** none  
**File size:** 27 bytes

> Deliberately built from the rarest letters in the static Huffman table (q, z, j, x). This is the case where a static table built on average English frequency actively HURTS compression -- included to show 'none' winning.

**Full hex dump:**
```
005d12dd5d12dd5d12dd150616fc9046
60c48158130960d3464810
```

**Header byte:** `00000000` (binary) = `0x00` (hex)  
**Tag bits:** `00` -> **none**

**Payload encoding:** raw 6-bit units, byte-packed directly

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `010111` | 0 | `10111` | `q` |
| 6 | `010001` | 0 | `10001` | `z` |
| 12 | `001011` | 0 | `01011` | `j` |
| 18 | `011101` | 0 | `11101` | `x` |
| 24 | `010111` | 0 | `10111` | `q` |
| 30 | `010001` | 0 | `10001` | `z` |
| 36 | `001011` | 0 | `01011` | `j` |
| 42 | `011101` | 0 | `11101` | `x` |
| 48 | `010111` | 0 | `10111` | `q` |
| 54 | `010001` | 0 | `10001` | `z` |
| 60 | `001011` | 0 | `01011` | `j` |
| 66 | `011101` | 0 | `11101` | `x` |
| 72 | `000101` | 0 | `00101` | `s` |
| 78 | `010000` | 0 | `10000` | `t` |
| 84 | `011000` | 0 | `11000` | `o` |
| 90 | `010110` | 0 | `10110` | `p` |

**Content bits (raw, space-separated every 6 bits):**
```
010111 010001 001011 011101 010111 010001 001011 011101 010111 010001 001011 011101 000101 010000 011000 010110
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 001001 000001 000110 011000 001100 010010 000001 010110 000001 001100 001001 011000 001101 001101 000110 010010 000001 0000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `deionlep`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `348edb4f`
- Computed: `348edb4f`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
qzjxqzjxqzjx
```

---

### Case 11: Adversarial rare-letter message, huffman

**File:** `11_adversarial_huffman.bin`  
**Message:** `qzjxqzjxqzjx`  
**Method:** huffman  
**File size:** 33 bytes

> Same message as case 10, forced through Huffman anyway. Compare the file size against case 10 to see the real cost of a frequency mismatch -- this is exactly the scenario the Auto/3-way selector is designed to avoid by picking 'none' instead.

**Full hex dump:**
```
8052548ddb7752548ddb7752548ddb77
fe22a0fc904660c48158130960d34648
10
```

**Header byte:** `10000000` (binary) = `0x80` (hex)  
**Tag bits:** `10` -> **huffman**

**Payload encoding:** static Huffman table over 6-bit (flag,char) symbols

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `010111` | 0 | `10111` | `q` |
| 6 | `010001` | 0 | `10001` | `z` |
| 12 | `001011` | 0 | `01011` | `j` |
| 18 | `011101` | 0 | `11101` | `x` |
| 24 | `010111` | 0 | `10111` | `q` |
| 30 | `010001` | 0 | `10001` | `z` |
| 36 | `001011` | 0 | `01011` | `j` |
| 42 | `011101` | 0 | `11101` | `x` |
| 48 | `010111` | 0 | `10111` | `q` |
| 54 | `010001` | 0 | `10001` | `z` |
| 60 | `001011` | 0 | `01011` | `j` |
| 66 | `011101` | 0 | `11101` | `x` |
| 72 | `000101` | 0 | `00101` | `s` |
| 78 | `010000` | 0 | `10000` | `t` |
| 84 | `011000` | 0 | `11000` | `o` |
| 90 | `010110` | 0 | `10110` | `p` |

**Content bits (raw, space-separated every 6 bits):**
```
010111 010001 001011 011101 010111 010001 001011 011101 010111 010001 001011 011101 000101 010000 011000 010110
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 001001 000001 000110 011000 001100 010010 000001 010110 000001 001100 001001 011000 001101 001101 000110 010010 000001 0000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `deionlep`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `348edb4f`
- Computed: `348edb4f`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
qzjxqzjxqzjx
```

---

### Case 12: Minimal single-character message

**File:** `12_minimal_none.bin`  
**Message:** `a`  
**Method:** none  
**File size:** 19 bytes

> The smallest possible non-empty message: a single letter. Useful for seeing the STOP_WORD and CRC trailer with almost no actual content bits in front of them.

**Full hex dump:**
```
000c54185bf61419c3d435404c25834d
192040
```

**Header byte:** `00000000` (binary) = `0x00` (hex)  
**Tag bits:** `00` -> **none**

**Payload encoding:** raw 6-bit units, byte-packed directly

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `000011` | 0 | `00011` | `a` |
| 6 | `000101` | 0 | `00101` | `s` |
| 12 | `010000` | 0 | `10000` | `t` |
| 18 | `011000` | 0 | `11000` | `o` |
| 24 | `010110` | 0 | `10110` | `p` |

**Content bits (raw, space-separated every 6 bits):**
```
000011 000101 010000 011000 010110
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 011000 010100 000110 011100 001111 010100 001101 010100 000001 001100 001001 011000 001101 001101 000110 010010 000001 000000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `ohimkhfh`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `e78ca757`
- Computed: `e78ca757`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
a
```

---

### Case 13: Highly skewed letter frequency, huffman

**File:** `13_skewed_huffman.bin`  
**Message:** `eeeeeeeeee teeeee`  
**Method:** huffman  
**File size:** 24 bytes

> Built almost entirely from 'e' and 't', the two most common letters in the static Huffman table. This is the best-case scenario for Huffman -- these symbols get the shortest codes.

**Full hex dump:**
```
8000000002e0000fe22afce04f043598
2c130960d3464810
```

**Header byte:** `10000000` (binary) = `0x80` (hex)  
**Tag bits:** `10` -> **huffman**

**Payload encoding:** static Huffman table over 6-bit (flag,char) symbols

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `000001` | 0 | `00001` | `e` |
| 6 | `000001` | 0 | `00001` | `e` |
| 12 | `000001` | 0 | `00001` | `e` |
| 18 | `000001` | 0 | `00001` | `e` |
| 24 | `000001` | 0 | `00001` | `e` |
| 30 | `000001` | 0 | `00001` | `e` |
| 36 | `000001` | 0 | `00001` | `e` |
| 42 | `000001` | 0 | `00001` | `e` |
| 48 | `000001` | 0 | `00001` | `e` |
| 54 | `000001` | 0 | `00001` | `e` |
| 60 | `000100` | 0 | `00100` | `(space)` |
| 66 | `010000` | 0 | `10000` | `t` |
| 72 | `000001` | 0 | `00001` | `e` |
| 78 | `000001` | 0 | `00001` | `e` |
| 84 | `000001` | 0 | `00001` | `e` |
| 90 | `000001` | 0 | `00001` | `e` |
| 96 | `000001` | 0 | `00001` | `e` |
| 102 | `000101` | 0 | `00101` | `s` |
| 108 | `010000` | 0 | `10000` | `t` |
| 114 | `011000` | 0 | `11000` | `o` |
| 120 | `010110` | 0 | `10110` | `p` |

**Content bits (raw, space-separated every 6 bits):**
```
000001 000001 000001 000001 000001 000001 000001 000001 000001 000001 000100 010000 000001 000001 000001 000001 000001 000101 010000 011000 010110
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 001110 000001 001111 000001 000011 010110 011000 001011 000001 001100 001001 011000 001101 001101 000110 010010 000001 0000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `cekeapoj`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `24a40fe9`
- Computed: `24a40fe9`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
eeeeeeeeee teeeee
```

---

### Case 14: Highly skewed letter frequency, none

**File:** `14_skewed_none.bin`  
**Message:** `eeeeeeeeee teeeee`  
**Method:** none  
**File size:** 31 bytes

> Same message as case 13, stored uncompressed for direct comparison -- shows how much Huffman saves when the message actually matches the assumed English frequency distribution.

**Full hex dump:**
```
00041041041041041110041041045418
5bf3813c10d660b04c25834d192040
```

**Header byte:** `00000000` (binary) = `0x00` (hex)  
**Tag bits:** `00` -> **none**

**Payload encoding:** raw 6-bit units, byte-packed directly

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `000001` | 0 | `00001` | `e` |
| 6 | `000001` | 0 | `00001` | `e` |
| 12 | `000001` | 0 | `00001` | `e` |
| 18 | `000001` | 0 | `00001` | `e` |
| 24 | `000001` | 0 | `00001` | `e` |
| 30 | `000001` | 0 | `00001` | `e` |
| 36 | `000001` | 0 | `00001` | `e` |
| 42 | `000001` | 0 | `00001` | `e` |
| 48 | `000001` | 0 | `00001` | `e` |
| 54 | `000001` | 0 | `00001` | `e` |
| 60 | `000100` | 0 | `00100` | `(space)` |
| 66 | `010000` | 0 | `10000` | `t` |
| 72 | `000001` | 0 | `00001` | `e` |
| 78 | `000001` | 0 | `00001` | `e` |
| 84 | `000001` | 0 | `00001` | `e` |
| 90 | `000001` | 0 | `00001` | `e` |
| 96 | `000001` | 0 | `00001` | `e` |
| 102 | `000101` | 0 | `00101` | `s` |
| 108 | `010000` | 0 | `10000` | `t` |
| 114 | `011000` | 0 | `11000` | `o` |
| 120 | `010110` | 0 | `10110` | `p` |

**Content bits (raw, space-separated every 6 bits):**
```
000001 000001 000001 000001 000001 000001 000001 000001 000001 000001 000100 010000 000001 000001 000001 000001 000001 000101 010000 011000 010110
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 001110 000001 001111 000001 000011 010110 011000 001011 000001 001100 001001 011000 001101 001101 000110 010010 000001 000000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `cekeapoj`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `24a40fe9`
- Computed: `24a40fe9`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
eeeeeeeeee teeeee
```

---

### Case 15: Mixed: abbreviations + punctuation, none

**File:** `15_mixed_none.bin`  
**Message:** `about the quick brown fox and the account. the abbreviation is not always obvious - but it works!`  
**Method:** none  
**File size:** 67 bytes

> A realistic longer message combining abbreviations, all three punctuation marks, and everyday words. Included as the 'none' baseline for the auto-comparison in case 18.

**Full hex dump:**
```
008f9130137bc464a613304358744865
130123bae084c048f9e6c10614431840
48f2cc46197866071446c4e70106404c
eaf5f150616fd63592da58f18130960d
346481
```

**Header byte:** `00000000` (binary) = `0x00` (hex)  
**Tag bits:** `00` -> **none**

**Payload encoding:** raw 6-bit units, byte-packed directly

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `100011` | **1** (abv) | `00011` | `a` |
| 6 | `111001` | **1** (abv) | `11001` | `b` |
| 12 | `000100` | 0 | `00100` | `(space)` |
| 18 | `110000` | **1** (abv) | `10000` | `t` |
| 24 | `000100` | 0 | `00100` | `(space)` |
| 30 | `110111` | **1** (abv) | `10111` | `q` |
| 36 | `101111` | **1** (abv) | `01111` | `k` |
| 42 | `000100` | 0 | `00100` | `(space)` |
| 48 | `011001` | 0 | `11001` | `b` |
| 54 | `001010` | 0 | `01010` | `r` |
| 60 | `011000` | 0 | `11000` | `o` |
| 66 | `010011` | 0 | `10011` | `w` |
| 72 | `001100` | 0 | `01100` | `n` |
| 78 | `000100` | 0 | `00100` | `(space)` |
| 84 | `001101` | 0 | `01101` | `f` |
| 90 | `011000` | 0 | `11000` | `o` |
| 96 | `011101` | 0 | `11101` | `x` |
| 102 | `000100` | 0 | `00100` | `(space)` |
| 108 | `100001` | **1** (abv) | `00001` | `e` |
| 114 | `100101` | **1** (abv) | `00101` | `s` |
| 120 | `000100` | 0 | `00100` | `(space)` |
| 126 | `110000` | **1** (abv) | `10000` | `t` |
| 132 | `000100` | 0 | `00100` | `(space)` |
| 138 | `100011` | **1** (abv) | `00011` | `a` |
| 144 | `101110` | **1** (abv) | `01110` | `c` |
| ... | *(45 more rows omitted)* | | | |

**Content bits (raw, space-separated every 6 bits):**
```
100011 111001 000100 110000 000100 110111 101111 000100 011001 001010 011000 010011 001100 000100 001101 011000 011101 000100 100001 100101 000100 110000 000100 100011 101110 101110 000010 000100 1100 ... (truncated)
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 010110 001101 011001 001011 011010 010110 001111 000110 000001 001100 001001 011000 001101 001101 000110 010010 000001
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `pfbjgpki`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `f5196fa8`
- Computed: `f5196fa8`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
about the quick brown fox and the account. the abbreviation is not always obvious - but it works!
```
**Decoded message (raw shortcodes, not expanded):**
```
[ABV:ab] [ABV:t] [ABV:qk] brown fox [ABV:es] [ABV:t] [ABV:acc]. [ABV:t] [ABV:abbn] is not [ABV:alw] obvious - [ABV:bt] it [ABV:wrx]!
```

---

### Case 16: Mixed: abbreviations + punctuation, zlib

**File:** `16_mixed_zlib.bin`  
**Message:** `about the quick brown fox and the account. the abbreviation is not always obvious - but it works!`  
**Method:** zlib  
**File size:** 79 bytes

> Same message as case 15, zlib method.

**Full hex dump:**
```
4078da013500caff8f9130137bc464a6
13304358744865130123bae084c048f9
e6c1061443184048f2cc461978660714
46c4e70106404ceaf5f150616041dd16
21fd63592da58f18130960d3464810
```

**Header byte:** `01000000` (binary) = `0x40` (hex)  
**Tag bits:** `01` -> **zlib**

**Payload encoding:** zlib.compress() over the raw 6-bit content bytes

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `100011` | **1** (abv) | `00011` | `a` |
| 6 | `111001` | **1** (abv) | `11001` | `b` |
| 12 | `000100` | 0 | `00100` | `(space)` |
| 18 | `110000` | **1** (abv) | `10000` | `t` |
| 24 | `000100` | 0 | `00100` | `(space)` |
| 30 | `110111` | **1** (abv) | `10111` | `q` |
| 36 | `101111` | **1** (abv) | `01111` | `k` |
| 42 | `000100` | 0 | `00100` | `(space)` |
| 48 | `011001` | 0 | `11001` | `b` |
| 54 | `001010` | 0 | `01010` | `r` |
| 60 | `011000` | 0 | `11000` | `o` |
| 66 | `010011` | 0 | `10011` | `w` |
| 72 | `001100` | 0 | `01100` | `n` |
| 78 | `000100` | 0 | `00100` | `(space)` |
| 84 | `001101` | 0 | `01101` | `f` |
| 90 | `011000` | 0 | `11000` | `o` |
| 96 | `011101` | 0 | `11101` | `x` |
| 102 | `000100` | 0 | `00100` | `(space)` |
| 108 | `100001` | **1** (abv) | `00001` | `e` |
| 114 | `100101` | **1** (abv) | `00101` | `s` |
| 120 | `000100` | 0 | `00100` | `(space)` |
| 126 | `110000` | **1** (abv) | `10000` | `t` |
| 132 | `000100` | 0 | `00100` | `(space)` |
| 138 | `100011` | **1** (abv) | `00011` | `a` |
| 144 | `101110` | **1** (abv) | `01110` | `c` |
| ... | *(45 more rows omitted)* | | | |

**Content bits (raw, space-separated every 6 bits):**
```
100011 111001 000100 110000 000100 110111 101111 000100 011001 001010 011000 010011 001100 000100 001101 011000 011101 000100 100001 100101 000100 110000 000100 100011 101110 101110 000010 000100 1100 ... (truncated)
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 010110 001101 011001 001011 011010 010110 001111 000110 000001 001100 001001 011000 001101 001101 000110 010010 000001 0000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `pfbjgpki`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `f5196fa8`
- Computed: `f5196fa8`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
about the quick brown fox and the account. the abbreviation is not always obvious - but it works!
```
**Decoded message (raw shortcodes, not expanded):**
```
[ABV:ab] [ABV:t] [ABV:qk] brown fox [ABV:es] [ABV:t] [ABV:acc]. [ABV:t] [ABV:abbn] is not [ABV:alw] obvious - [ABV:bt] it [ABV:wrx]!
```

---

### Case 17: Mixed: abbreviations + punctuation, huffman

**File:** `17_mixed_huffman.bin`  
**Message:** `about the quick brown fox and the account. the abbreviation is not always obvious - but it works!`  
**Method:** huffman  
**File size:** 65 bytes

> Same message as case 15, huffman method. Compare file sizes across cases 15-17 to see which method the Auto selector would pick for this realistic message.

**Full hex dump:**
```
806f70b255fde6efea6c5744ddeb9c8d
92adee2e2b2c956f70707ca7fa4995bd
ea56a6f5a69cfeeeab84953cb2b212ca
5fe22afd63592da58f18130960d34648
10
```

**Header byte:** `10000000` (binary) = `0x80` (hex)  
**Tag bits:** `10` -> **huffman**

**Payload encoding:** static Huffman table over 6-bit (flag,char) symbols

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `100011` | **1** (abv) | `00011` | `a` |
| 6 | `111001` | **1** (abv) | `11001` | `b` |
| 12 | `000100` | 0 | `00100` | `(space)` |
| 18 | `110000` | **1** (abv) | `10000` | `t` |
| 24 | `000100` | 0 | `00100` | `(space)` |
| 30 | `110111` | **1** (abv) | `10111` | `q` |
| 36 | `101111` | **1** (abv) | `01111` | `k` |
| 42 | `000100` | 0 | `00100` | `(space)` |
| 48 | `011001` | 0 | `11001` | `b` |
| 54 | `001010` | 0 | `01010` | `r` |
| 60 | `011000` | 0 | `11000` | `o` |
| 66 | `010011` | 0 | `10011` | `w` |
| 72 | `001100` | 0 | `01100` | `n` |
| 78 | `000100` | 0 | `00100` | `(space)` |
| 84 | `001101` | 0 | `01101` | `f` |
| 90 | `011000` | 0 | `11000` | `o` |
| 96 | `011101` | 0 | `11101` | `x` |
| 102 | `000100` | 0 | `00100` | `(space)` |
| 108 | `100001` | **1** (abv) | `00001` | `e` |
| 114 | `100101` | **1** (abv) | `00101` | `s` |
| 120 | `000100` | 0 | `00100` | `(space)` |
| 126 | `110000` | **1** (abv) | `10000` | `t` |
| 132 | `000100` | 0 | `00100` | `(space)` |
| 138 | `100011` | **1** (abv) | `00011` | `a` |
| 144 | `101110` | **1** (abv) | `01110` | `c` |
| ... | *(45 more rows omitted)* | | | |

**Content bits (raw, space-separated every 6 bits):**
```
100011 111001 000100 110000 000100 110111 101111 000100 011001 001010 011000 010011 001100 000100 001101 011000 011101 000100 100001 100101 000100 110000 000100 100011 101110 101110 000010 000100 1100 ... (truncated)
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 010110 001101 011001 001011 011010 010110 001111 000110 000001 001100 001001 011000 001101 001101 000110 010010 000001 0000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `pfbjgpki`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `f5196fa8`
- Computed: `f5196fa8`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
about the quick brown fox and the account. the abbreviation is not always obvious - but it works!
```
**Decoded message (raw shortcodes, not expanded):**
```
[ABV:ab] [ABV:t] [ABV:qk] brown fox [ABV:es] [ABV:t] [ABV:acc]. [ABV:t] [ABV:abbn] is not [ABV:alw] obvious - [ABV:bt] it [ABV:wrx]!
```

---

### Case 18: Legacy pre-1.7 format (no header byte)

**File:** `18_legacy_format.bin`  
**Message:** `this is a legacy format file made before this version`  
**Method:** legacy (pre-1.7, detected via fallback)  
**File size:** 52 bytes

> This file has NO header byte -- it uses the 1.6-and-earlier format where the decoder must guess the compression method by attempting zlib.decompress() and falling back to raw bytes on failure. Included to prove 1.7's decoder still reads old files correctly.

**Full hex dump:**
```
4141851061440c448168339510d60a70
340434648113ca44e6d1105061447812
851983054185bf69a24134138b04c258
34d19204
```

**Header byte:** none -- this is a legacy pre-1.7 file, detected via fallback.

**Payload encoding:** raw 6-bit units, byte-packed directly (identical to 'none' but no header)

**Content bits, chunked into 6-bit units** (flag + Baudot code):

| Offset | 6 bits | Flag | Baudot bits | Char |
|---|---|---|---|---|
| 0 | `010000` | 0 | `10000` | `t` |
| 6 | `010100` | 0 | `10100` | `h` |
| 12 | `000110` | 0 | `00110` | `i` |
| 18 | `000101` | 0 | `00101` | `s` |
| 24 | `000100` | 0 | `00100` | `(space)` |
| 30 | `000110` | 0 | `00110` | `i` |
| 36 | `000101` | 0 | `00101` | `s` |
| 42 | `000100` | 0 | `00100` | `(space)` |
| 48 | `000011` | 0 | `00011` | `a` |
| 54 | `000100` | 0 | `00100` | `(space)` |
| 60 | `010010` | 0 | `10010` | `l` |
| 66 | `000001` | 0 | `00001` | `e` |
| 72 | `011010` | 0 | `11010` | `g` |
| 78 | `000011` | 0 | `00011` | `a` |
| 84 | `001110` | 0 | `01110` | `c` |
| 90 | `010101` | 0 | `10101` | `y` |
| 96 | `000100` | 0 | `00100` | `(space)` |
| 102 | `001101` | 0 | `01101` | `f` |
| 108 | `011000` | 0 | `11000` | `o` |
| 114 | `001010` | 0 | `01010` | `r` |
| 120 | `011100` | 0 | `11100` | `m` |
| 126 | `000011` | 0 | `00011` | `a` |
| 132 | `010000` | 0 | `10000` | `t` |
| 138 | `000100` | 0 | `00100` | `(space)` |
| 144 | `001101` | 0 | `01101` | `f` |
| ... | *(26 more rows omitted)* | | | |

**Content bits (raw, space-separated every 6 bits):**
```
010000 010100 000110 000101 000100 000110 000101 000100 000011 000100 010010 000001 011010 000011 001110 010101 000100 001101 011000 001010 011100 000011 010000 000100 001101 000110 010010 000001 0001 ... (truncated)
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 011010 011010 001001 000001 001101 000001 001110 001011 000001 001100 001001 011000 001101 001101 000110 010010 000001
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)
- CRC32 nibble-letters: `ggdefecj`
- Trailer tag word: `endoffile`

**CRC32 verification:**
- Stored:   `66345429`
- Computed: `66345429`
- Result: **MATCH**

**Decoded message (abbreviations expanded):**
```
this is a legacy format file made before this version
```
**Decoded message (raw shortcodes, not expanded):**
```
this is a legacy format file [ABV:md] [ABV:bf] this version
```

---

### Case 19: Deliberately corrupted file (CRC32 mismatch)

**File:** `19_corrupted_file.bin`  
**Message:** `this file will be deliberately corrupted for testing`  
**Method:** none  
**File size:** 48 bytes

> Built normally with the 'none' method, then byte offset 10 in the final file was corrupted by flipping every bit (XOR 0xFF). This simulates transmission/storage corruption. The CRC32 check will FAIL because the stored CRC32 (computed before corruption) no longer matches the corrupted content. Demonstrates the integrity-check feature working as intended.

**Full hex dump:**
```
0041418510d192044ce6ec9129cb9d44
39828a1d6401244b7811004540631a15
0616fc934e24e38104130960d3464810
```

**Header byte:** `00000000` (binary) = `0x00` (hex)  
**Tag bits:** `00` -> **none**

**Payload encoding:** raw 6-bit units, byte-packed directly

**Corruption details:**
- Byte offset `10` was flipped: `0x13` -> `0xec` (XOR 0xFF)
- Original (uncorrupted) file hex:
  ```
  0041418510d192044ce6139129cb9d44
  39828a1d6401244b7811004540631a15
  0616fc934e24e38104130960d3464810
  ```

**Content bits (raw, space-separated every 6 bits):**
```
010000 010100 000110 000101 000100 001101 000110 010010 000001 000100 110011 100110 111011 001001 000100 101001 110010 111001 110101 000100 001110 011000 001010 001010 000111 010110 010000 000001 0010 ... (truncated)
```

**Trailer bits** (delimiter + CRC32 nibbles + "endoffile", space-separated):
```
111111 001001 001101 001110 001001 001110 001110 000001 000001 000001 001100 001001 011000 001101 001101 000110 010010 000001 0000
```
- Delimiter: `111111` (flag=1 + Baudot 11111 = reserved marker)

**CRC32 verification:**
- Stored:   `35232244`
- Computed: `3ceea715`
- Result: **MISMATCH**

**Decoded message (abbreviations expanded):**
```
(CRC MISMATCH - decode would warn user before proceeding)
```

---

## How These Files Were Generated

All 19 files in `test_files/` were produced by `generate_test_files.py`, which calls directly into `1.7.py`'s real encoding functions (`build_encoded_bytes`, `build_message_content_bits`, etc.) -- nothing in this document is hand-simulated. Every file was then independently verified by running it through `1.7.py`'s actual `decode_from_file()` function to confirm the CRC32 check and decoded message match what's shown here.

You can reproduce any of this yourself:
```bash
python3 1.7.py
# choose option 2 (Decode) or option 3 (CRC32 Check)
# enter any filename from test_files/, e.g. 01_short_none
```
