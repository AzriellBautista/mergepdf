# mergepdf

Merge multiple PDF files into a single PDF.

Point it at some PDFs and it writes one PDF.

```console
$ mergepdf .\documents -o merged.pdf
```

## Contents

- [Install](#install)
- [Quick start](#quick-start)
- [FILE arguments](#file-arguments)
- [Choosing files with `--list` and `--pattern`](#choosing-files-with---list-and---pattern)
- [Page selections](#page-selections)
- [Ordering](#ordering)
- [Output](#output)
- [Bookmarks and outlines](#bookmarks-and-outlines)
- [Duplicate inputs](#duplicate-inputs)
- [Metadata](#metadata)
- [Error handling](#error-handling)
- [Exit codes](#exit-codes)
- [Verbosity](#verbosity)
- [Option reference](#option-reference)
- [Design notes](#design-notes)

## Install

The only dependency is [`pypdf`](https://pypdf.readthedocs.io/) 6.19.0 or newer,
on Python 3.13 or newer. With [`uv`](https://docs.astral.sh/uv/) that is one
command, and it puts `mergepdf` on your PATH:

```console
$ uv tool install git+https://github.com/AzriellBautista/mergepdf
```

From a clone:

```console
$ uv tool install .
```

`uv tool install` gives you an isolated environment holding just this tool, so
it cannot disturb anything else you have installed. To upgrade, re-run the same
command; to remove it, `uv tool uninstall mergepdf`.

<details>
<summary>Other ways to run it</summary>

Without installing anything, from a clone:

```console
$ uv run mergepdf .\documents -o merged.pdf     # builds on first use, then reuses
$ uv run --project . python -m mergepdf .\documents -o merged.pdf
```

With pip, into your current environment:

```console
$ python -m pip install .
$ python -m mergepdf .\documents -o merged.pdf
```

</details>

## Quick start

```console
# Merge a whole folder, alphabetically by filename.
$ mergepdf .\documents -o merged.pdf

# Merge specific files in a specific order.
$ mergepdf 03.pdf 01.pdf 02.pdf

# Take only some pages from each file.
$ mergepdf "report.pdf:1-3,7" "appendix.pdf:-2"

# Check what would happen without writing anything.
$ mergepdf .\documents --recursive --dry-run
```

## FILE arguments

Every `FILE` is one of:

| Argument | Meaning |
| --- | --- |
| `report.pdf` | That one file, all pages |
| `documents` | Every PDF directly inside that directory |
| `documents -r` | Every PDF in that directory and its subdirectories |
| `report.pdf:1-3,7` | That file, pages 1 to 3 plus page 7 |

You can mix files and directories freely, and the output is the concatenation
of everything in the order described under [Ordering](#ordering). A `FILE`
argument is optional as long as `--list` or `--pattern` supplies at least one
input; see
[Choosing files with `--list` and `--pattern`](#choosing-files-with---list-and---pattern).

A page selection may only be applied to a single file. Applying one to a
directory is an error, because "page 3 of a directory" has no meaning.

## Choosing files with `--list` and `--pattern`

Naming every file gets old when the set changes or lives in several places. Two
further sources let you point mergepdf at a set instead, and both are repeatable
and can be combined with each other and with `FILE` arguments.

### `--list` / `-L`

Reads inputs from a text file, one per line:

```console
$ mergepdf --list pdfs.txt -o merged.pdf
```

```text
# cover sheets
report.pdf
appendix.pdf
# only the last two pages of this one
scan.pdf:-2
```

- Blank lines and lines starting with `#` are ignored, so a generated list can
  carry a header.
- Each remaining line takes the same syntax as a `FILE` argument, so a page
  selection such as `scan.pdf:-2` is allowed.
- Paths are relative to the **current directory**, not to the directory the list
  file lives in.
- A list that cannot be read, has a bad selection, or contains no usable entries
  is an error (exit 1). A bad line is reported as `file:line`.

### `--pattern` / `-P`

Finds inputs with a glob:

```console
$ mergepdf -P "documents/*.pdf"
$ mergepdf -P "**/scan-*.pdf"
```

- The part before the first wildcard is the directory to scan. `documents/*.pdf`
  scans `documents`; a pattern that starts with a wildcard is matched against the
  current directory.
- `--recursive` widens a pattern that does not already contain `**` so it also
  matches in subdirectories: `-P "documents/*.pdf" -r`. A pattern that already
  says `**` is as wide as it gets, with or without `-r`.
- Matches are sorted, so two runs over one tree produce the same output. An
  explicit `--order` still applies on top.
- A pattern that matches nothing is an error (exit 1), even with
  `--skip-invalid`: that flag is about files that cannot be *read*, whereas an
  empty match almost always means the pattern is mistyped.

In a `--pattern`, `[...]` is a glob character class, so `-P "report[12].pdf"`
matches `report1.pdf` and `report2.pdf`. A filename that literally contains a
bracket belongs in a `FILE` argument or a `--list` entry, both of which treat
brackets literally.

### Combining sources

Positional `FILE` arguments come first, then each `--list` in the order given,
then each `--pattern`. That order is what you get unless you pass `--order`.

```console
$ mergepdf cover.pdf -L body.txt -P "appendix/*.pdf"
```

`--output-dir` cannot be combined with `--list` or `--pattern`, because that
mode writes one file per supplied *directory* and these name individual files.

## Page selections

Append a colon and a selection to narrow a single file:

```console
$ mergepdf "report.pdf:1-3,7"
```

### Grammar

| Form | Selects |
| --- | --- |
| `:7` | Page 7 |
| `:1-3` | Pages 1, 2 and 3 |
| `:5-` | Page 5 through the last page |
| `:-1` | The last page |
| `:-2` | The last two pages |
| `:1-3,7` | Pages 1 to 3, then page 7 |
| `:1-3,10-` | Pages 1 to 3, then page 10 to the end |

Page numbers are **1-based** and both ends are **inclusive**, matching what a
PDF viewer shows you. Parts are combined in the order you write them, so
`:1-3,7` and `:7,1-3` produce different output.

### `-2` is a count, not an index

This is the one that surprises people. `-N` means **the last N pages**, not
"the Nth page from the end". On a 12-page document:

| Selection | Result | |
| --- | --- | --- |
| `:-1` | last page | 1 page |
| `:-2` | last two | 2 pages |
| `:-12` | last twelve | all 12 pages |
| `:-13` | clamped | all 12 pages |

To get a single page counted from the end, use a negative-looking number with
no dash and accept that it is a count, or select that page explicitly.

### Clamping and errors

- A selection that runs past the end of a short document is **clamped**, not
  an error. `:99-` on a 3-page file yields nothing from that part and logs
  `page selection '99-' is outside the document (3 pages)`.
- If a selection matches **no pages at all**, that is an error (exit 4) rather
  than a silent zero-page contribution.
- `0` is rejected, because page numbers start at 1.
- A range that ends before it starts (`:5-2`) is rejected.
- A count with an end (`:-2-3`) is rejected.

All three of those last rejections happen during argument parsing, so they exit
2 and name the offending token:

```console
$ mergepdf "report.pdf:0"
mergepdf: error: argument FILE: 'report.pdf:0': page numbers are 1-based, so 0 is not valid: '0'. Expected something like ':1', ':1-3', ':1-3,7', ':5-', or ':-1'.
```

A token whose tail contains no digits at all is never treated as a mangled
selection. `report.pdf:final` is reported as a missing file, because that is
what it probably is.
- The same page listed twice in one selection is included once, with a
  `duplicate pages ignored` note. This differs from repeating the whole file,
  which is treated as a duplicate input; see
  [Duplicate inputs](#duplicate-inputs).

### Quote the argument

The comma is a separator to your shell as well as to mergepdf. Quote any
selection containing one:

```console
$ mergepdf "report.pdf:1-3,7"      # correct
$ mergepdf report.pdf:1-3,7        # wrong on bash, cmd.exe and PowerShell
```

On Windows, `cmd.exe` and PowerShell each apply their own quoting rules on top,
so the quoting matters twice over.

## Ordering

By default files are merged in the order you supplied them. For a directory,
that means a pre-order walk: entries sorted alphabetically at each level,
descending into subdirectories only with `-r`.

`--order` changes that, and `--sort` chooses the direction:

| `--order` | Sorts by |
| --- | --- |
| `none` (default) | Supplied or discovered order |
| `name` | Path |
| `created` | File creation time |
| `modified` | Last modification time |

```console
$ mergepdf .\documents --order name
$ mergepdf .\documents --order modified --sort desc   # newest first
```

Sorting is total: files with equal timestamps are broken by file identity, so
the order is reproducible rather than dependent on directory iteration order.

Passing `--sort` without `--order` logs a warning that it has no effect.

> **`created` is not portable.** On Windows it uses the real creation time.
> On Linux and macOS there is no portable creation time, so it falls back to
> `st_ctime`, which records the last inode change and is often *not* when the
> file was created. Use `--order modified` if you need the same behaviour
> everywhere.

## Output

```console
$ mergepdf .\documents -o out.pdf            # explicit file (default merged.pdf)
$ mergepdf .\archive\2023 .\archive\2024 -d .\out   # one file per directory
```

- `-o` writes a single PDF. Default `merged.pdf` in the current directory.
- `-d` writes one PDF per supplied directory, named after the directory, into
  `DIR`. Every `FILE` must be a directory in this mode, page selections are
  not allowed, and two directories that would produce the same output name are
  an error rather than one silently overwriting the other.
- The two modes are mutually exclusive.
- An existing output is never replaced without `-f`.
- The output is written to a temporary file beside the target and then renamed
  into place, so an interrupted or failed run cannot leave a half-written PDF
  or destroy the previous good output.
- The output is never merged into itself. If the output path is also an input,
  that is an error.

## Bookmarks and outlines

By default each merged file contributes one top-level bookmark, named after
the file, with any page selection shown in brackets:

```
report.pdf
appendix.pdf [1-3,7]
```

Bookmarks already inside each input are imported beneath mergepdf's own entry,
preserving nesting. Repeated bookmark names are numbered `name (2)`,
`name (3)`, and so on.

- `--no-bookmarks` omits mergepdf's own per-file entries.
- `--no-import-outlines` leaves existing bookmarks in the input PDFs behind.

## Duplicate inputs

Supplying the same file twice merges it once. The first occurrence wins and
the rest are skipped with a warning.

Two things are compared, not one:

- **File identity**, from the filesystem's device and inode. Two hard links to
  one file are duplicates even though their paths differ, and two spellings of
  one path are duplicates even though the text differs. If the filesystem
  reports an unusable inode, the resolved path is used instead.
- **Page selection**, normalised. `f:1-2` and `f:01-02` are the same request,
  and `f:1-2,3` and `f:3,1-2` are the same request, so both pairs are
  deduplicated.

Ranges are deliberately *not* merged, so `f:1-3` and `f:1-2,3` stay distinct
even though they select the same pages. Deciding they are equivalent needs
the page count, which is not known until the file is opened.

Supplying one file with two different selections is **not** a duplicate; both
are merged:

```console
$ mergepdf "report.pdf:1-3" "report.pdf:10-"    # both parts included
```

## Metadata

`/Title` and `/Author` are copied from the first file that merges
successfully. `/Producer` and `/Creator` are set to `mergepdf <version>`.

`--metadata` sets any field explicitly, and repeats:

```console
$ mergepdf .\documents -o out.pdf \
    --metadata /Title="Annual Report 2026" \
    --metadata /Author="Records Office" \
    --metadata /Subject=Quarterly filings
```

- The format is `KEY=VALUE`. Only the first `=` separates, so a value may
  contain more of them: `--metadata /Title=a=b` sets `a=b`.
- The leading slash is optional. `Title=Report` and `/Title=Report` are the
  same thing, because the slash is part of the PDF name syntax rather than
  something you should have to type.
- An empty value is allowed and clears the field: `--metadata /Title=`.
- Repeating a key is last-wins, so a later flag overrides an earlier one.
- An explicit value wins over both the title and author copied from the first
  input, and over the `/Producer` and `/Creator` mergepdf would otherwise set.
- A key containing a space or any of `( ) < > [ ] { } / %` is rejected, since
  those cannot appear unescaped in a PDF name.

Dates are passed through untouched, so a `/CreationDate` must be in PDF's own
`D:YYYYMMDDHHmmSS+ZZ'00'` form if you want a conforming value.

## Error handling

Every input is checked before any merging starts, and **all** problems are
reported in one pass rather than one per attempt. mergepdf then stops, unless
you pass `--skip-invalid`, in which case the bad inputs are logged and
skipped and the rest are merged. If every input fails, nothing is written.

```console
$ mergepdf good.pdf broken.pdf missing.pdf -o out.pdf
[ERROR] 2 inputs could not be used:
  Path not found: missing.pdf
  broken.pdf: File has not been decrypted
Aborting because some inputs could not be used. Pass --skip-invalid to merge the rest anyway.
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Input error: path not found, not a PDF, no PDFs found, output is also an input |
| 2 | Usage error, including a malformed page selection |
| 3 | Output already exists and `-f` was not given |
| 4 | A PDF could not be read, or a selection matched no pages |
| 5 | Output could not be written |
| 130 | Interrupted |

Note the split between codes 1, 2 and 4 for selection problems: a selection
that is *syntactically* wrong (`:0`, `:5-2`, `:-2-3`) is rejected by argument
parsing and exits 2, while a well-formed selection that matches nothing exits
4. A missing path is an input error and exits 1.

## Verbosity

| Flag | Shows |
| --- | --- |
| *(none)* | Warnings and errors only |
| `-v` | Progress, one line per file |
| `-vv` | mergepdf's internal decisions, plus the traceback when a run fails |
| `--quiet` | Errors only |

`-vv` is as deep as it goes. Extra `-v` flags raise no further log level. The
one visible difference is that the `-vv` argument dump reports the count you
actually passed, so a typo like `-vvvv` is visible in the log rather than
silently absorbed.

## Option reference

| Option | Effect |
| --- | --- |
| `-L`, `--list` | Read inputs from a text file, one per line. Repeatable. |
| `-P`, `--pattern` | Find inputs with a glob. Repeatable. |
| `-o`, `--outfile` | Output PDF. Default `merged.pdf`. |
| `-d`, `--output-dir` | One merged PDF per supplied directory, into `DIR`. |
| `-r`, `--recursive` | Descend into subdirectories, and widen `--pattern`. |
| `--order` | `none`, `name`, `created`, `modified`. |
| `--sort` | `asc` or `desc`. |
| `-f`, `--force` | Overwrite an existing output. |
| `--dry-run` | Print the merge plan; write nothing. |
| `--skip-invalid` | Skip unreadable inputs instead of aborting. |
| `--no-bookmarks` | Do not add per-file bookmark entries. |
| `--no-import-outlines` | Do not carry over input bookmarks. |
| `--metadata` | Set a metadata field, `KEY=VALUE`. Repeatable. |
| `--quiet` | Errors only. |
| `-v`, `--verbose` | Repeat for more detail. |
| `--version` | Print the version. |

`--dry-run` prints to stdout, is not suppressed by `--quiet`, and does not
check whether the output already exists.

## Design notes

A few decisions worth knowing about, in case they surprise you.

**A colon separates a page selection.** Windows forbids `:` in a filename, so
on Windows no real file can be mistaken for a selection. On Linux and macOS a
colon is an ordinary filename character, so a token that names an existing file
always wins over reading it as a selection. A Windows drive letter is treated
as part of the path, so `C:1` is the file `1` relative to drive C rather than
page 1 of a file called `C`.

**Brackets were the original syntax and had to go.** `[`, `]` and `-` are all
legal in filenames on every platform, so `file[1-2].pdf` and `report.pdf[2]`
were genuinely ambiguous. The colon removes the ambiguity at the root rather
than adding special cases for it. A file named `report.pdf[2]` is not a PDF as
far as mergepdf is concerned, because everything after the final dot is its
extension; it is refused with a clear message rather than silently
misinterpreted. `FILE` arguments and `--list` entries therefore treat brackets
as ordinary filename characters. The one exception is `--pattern`, which is
deliberately glob-shaped, so `[...]` there is a character class.

**A selection is a request, not a slice.** Out-of-range parts clamp and warn,
so a selection written for a longer document still works on a shorter one.

**Directory walks cannot loop.** Symlinks and Windows junctions that point at
an ancestor are skipped by identity rather than followed until the interpreter
runs out of stack.

**Skipping a broken file is opt-in.** By default a bad input aborts the run, so
a short output is never mistaken for a complete one.
