#!/usr/bin/env python3
"""
MUMPS/M Language Server Protocol Implementation

The language that stores your medical records, your bank balance,
and probably knows more about your health than you do.

MIT/Apache 2.0 License - Zane Hambly 2025
"""

import re
import json
import sys
import os
import glob
from pathlib import Path
from urllib.parse import urlparse, unquote
from typing import Dict, List, Optional, Tuple, Any, Set

# ============================================================================
# MUMPS Language Definitions
# From the 1976 ANSI Standard and 1995 Pocket Guide
# Your medical history is parsed by these regexes
# ============================================================================

# Commands - the verbs of MUMPS
# Each has a full form and abbreviation because brevity is next to godliness
MUMPS_COMMANDS = {
    'BREAK': ('B', 'Breakpoint for debugging'),
    'CLOSE': ('C', 'Close a device'),
    'DO': ('D', 'Execute a routine or subroutine'),
    'ELSE': ('E', 'Alternative execution path'),
    'FOR': ('F', 'Iteration control'),
    'GOTO': ('G', 'Transfer control (controversial since 1966)'),
    'HALT': ('H', 'Terminate execution'),
    'HANG': ('H', 'Suspend execution for specified seconds'),
    'IF': ('I', 'Conditional execution'),
    'JOB': ('J', 'Start a background process'),
    'KILL': ('K', 'Remove variables from memory'),
    'LOCK': ('L', 'Control concurrent access'),
    'MERGE': ('M', 'Copy data structures'),
    'NEW': ('N', 'Create new variable scope'),
    'OPEN': ('O', 'Open a device'),
    'QUIT': ('Q', 'Return from routine'),
    'READ': ('R', 'Read from device'),
    'SET': ('S', 'Assign values'),
    'TCOMMIT': ('TC', 'Commit transaction'),
    'TRESTART': ('TRE', 'Restart transaction'),
    'TROLLBACK': ('TRO', 'Rollback transaction'),
    'TSTART': ('TS', 'Start transaction'),
    'USE': ('U', 'Select device for I/O'),
    'VIEW': ('V', 'Implementation-specific operations'),
    'WRITE': ('W', 'Write to device'),
    'XECUTE': ('X', 'Execute string as code (exciting!)'),
}

# Intrinsic Functions - the standard library
# $PIECE alone handles 90% of string processing in healthcare IT
MUMPS_FUNCTIONS = {
    '$ASCII': ('$A', 'Get ASCII value of character'),
    '$CHAR': ('$C', 'Get character from ASCII value'),
    '$DATA': ('$D', 'Check if variable exists'),
    '$EXTRACT': ('$E', 'Extract substring'),
    '$FIND': ('$F', 'Find substring position'),
    '$FNUMBER': ('$FN', 'Format number'),
    '$GET': ('$G', 'Get value with default'),
    '$INCREMENT': ('$I', 'Atomically increment a variable'),
    '$JUSTIFY': ('$J', 'Right-justify string'),
    '$LENGTH': ('$L', 'Get string/list length'),
    '$NAME': ('$NA', 'Get variable name reference'),
    '$NEXT': ('$N', 'Get next subscript (deprecated)'),
    '$ORDER': ('$O', 'Get next subscript in sequence'),
    '$PIECE': ('$P', 'Extract delimited piece (the workhorse)'),
    '$QLENGTH': ('$QL', 'Get subscript count'),
    '$QSUBSCRIPT': ('$QS', 'Get specific subscript'),
    '$QUERY': ('$Q', 'Get next node reference'),
    '$RANDOM': ('$R', 'Generate random number'),
    '$REVERSE': ('$RE', 'Reverse string'),
    '$SELECT': ('$S', 'Conditional expression'),
    '$STACK': ('$ST', 'Get stack information'),
    '$TEXT': ('$T', 'Get routine source line'),
    '$TRANSLATE': ('$TR', 'Character translation'),
    '$VIEW': ('$V', 'Implementation-specific function'),
}

