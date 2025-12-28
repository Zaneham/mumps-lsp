# MUMPS/M Language Support for Visual Studio Code

Language Server Protocol (LSP) implementation for **MUMPS/M** (Massachusetts General Hospital Utility Multi-Programming System), the programming language that knows more about your medical history than your GP does.

## About MUMPS

MUMPS was developed in 1966 at Massachusetts General Hospital. It was designed to handle hierarchical databases and string processing for medical records. The language is now an ANSI and ISO standard (ISO/IEC 11756:1999), which sounds terribly official until you realise the standard was written when the average hospital still used fax machines for everything.

Today, MUMPS powers:

- **Epic Systems** - handling 78% of US patient records (305 million people)
- **VistA** - the US Veterans Administration system (8 million veterans, 163 hospitals)
- **MEDITECH** - another substantial chunk of healthcare IT
- **InterSystems Caché/IRIS** - the modern runtime for MUMPS
- **YottaDB** - open-source MUMPS for the budget-conscious

If you've ever wondered why healthcare IT seems to exist in a parallel universe where "modern" means "from the 1990s," well, you're looking at it.

## Features

- **Syntax highlighting** for MUMPS constructs
- **Code completion** for commands, functions, variables
- **Hover information** with documentation
- **Go to definition** for labels and routines
- **Find references** across the document
- **Document outline** showing routine structure
- **Support for all MUMPS constructs:**
  - Commands (SET, DO, QUIT, KILL, etc.)
  - Intrinsic functions ($PIECE, $ORDER, $DATA, etc.)
  - Special variables ($HOROLOG, $JOB, $IO, etc.)
  - Structured system variables (^$GLOBAL, ^$LOCK, etc.)
  - Global variables (^PATIENT, ^LAB, etc.)
  - Pattern matching and indirection

## Installation

1. Install the extension from the VS Code Marketplace
2. Ensure Python 3.8+ is installed and available in PATH
3. Open any `.m`, `.mps`, `.mumps`, `.ros`, or `.int` file
4. Your medical records are now syntax-highlighted

## File Extensions

| Extension | Description |
|-----------|-------------|
| `.m`      | MUMPS source file (also used by MATLAB, but they started later) |
| `.mps`    | MUMPS source file |
| `.mumps`  | MUMPS source file (for the unabbreviated) |
| `.ros`    | InterSystems routine |
| `.int`    | InterSystems intermediate |
| `.zwr`    | Global export file |

## Language Overview

MUMPS uses a terse syntax where every command has a one or two-letter abbreviation. The philosophy was that storage was expensive in 1966, and apparently the philosophy stuck.

```mumps
; MUMPS Patient Record Example
; Your medical history in 50 lines or less
;
START ; Entry point
 N PATID,NAME,DOB,MEDS
 S PATID=$$GETID^PATIENT
 I PATID="" W "Patient not found",! Q
 ;
 ; Fetch patient data from global
 S NAME=$G(^PATIENT(PATID,"NAME"))
 S DOB=$G(^PATIENT(PATID,"DOB"))
 ;
 W "Patient: ",NAME,!
 W "DOB: ",$$FMTDATE(DOB),!
 ;
 ; List medications
 W !,"Current Medications:",!
 S MEDS=""
 F  S MEDS=$O(^PATIENT(PATID,"MEDS",MEDS)) Q:MEDS=""  D
 . W "  - ",MEDS,!
 Q
 ;
FMTDATE(DT) ; Format $H date for humans
 N M,D,Y
 S Y=DT\365.25+1840
 S D=DT#365.25
 ; Close enough for government work
 Q M_"/"_D_"/"_Y
 ;
SAVE(ID,DATA) ; Save patient record
 TSTART
 M ^PATIENT(ID)=DATA
 TCOMMIT
 Q 1
```

### Key Syntax Elements

- **Comments:** `;` to end of line
- **Assignment:** `SET` or `S` (because three letters is two too many)
- **Labels:** Start of line, letters and numbers, optionally with parameters
- **Line structure:** Label, dots for block level, command, arguments
- **Statement separator:** Space (yes, really)

### Commands

| Command | Abbrev | Does What |
|---------|--------|-----------|
| SET | S | Assign values |
| DO | D | Call routine |
| QUIT | Q | Return |
| IF | I | Conditional |
| FOR | F | Loop |
| WRITE | W | Output |
| READ | R | Input |
| KILL | K | Delete variables |
| NEW | N | Create local scope |
| MERGE | M | Copy data structures |
| LOCK | L | Concurrency control |
| XECUTE | X | Execute string as code |

### Intrinsic Functions

