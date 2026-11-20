# Data File Format

Each language has one data file in tab-separated values (TSV) format.

## File naming

```
<language>.tsv
```

Use the lowercase English name of the language.

Examples: `indonesian.tsv`, `japanese.tsv`, `french.tsv`

## Encoding and structure

- UTF-8 encoding
- Tab character as the column separator
- One entry per line
- Exactly 3 columns per line
- The first line is a header row

## Columns

| # | Column          | Required | Description                                                   |
|---|-----------------|----------|---------------------------------------------------------------|
| 1 | kanji           | Yes      | The kanji (or kanji compound)                                 |
| 2 | english_keyword | No       | An English keyword or phrase. Spaces allowed. May be blank.   |
| 3 | core_meanings   | No       | Meanings separated by commas. May be blank.                   |

## Header row

The first line must be exactly:

```
kanji<TAB>english_keyword<TAB>core_meanings
```

## Rules

- Separate columns with a single tab. Do not use spaces to align columns.
- If a column is blank, keep its tab so the line still has 3 columns.
- The english keyword may contain spaces (for example `big city`).
- Separate core meanings with commas. Meanings themselves should not contain commas.
- Do not use tabs or newlines inside any field.

## Example

`indonesian.tsv` (`<TAB>` stands for a real tab character):

```
kanji<TAB>english_keyword<TAB>core_meanings
水<TAB>water<TAB>air, banjir, sungai
火<TAB>fire<TAB>api, kebakaran, panas
愛<TAB><TAB>cinta, kasih sayang
山<TAB>mountain<TAB>
川<TAB><TAB>
休<TAB>take a break<TAB>istirahat, libur
```

- `愛` has no english keyword, so the second column is empty.
- `山` has no core meanings, so the line ends with a trailing tab.
- `川` has only the kanji, so it has two trailing tabs.
- `休` has a keyword with spaces, which is fine because only tabs separate columns.