# Special Variables - system state
# $HOROLOG has been counting since 1840. Yes, really.
MUMPS_SPECIAL_VARS = {
    '$DEVICE': ('$D', 'Device status'),
    '$ECODE': ('$EC', 'Error codes'),
    '$ESTACK': ('$ES', 'Error stack level'),
    '$ETRAP': ('$ET', 'Error trap'),
    '$HOROLOG': ('$H', 'Date/time since Dec 31, 1840'),
    '$IO': ('$I', 'Current I/O device'),
    '$JOB': ('$J', 'Process identifier'),
    '$KEY': ('$K', 'Terminator from last READ'),
    '$PRINCIPAL': ('$P', 'Principal device'),
    '$QUIT': ('$Q', 'Quit context flag'),
    '$REFERENCE': ('$R', 'Last global reference'),
    '$STACK': ('$ST', 'Stack level'),
    '$STORAGE': ('$S', 'Available storage'),
    '$SYSTEM': ('$SY', 'System identifier'),
    '$TEST': ('$T', 'Result of last IF'),
    '$TLEVEL': ('$TL', 'Transaction level'),
    '$TRESTART': ('$TR', 'Transaction restart count'),
    '$X': ('$X', 'Horizontal cursor position'),
    '$Y': ('$Y', 'Vertical cursor position'),
}

# Structured System Variables - database metadata
MUMPS_SSVN = {
    '^$CHARACTER': ('^$C', 'Character set information'),
    '^$DEVICE': ('^$D', 'Device information'),
    '^$GLOBAL': ('^$G', 'Global directory'),
    '^$JOB': ('^$J', 'Job information'),
    '^$LOCK': ('^$L', 'Lock information'),
    '^$ROUTINE': ('^$R', 'Routine information'),
    '^$SYSTEM': ('^$S', 'System information'),
}

# MUMPS file extensions
MUMPS_EXTENSIONS = ['*.m', '*.mps', '*.mumps', '*.ros', '*.int']


def uri_to_path(uri: str) -> str:
    """Convert file URI to filesystem path."""
    parsed = urlparse(uri)
    path = unquote(parsed.path)
    # On Windows, remove leading slash from /C:/path
    if sys.platform == 'win32' and path.startswith('/') and len(path) > 2 and path[2] == ':':
        path = path[1:]
    return path


def path_to_uri(path: str) -> str:
    """Convert filesystem path to file URI."""
    path = os.path.abspath(path)
    if sys.platform == 'win32':
        path = '/' + path.replace('\\', '/')
    return f'file://{path}'