| Function | Abbrev | Purpose |
|----------|--------|---------|
| $PIECE | $P | Extract delimited piece (the workhorse) |
| $ORDER | $O | Traverse subscripts |
| $DATA | $D | Check existence |
| $GET | $G | Get with default |
| $LENGTH | $L | String/list length |
| $EXTRACT | $E | Substring |
| $SELECT | $S | Conditional expression |
| $HOROLOG | $H | Date/time since Dec 31, 1840 |

### The Global Database

MUMPS has a built-in hierarchical database. Variables starting with `^` persist to disk:

```mumps
; Store patient
S ^PATIENT(12345,"NAME")="Smith,John"
S ^PATIENT(12345,"DOB")=56789
S ^PATIENT(12345,"MEDS","Aspirin")=1
S ^PATIENT(12345,"MEDS","Metformin")=1

; Traverse all patients
S ID="" F  S ID=$O(^PATIENT(ID)) Q:ID=""  D
. W !,"Patient: ",^PATIENT(ID,"NAME")
```

### The Naked Reference

```mumps
S ^PATIENT(123,"NAME")="Smith"
S ^("DOB")=56789  ; Same as ^PATIENT(123,"DOB")
```

Yes, you can omit the global name and subscripts. Yes, this is a feature. Yes, this causes bugs.

## Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `mumps.pythonPath` | Path to Python interpreter | `python` |
| `mumps.serverPath` | Path to LSP server script | (bundled) |
| `mumps.trace.server` | Trace level for debugging | `off` |
| `mumps.maxGlobalDepth` | Maximum depth for global analysis | `10` |

## Requirements

- Visual Studio Code 1.75.0 or later
- Python 3.8 or later
- Optional: working knowledge of 1960s programming philosophy

## Known Limitations

- The parser handles standard MUMPS but may not cover all vendor extensions
- InterSystems ObjectScript class syntax is not fully supported
- Some implementations (GT.M, Caché, IRIS) have unique extensions
- The language itself is a limitation, but you knew that

## Documentation Sources

This extension was developed using:

1. **MUMPS Language Standard, NBS Handbook 118** (1976)
   - The ANSI X11.1 standard for MUMPS
   - National Bureau of Standards (now NIST)

2. **MUMPS Pocket Guide** (1995)
   - Quick reference for commands, functions, variables

3. **ISO/IEC 11756:1999**
   - International standard for MUMPS

## Why Does This Exist?

You might reasonably ask why anyone would want language support for MUMPS in 2025. The answer is that approximately 305 million Americans have their medical records stored in MUMPS databases. The VA's VistA system, which handles healthcare for 8 million veterans across 163 hospitals, runs on MUMPS. InterSystems Caché, which powers Epic (the largest electronic health records vendor), is a MUMPS implementation.

MUMPS isn't going anywhere. It's too embedded in healthcare infrastructure to replace. So you might as well have syntax highlighting.

## Licence

Copyright 2025 Zane Hambly

Licensed under the Apache Licence, Version 2.0. See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome. Pull requests should include:
- Working code
- A tolerance for the absurd

## Related Projects

If you've somehow found satisfaction in providing tooling for a language where naked references are a feature and the date system starts in 1840, you might appreciate:

- **[JOVIAL J73 LSP](https://github.com/Zaneham/jovial-lsp)** - For when your systems handle aircraft rather than patients. JOVIAL has been keeping F-15s airborne since the 1970s. Different sort of life-critical, same era of computing philosophy.

- **[CMS-2 LSP](https://github.com/Zaneham/cms2-lsp)** - The US Navy's tactical language. Aegis cruisers and submarines. Like MUMPS, it's still in production. Unlike MUMPS, it doesn't store your prescription history.

- **[CORAL 66 LSP](https://github.com/Zaneham/coral66-lsp)** - The British equivalent. Tornado aircraft and Royal Navy vessels. Developed at Malvern, presumably between tea breaks. Crown Copyright and all that.

- **[HAL/S LSP](https://github.com/Zaneham/hals-lsp)** - NASA's Space Shuttle language. Native vector and matrix operations because astronauts have enough to worry about. Also handles real-time scheduling. MUMPS handles scheduling too, but for appointments, not orbital maneuvers.

- **[Minuteman Guidance Computer Emulator](https://github.com/Zaneham/minuteman-emu)** - An emulator for ICBM guidance computers. Also life-critical in a very different way. We preserve these languages so people don't have to rediscover how they work in a crisis.

- **[Minuteman Assembler](https://github.com/Zaneham/minuteman-assembler)** - Two-pass assembler for the D17B/D37C. For the other kind of critical infrastructure. Complete with documentation about missile guidance algorithms that are now declassified, presumably because everyone has better missiles now.

## Acknowledgements

- Massachusetts General Hospital (original MUMPS development)
- The MUMPS Development Committee
- National Bureau of Standards / NIST
- InterSystems Corporation
- FIS/GT.M and YottaDB
- The brave souls maintaining healthcare IT infrastructure