class WorkspaceIndex:
    """
    Index of all MUMPS routines in the workspace.

    Enables cross-file navigation - the killer feature for MUMPS.
    When you see D ^ROUTINE, you can actually go to that routine.
    Your predecessors were not so lucky.
    """

    def __init__(self):
        # routine_name -> (uri, MUMPSDocument)
        self.routines: Dict[str, Tuple[str, MUMPSDocument]] = {}
        self.workspace_root: Optional[str] = None

    def set_workspace_root(self, root: str):
        """Set workspace root and scan for routines."""
        self.workspace_root = root
        self.scan_workspace()

    def scan_workspace(self):
        """Scan workspace for all MUMPS files."""
        if not self.workspace_root:
            return

        self.routines.clear()

        for ext in MUMPS_EXTENSIONS:
            pattern = os.path.join(self.workspace_root, '**', ext)
            for filepath in glob.glob(pattern, recursive=True):
                self.index_file(filepath)

    def index_file(self, filepath: str):
        """Index a single MUMPS file."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            uri = path_to_uri(filepath)
            doc = MUMPSDocument(uri, content)
            routine_name = Path(filepath).stem
            self.routines[routine_name] = (uri, doc)
        except Exception:
            pass  # Skip files we can't read

    def update_document(self, uri: str, doc: 'MUMPSDocument'):
        """Update index when a document changes."""
        path = uri_to_path(uri)
        routine_name = Path(path).stem
        self.routines[routine_name] = (uri, doc)

    def remove_document(self, uri: str):
        """Remove document from index."""
        path = uri_to_path(uri)
        routine_name = Path(path).stem
        if routine_name in self.routines:
            del self.routines[routine_name]

    def find_routine(self, name: str) -> Optional[Tuple[str, 'MUMPSDocument']]:
        """Find a routine by name."""
        return self.routines.get(name)

    def find_label_in_routine(self, label: str, routine: str) -> Optional[Tuple[str, int]]:
        """Find a label in a specific routine. Returns (uri, line_num)."""
        result = self.find_routine(routine)
        if result:
            uri, doc = result
            if label in doc.labels:
                line_num, _ = doc.labels[label]
                return (uri, line_num)
        return None

    def find_all_references_to_routine(self, routine_name: str) -> List[Tuple[str, int, int]]:
        """Find all calls to a routine across workspace. Returns [(uri, line, char)]."""
        refs = []
        for name, (uri, doc) in self.routines.items():
            for line_num, char_pos, label, routine in doc.routine_calls:
                if routine == routine_name:
                    refs.append((uri, line_num, char_pos))
        return refs

    def find_all_references_to_label(self, label: str, routine: str) -> List[Tuple[str, int, int]]:
        """Find all calls to a specific label in a routine. Returns [(uri, line, char)]."""
        refs = []
        for name, (uri, doc) in self.routines.items():
            for line_num, char_pos, call_label, call_routine in doc.routine_calls:
                if call_routine == routine and call_label == label:
                    refs.append((uri, line_num, char_pos))
        return refs

    def get_all_routine_names(self) -> List[str]:
        """Get all known routine names."""
        return list(self.routines.keys())


class MUMPSDocument:
    """
    Represents a parsed MUMPS document.

    MUMPS code structure:
    - Lines start with optional label, then dot-levels, then commands
    - Labels can have formal parameters (like LABEL(param1,param2))
    - Everything after ; is a comment
    - Global variables start with ^
    - Local variables are just identifiers
    """

    def __init__(self, uri: str, content: str):
        self.uri = uri
        self.content = content
        self.lines = content.split('\n')
        self.labels: Dict[str, Tuple[int, Optional[List[str]]]] = {}
        self.variables: Dict[str, List[int]] = {}
        self.globals: Dict[str, List[int]] = {}
        # Track routine calls: list of (line_num, char_pos, label, routine_name)
        self.routine_calls: List[Tuple[int, int, Optional[str], str]] = []
        self.parse()

    @property
    def routine_name(self) -> str:
        """Get routine name from URI (filename without extension)."""
        path = uri_to_path(self.uri)
        return Path(path).stem if path else ''

    def parse(self):
        """Parse the document for symbols."""
        # Label pattern: start of line, optional %, alphanumeric, optional params
        label_pattern = re.compile(r'^(%?[A-Za-z][A-Za-z0-9]*)(?:\(([^)]*)\))?')
        # Variable pattern: local variable (not preceded by $ or ^)
        var_pattern = re.compile(r'(?<![$^%])(?<![A-Za-z])([A-Za-z][A-Za-z0-9]*)\b')
        # Global pattern: ^ followed by optional % and name
        global_pattern = re.compile(r'\^(%?[A-Za-z][A-Za-z0-9]*)')
        # Routine call patterns:
        # D ^ROUTINE, DO ^ROUTINE, G ^ROUTINE, GOTO ^ROUTINE
        # D LABEL^ROUTINE, $$LABEL^ROUTINE, etc.
        routine_call_pattern = re.compile(
            r'(?:(?:D|DO|G|GOTO|JOB|J)\s+)?'  # Optional command
            r'(?:\$\$)?'  # Optional $$ for extrinsic
            r'(%?[A-Za-z][A-Za-z0-9]*)?'  # Optional label
            r'\^(%?[A-Za-z][A-Za-z0-9]*)'  # ^ROUTINE (required)
        )

        for line_num, line in enumerate(self.lines):
            # Check for label at start of line
            if line and not line[0].isspace() and line[0] != ';':
                match = label_pattern.match(line)
                if match:
                    label_name = match.group(1)
                    params_str = match.group(2)
                    params = None
                    if params_str:
                        params = [p.strip() for p in params_str.split(',')]
                    self.labels[label_name] = (line_num, params)

            # Find variables (skip comment portion)
            code_part = line.split(';')[0] if ';' in line else line

            # Find local variables
            for match in var_pattern.finditer(code_part):
                var_name = match.group(1)
                # Skip if it's a command abbreviation
                if var_name.upper() in ['B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
                                         'K', 'L', 'M', 'N', 'O', 'Q', 'R', 'S', 'U',
                                         'V', 'W', 'X']:
                    continue
                if var_name not in self.variables:
                    self.variables[var_name] = []
                self.variables[var_name].append(line_num)

            # Find global variables
            for match in global_pattern.finditer(code_part):
                global_name = match.group(1)
                if global_name not in self.globals:
                    self.globals[global_name] = []
                self.globals[global_name].append(line_num)

            # Find routine calls (^ROUTINE references)
            for match in routine_call_pattern.finditer(code_part):
                label = match.group(1)  # May be None
                routine = match.group(2)
                if routine:
                    self.routine_calls.append((line_num, match.start(), label, routine))

    def get_word_at_position(self, line: int, character: int) -> Optional[str]:
        """Get the word at the given position."""
        if line >= len(self.lines):
            return None

        line_text = self.lines[line]
        if character >= len(line_text):
            return None

        # Find word boundaries
        start = character
        while start > 0 and (line_text[start - 1].isalnum() or line_text[start - 1] in '$^%'):
            start -= 1

        end = character
        while end < len(line_text) and (line_text[end].isalnum() or line_text[end] in '$^%'):
            end += 1

        return line_text[start:end] if start < end else None


class MUMPSLanguageServer:
    """
    MUMPS Language Server

    Implements LSP for the language that runs healthcare.
    Every prescription, every diagnosis, every bill - probably MUMPS.
    Now with cross-file navigation, because D ^ROUTINE should actually work.
    """

    def __init__(self):
        self.documents: Dict[str, MUMPSDocument] = {}
        self.workspace_index = WorkspaceIndex()
        self.running = True

    def send_message(self, message: dict):
        """Send a JSON-RPC message to the client."""
        content = json.dumps(message)
        header = f'Content-Length: {len(content)}\r\n\r\n'
        sys.stdout.write(header + content)
        sys.stdout.flush()

    def send_response(self, request_id: Any, result: Any):
        """Send a response to a request."""
        self.send_message({
            'jsonrpc': '2.0',
            'id': request_id,
            'result': result
        })

    def send_error(self, request_id: Any, code: int, message: str):
        """Send an error response."""
        self.send_message({
            'jsonrpc': '2.0',
            'id': request_id,
            'error': {'code': code, 'message': message}
        })

    def read_message(self) -> Optional[dict]:
        """Read a JSON-RPC message from stdin."""
        try:
            headers = {}
            while True:
                line = sys.stdin.readline()
                if not line:
                    return None
                line = line.strip()
                if not line:
                    break
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()

            content_length = int(headers.get('Content-Length', 0))
            if content_length > 0:
                content = sys.stdin.read(content_length)
                return json.loads(content)
        except Exception:
            return None
        return None

    def handle_initialize(self, params: dict) -> dict:
        """Handle initialize request."""
        # Get workspace root for cross-file navigation
        root_uri = params.get('rootUri') or params.get('rootPath')
        if root_uri:
            if root_uri.startswith('file://'):
                root_path = uri_to_path(root_uri)
            else:
                root_path = root_uri
            self.workspace_index.set_workspace_root(root_path)

        return {
            'capabilities': {
                'textDocumentSync': {
                    'openClose': True,
                    'change': 1,  # Full sync
                    'save': {'includeText': True}
                },
                'completionProvider': {
                    'triggerCharacters': ['$', '^', '.', '('],
                    'resolveProvider': False
                },
                'hoverProvider': True,
                'definitionProvider': True,
                'referencesProvider': True,
                'documentSymbolProvider': True,
                'workspaceSymbolProvider': True,  # Cross-file symbol search
            },
            'serverInfo': {
                'name': 'MUMPS Language Server',
                'version': '1.1.0'
            }
        }

    def handle_completion(self, params: dict) -> List[dict]:
        """Provide completion items."""
        uri = params['textDocument']['uri']
        position = params['position']

        doc = self.documents.get(uri)
        if not doc:
            return []

        line = position['line']
        character = position['character']

        if line >= len(doc.lines):
            return []

        line_text = doc.lines[line]
        prefix = line_text[:character] if character <= len(line_text) else line_text

        completions = []

        # Check what kind of completion we need
        if prefix.rstrip().endswith('$') or '$' in prefix.split()[-1] if prefix.split() else False:
            # Function or special variable completion
            for func, (abbrev, desc) in MUMPS_FUNCTIONS.items():
                completions.append({
                    'label': func,
                    'kind': 3,  # Function
                    'detail': f'({abbrev}) {desc}',
                    'insertText': func[1:],  # Skip the $
                    'documentation': desc
                })
            for var, (abbrev, desc) in MUMPS_SPECIAL_VARS.items():
                completions.append({
                    'label': var,
                    'kind': 6,  # Variable
                    'detail': f'({abbrev}) {desc}',
                    'insertText': var[1:],
                    'documentation': desc
                })

        elif prefix.rstrip().endswith('^') or ('^' in prefix and '$' not in prefix.split('^')[-1]):
            # Global variable or SSVN completion
            for ssvn, (abbrev, desc) in MUMPS_SSVN.items():
                completions.append({
                    'label': ssvn,
                    'kind': 6,  # Variable
                    'detail': f'({abbrev}) {desc}',
                    'insertText': ssvn[1:],
                    'documentation': desc
                })
            # Also suggest known globals from the document
            for global_name in doc.globals.keys():
                completions.append({
                    'label': f'^{global_name}',
                    'kind': 6,
                    'detail': 'Global variable',
                    'insertText': global_name
                })

        else:
            # Command completion (at start of command position)
            for cmd, (abbrev, desc) in MUMPS_COMMANDS.items():
                completions.append({
                    'label': cmd,
                    'kind': 14,  # Keyword
                    'detail': f'({abbrev}) {desc}',
                    'documentation': desc
                })
                # Also offer abbreviation
                completions.append({
                    'label': abbrev,
                    'kind': 14,
                    'detail': f'{cmd} - {desc}',
                    'documentation': desc
                })

            # Add labels from document
            for label, (line_num, params) in doc.labels.items():
                param_str = f'({", ".join(params)})' if params else ''
                completions.append({
                    'label': label,
                    'kind': 12,  # Function
                    'detail': f'Label at line {line_num + 1}{param_str}',
                })

            # Add local variables
            for var_name in doc.variables.keys():
                completions.append({
                    'label': var_name,
                    'kind': 6,  # Variable
                    'detail': 'Local variable'
                })

        return completions

    def handle_hover(self, params: dict) -> Optional[dict]:
        """Provide hover information."""
        uri = params['textDocument']['uri']
        position = params['position']

        doc = self.documents.get(uri)
        if not doc:
            return None

        word = doc.get_word_at_position(position['line'], position['character'])
        if not word:
            return None

        word_upper = word.upper()

        # Check commands
        if word_upper in MUMPS_COMMANDS:
            abbrev, desc = MUMPS_COMMANDS[word_upper]
            return {
                'contents': {
                    'kind': 'markdown',
                    'value': f'**{word_upper}** (abbrev: {abbrev})\n\nCommand: {desc}'
                }
            }

        # Check command abbreviations
        for cmd, (abbrev, desc) in MUMPS_COMMANDS.items():
            if word_upper == abbrev:
                return {
                    'contents': {
                        'kind': 'markdown',
                        'value': f'**{abbrev}** ({cmd})\n\nCommand: {desc}'
                    }
                }

        # Check functions (with $)
        if word.startswith('$'):
            func_upper = word.upper()
            if func_upper in MUMPS_FUNCTIONS:
                abbrev, desc = MUMPS_FUNCTIONS[func_upper]
                return {
                    'contents': {
                        'kind': 'markdown',
                        'value': f'**{func_upper}** (abbrev: {abbrev})\n\nIntrinsic function: {desc}'
                    }
                }
            # Check special variables
            if func_upper in MUMPS_SPECIAL_VARS:
                abbrev, desc = MUMPS_SPECIAL_VARS[func_upper]
                return {
                    'contents': {
                        'kind': 'markdown',
                        'value': f'**{func_upper}** (abbrev: {abbrev})\n\nSpecial variable: {desc}'
                    }
                }

        # Check SSVNs (with ^$)
        if word.startswith('^$'):
            ssvn_upper = word.upper()
            if ssvn_upper in MUMPS_SSVN:
                abbrev, desc = MUMPS_SSVN[ssvn_upper]
                return {
                    'contents': {
                        'kind': 'markdown',
                        'value': f'**{ssvn_upper}** (abbrev: {abbrev})\n\nStructured system variable: {desc}'
                    }
                }

        # Check labels
        if word in doc.labels:
            line_num, params = doc.labels[word]
            param_str = f'Parameters: {", ".join(params)}' if params else 'No parameters'
            return {
                'contents': {
                    'kind': 'markdown',
                    'value': f'**{word}**\n\nLabel at line {line_num + 1}\n\n{param_str}'
                }
            }

        # Check global variables
        if word.startswith('^'):
            global_name = word[1:]
            if global_name in doc.globals:
                lines = doc.globals[global_name]
                return {
                    'contents': {
                        'kind': 'markdown',
                        'value': f'**{word}**\n\nGlobal variable\n\nReferenced on lines: {", ".join(str(l+1) for l in lines[:10])}'
                    }
                }

        # Check local variables
        if word in doc.variables:
            lines = doc.variables[word]
            return {
                'contents': {
                    'kind': 'markdown',
                    'value': f'**{word}**\n\nLocal variable\n\nReferenced on lines: {", ".join(str(l+1) for l in lines[:10])}'
                }
            }

        return None

    def handle_definition(self, params: dict) -> Optional[dict]:
        """Go to definition - now with cross-file support!"""
        uri = params['textDocument']['uri']
        position = params['position']

        doc = self.documents.get(uri)
        if not doc:
            return None

        line_num = position['line']
        char_pos = position['character']

        # Get the full line to check for routine references
        if line_num < len(doc.lines):
            line_text = doc.lines[line_num]

            # Check if we're on a routine call like LABEL^ROUTINE or ^ROUTINE
            routine_pattern = re.compile(
                r'(%?[A-Za-z][A-Za-z0-9]*)?\^(%?[A-Za-z][A-Za-z0-9]*)'
            )
            for match in routine_pattern.finditer(line_text):
                if match.start() <= char_pos <= match.end():
                    label = match.group(1)
                    routine = match.group(2)

                    # Try to find the routine in workspace
                    result = self.workspace_index.find_routine(routine)
                    if result:
                        target_uri, target_doc = result

                        # If label specified, find that label
                        if label and label in target_doc.labels:
                            target_line, _ = target_doc.labels[label]
                        else:
                            target_line = 0  # Go to top of routine

                        return {
                            'uri': target_uri,
                            'range': {
                                'start': {'line': target_line, 'character': 0},
                                'end': {'line': target_line, 'character': 0}
                            }
                        }

        word = doc.get_word_at_position(line_num, char_pos)
        if not word:
            return None

        # Check if it's a label in current document
        if word in doc.labels:
            label_line, _ = doc.labels[word]
            return {
                'uri': uri,
                'range': {
                    'start': {'line': label_line, 'character': 0},
                    'end': {'line': label_line, 'character': len(word)}
                }
            }

        # For variables, go to first reference
        if word in doc.variables and doc.variables[word]:
            first_line = doc.variables[word][0]
            return {
                'uri': uri,
                'range': {
                    'start': {'line': first_line, 'character': 0},
                    'end': {'line': first_line, 'character': 0}
                }
            }

        return None

    def handle_references(self, params: dict) -> List[dict]:
        """Find all references - now searches entire workspace!"""
        uri = params['textDocument']['uri']
        position = params['position']

        doc = self.documents.get(uri)
        if not doc:
            return []

        line_num = position['line']
        char_pos = position['character']
        references = []

        # Check if we're on a routine reference
        if line_num < len(doc.lines):
            line_text = doc.lines[line_num]
            routine_pattern = re.compile(
                r'(%?[A-Za-z][A-Za-z0-9]*)?\^(%?[A-Za-z][A-Za-z0-9]*)'
            )
            for match in routine_pattern.finditer(line_text):
                if match.start() <= char_pos <= match.end():
                    label = match.group(1)
                    routine = match.group(2)

                    # Find all references to this routine across workspace
                    if label:
                        refs = self.workspace_index.find_all_references_to_label(label, routine)
                    else:
                        refs = self.workspace_index.find_all_references_to_routine(routine)

                    for ref_uri, ref_line, ref_char in refs:
                        references.append({
                            'uri': ref_uri,
                            'range': {
                                'start': {'line': ref_line, 'character': ref_char},
                                'end': {'line': ref_line, 'character': ref_char + len(routine) + 1}
                            }
                        })
                    return references

        word = doc.get_word_at_position(line_num, char_pos)
        if not word:
            return []

        # Check if it's a label - search across workspace for calls to this routine+label
        if word in doc.labels:
            routine_name = Path(uri_to_path(uri)).stem

            # Find references in current file
            pattern = re.compile(rf'\b{re.escape(word)}\b')
            for ln, line in enumerate(doc.lines):
                for match in pattern.finditer(line):
                    references.append({
                        'uri': uri,
                        'range': {
                            'start': {'line': ln, 'character': match.start()},
                            'end': {'line': ln, 'character': match.end()}
                        }
                    })

            # Find cross-file references (LABEL^ROUTINE calls)
            for ref_uri, ref_line, ref_char in self.workspace_index.find_all_references_to_label(word, routine_name):
                references.append({
                    'uri': ref_uri,
                    'range': {
                        'start': {'line': ref_line, 'character': ref_char},
                        'end': {'line': ref_line, 'character': ref_char + len(word)}
                    }
                })

        # Check variables (local to file)
        elif word in doc.variables:
            pattern = re.compile(rf'(?<![A-Za-z]){re.escape(word)}\b')
            for ln, line in enumerate(doc.lines):
                for match in pattern.finditer(line):
                    references.append({
                        'uri': uri,
                        'range': {
                            'start': {'line': ln, 'character': match.start()},
                            'end': {'line': ln, 'character': match.end()}
                        }
                    })

        # Check globals - search across entire workspace
        elif word.startswith('^'):
            global_name = word[1:]
            pattern = re.compile(rf'\^{re.escape(global_name)}\b')

            # Search all indexed documents
            for routine_name, (doc_uri, indexed_doc) in self.workspace_index.routines.items():
                for ln, line in enumerate(indexed_doc.lines):
                    for match in pattern.finditer(line):
                        references.append({
                            'uri': doc_uri,
                            'range': {
                                'start': {'line': ln, 'character': match.start()},
                                'end': {'line': ln, 'character': match.end()}
                            }
                        })

        return references

    def handle_document_symbol(self, params: dict) -> List[dict]:
        """Provide document symbols."""
        uri = params['textDocument']['uri']
        doc = self.documents.get(uri)
        if not doc:
            return []

        symbols = []

        # Add labels as functions
        for label, (line_num, params) in doc.labels.items():
            param_str = f'({", ".join(params)})' if params else ''
            symbols.append({
                'name': label + param_str,
                'kind': 12,  # Function
                'range': {
                    'start': {'line': line_num, 'character': 0},
                    'end': {'line': line_num, 'character': len(label)}
                },
                'selectionRange': {
                    'start': {'line': line_num, 'character': 0},
                    'end': {'line': line_num, 'character': len(label)}
                }
            })

        # Add globals as variables
        for global_name, lines in doc.globals.items():
            if lines:
                symbols.append({
                    'name': f'^{global_name}',
                    'kind': 13,  # Variable
                    'range': {
                        'start': {'line': lines[0], 'character': 0},
                        'end': {'line': lines[0], 'character': len(global_name) + 1}
                    },
                    'selectionRange': {
                        'start': {'line': lines[0], 'character': 0},
                        'end': {'line': lines[0], 'character': len(global_name) + 1}
                    }
                })

        return symbols

    def handle_did_open(self, params: dict):
        """Handle textDocument/didOpen."""
        uri = params['textDocument']['uri']
        text = params['textDocument']['text']
        doc = MUMPSDocument(uri, text)
        self.documents[uri] = doc
        # Update workspace index
        self.workspace_index.update_document(uri, doc)

    def handle_did_change(self, params: dict):
        """Handle textDocument/didChange."""
        uri = params['textDocument']['uri']
        changes = params.get('contentChanges', [])
        if changes:
            # Full sync mode - take the whole content
            text = changes[0].get('text', '')
            doc = MUMPSDocument(uri, text)
            self.documents[uri] = doc
            # Update workspace index
            self.workspace_index.update_document(uri, doc)

    def handle_did_close(self, params: dict):
        """Handle textDocument/didClose."""
        uri = params['textDocument']['uri']
        if uri in self.documents:
            del self.documents[uri]
        # Note: we don't remove from workspace index - file still exists

    def handle_workspace_symbol(self, params: dict) -> List[dict]:
        """Handle workspace/symbol - search all routines and labels."""
        query = params.get('query', '').lower()
        symbols = []

        for routine_name, (uri, doc) in self.workspace_index.routines.items():
            # Add routine itself
            if not query or query in routine_name.lower():
                symbols.append({
                    'name': routine_name,
                    'kind': 12,  # Function
                    'location': {
                        'uri': uri,
                        'range': {
                            'start': {'line': 0, 'character': 0},
                            'end': {'line': 0, 'character': 0}
                        }
                    },
                    'containerName': 'Routine'
                })

            # Add labels within routine
            for label, (line_num, label_params) in doc.labels.items():
                if not query or query in label.lower():
                    param_str = f'({", ".join(label_params)})' if label_params else ''
                    symbols.append({
                        'name': f'{label}{param_str}',
                        'kind': 12,  # Function
                        'location': {
                            'uri': uri,
                            'range': {
                                'start': {'line': line_num, 'character': 0},
                                'end': {'line': line_num, 'character': len(label)}
                            }
                        },
                        'containerName': routine_name
                    })

        return symbols

    def run(self):
        """Main server loop."""
        while self.running:
            message = self.read_message()
            if message is None:
                break

            method = message.get('method', '')
            params = message.get('params', {})
            request_id = message.get('id')

            try:
                if method == 'initialize':
                    result = self.handle_initialize(params)
                    self.send_response(request_id, result)

                elif method == 'initialized':
                    pass  # No response needed

                elif method == 'shutdown':
                    self.send_response(request_id, None)

                elif method == 'exit':
                    self.running = False

                elif method == 'textDocument/didOpen':
                    self.handle_did_open(params)

                elif method == 'textDocument/didChange':
                    self.handle_did_change(params)

                elif method == 'textDocument/didClose':
                    self.handle_did_close(params)

                elif method == 'textDocument/completion':
                    result = self.handle_completion(params)
                    self.send_response(request_id, result)

                elif method == 'textDocument/hover':
                    result = self.handle_hover(params)
                    self.send_response(request_id, result)

                elif method == 'textDocument/definition':
                    result = self.handle_definition(params)
                    self.send_response(request_id, result)

                elif method == 'textDocument/references':
                    result = self.handle_references(params)
                    self.send_response(request_id, result)

                elif method == 'textDocument/documentSymbol':
                    result = self.handle_document_symbol(params)
                    self.send_response(request_id, result)

                elif method == 'workspace/symbol':
                    result = self.handle_workspace_symbol(params)
                    self.send_response(request_id, result)

                elif request_id is not None:
                    # Unknown method with ID - send empty response
                    self.send_response(request_id, None)

            except Exception as e:
                if request_id is not None:
                    self.send_error(request_id, -32603, str(e))


if __name__ == '__main__':
    server = MUMPSLanguageServer()
    server.run()
