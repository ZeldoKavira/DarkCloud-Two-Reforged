#!/usr/bin/env python3
"""Decompile Dark Cloud 2 SB2 script bytecode to readable pseudo-code."""

import struct
import sys
from pathlib import Path

# VM opcodes from exe__10CRunScriptFP8vmcode_t
OPCODES = {
    0x01: "LOAD",       # Load variable (arg2 = var type, arg1 = index)
    0x02: "LOAD_REF",   # Load variable reference
    0x03: "PUSH",       # Push constant (arg1 = type: 1=int, 2=float, 3=string)
    0x04: "POP",        # Pop stack
    0x05: "ASSIGN",     # Assignment
    0x06: "ADD",        # Addition
    0x07: "SUB",        # Subtraction
    0x08: "MUL",        # Multiplication
    0x09: "DIV",        # Division
    0x0A: "MOD",        # Modulo
    0x0B: "NEG",        # Negate
    0x0C: "ITOF",       # Int to float
    0x0D: "FTOI",       # Float to int
    0x0E: "CMP",        # Compare (arg1 = comparison type)
    0x0F: "RET",        # Return
    0x10: "JMP",        # Unconditional jump (arg1 = offset)
    0x11: "JZ",         # Jump if zero (arg1 = offset)
    0x12: "JNZ",        # Jump if not zero (arg1 = offset)
    0x13: "CALL",       # Call function (arg2 = funcdata offset)
    0x14: "PRINT",      # Debug print
    0x15: "EXT",        # External function call (arg1 = func_id)
    0x17: "WAIT",       # Wait/yield
    0x18: "AND",        # Bitwise AND
    0x19: "OR",         # Bitwise OR
    0x1A: "NOT",        # Logical NOT
    0x1B: "END",        # End script
    0x1C: "RESUME",     # Resume from wait
    0x1D: "SIN",        # Sine
    0x1E: "COS",        # Cosine
}

# Comparison sub-opcodes (for opcode 0x0E)
CMP_OPS = {
    0x28: "==",
    0x29: "!=",
    0x2A: "<",
    0x2B: "<=",
    0x2C: ">",
    0x2D: ">=",
}

# Variable types (for LOAD/LOAD_REF arg2)
VAR_TYPES = {
    0x01: "local",
    0x02: "local[]",
    0x04: "local[][]",
    0x08: "param",
    0x10: "param[]",
    0x20: "param[][]",
    0x40: "global",
    0x200: "global",
}

# External function ID to name mapping (dungeon scripts)
EXT_FUNCS = {
    0: "_NORMAL_VECTOR",
    1: "_COPY_VECTOR",
    2: "_ADD_VECTOR",
    3: "_SUB_VECTOR",
    4: "_SCALE_VECTOR",
    5: "_DIV_VECTOR",
    6: "_ANGLE_CMP",
    7: "_ANGLE_LIMIT",
    8: "_SQRT",
    9: "_ATAN2F",
    10: "_ND_TEST",
    11: "_GET_DIST_VECTOR",
    12: "_GET_DIST_VECTOR2",
    13: "_CALC_IP_CIRCLE_LINE",
    14: "_GET_ANGLE_INNER",
    21: "_MY_SE_PLAY",
    22: "_MY_SE_STOP",
    23: "_MONS_SE_PLAY",
    24: "_MONS_SE_STOP",
    25: "_SET_CAMERA_NEXT_REF",
    26: "_SET_CAMERA_FOLLOW",
    27: "_SET_CAMERA_NEXT_POS",
    28: "_SET_CAMERA_MODE",
    29: "_SET_CAMERA_SPEED",
    30: "_CAMERA_QUAKE",
    31: "_SET_CAMERA_CTRL_PARAM1",
    32: "_SET_CAMERA_CTRL_PARAM2",
    33: "_RESET_CAMERA_CTRL_PARAM",
    35: "_GET_RND",
    36: "_GET_RNDF",
    37: "_V_PUSH",
    38: "_V_POP",
    39: "_GET_MONSTER_NUM",
    40: "_GET_MONSTER_INDEX",
    41: "_GET_MONSTER_ID",
    42: "_GET_USERID",
    43: "_GET_USER_MONS_ID",
    44: "_RESET_TIMER",
    45: "_GET_TIMER",
    46: "_CREATE_MONSTER",
    47: "_RUN_EVENT_SCRIPT",
    48: "_GET_FRAME_POS",
    49: "_GET_OBJ_POS",
    50: "_GET_MAPOBJ_POS",
    51: "_SET_PAUSE",
    52: "_CHECK_PAUSE",
    53: "_GET_BIT_FLAG",
    54: "_SET_BIT_FLAG",
    55: "_GET_ATT_TYPE",
    56: "_GET_USER_ATTR",
    57: "_TRANS_RESERV_IMG",
    58: "_GET_STS_ATTR",
    59: "_V_PUSH2",
    60: "_V_POP2",
    61: "_SET_LOCKON_MODE",
    62: "_SET_MOTION_BLUR",
    63: "_SET_MAPOBJ_SHOW",
    64: "_GET_EVENT_INFO",
    65: "_MONS_SE_LOOP",
    66: "_MONS_VOL_CTRL",
    70: "_GET_DIST",
    71: "_SEARCH_AREA",
    72: "_GET_PLACE_POS",
    73: "_SET_PLACE_POS",
    74: "_GET_INDEX_POS",
    75: "_GET_POS",
    76: "_SET_POS",
    77: "_GET_ROT",
    78: "_SET_ROT",
    79: "_SET_NEXT_ROT",
    80: "_SET_NEXT_POS",
    81: "_CHK_MOVE_END",
    82: "_RESET_MOVE",
    83: "_GET_TARGET_POS",
    84: "_GET_TARGET_DIST",
    85: "_GET_TARGET_ANGLE",
    86: "_GET_TARGET_REF_POS",
    87: "_GET_REF_DIR",
    88: "_GET_REFANGLE_POS",
    89: "_GET_TARGET_ROT",
    90: "_GET_REF_ANGLE",
    91: "_GET_HIGH",
    92: "_GET_NEAR_MONS_POS",
    93: "_GET_TARGET_OLD_POS",
    94: "_GET_TARGET_SPEED",
    95: "_CALC_MOVE_NEXT_POS",
    96: "_GET_POSREF_ANGLE",
    97: "_GET_ACTIVE_MONS_POS",
    98: "_GET_ACTIVE_MONS_ROT",
    99: "_GET_ACTIVE_MONS_DIST",
    100: "_GET_ACTIVE_MONS_ANGLE",
    101: "_GET_REF_ROT",
    102: "_GET_REF_ROT2",
    103: "_FLYING_SEARCH_AREA",
    104: "_GET_HIGH2",
    105: "_GET_RANGE_MONS_ID",
    106: "_GET_ENTRY_OBJ_POS",
    108: "_SEARCH_AREA2",
    110: "_SET_OBJ",
    111: "_SET_BODY",
    112: "_SET_DMG",
    113: "_SET_DMG2",
    114: "_LINK_MAP_TO_OBJECT",
    115: "_LINK_OBJECT_TO_PIECE",
    116: "_LOAD_EFFECT_SCRIPT",
    117: "_SET_SCOOP",
    118: "_LOAD_RESERV_IMG",
    119: "_SET_PRIORITY_LIMMIT",
    120: "_SET_MODEL_LIGHT_SWITCH",
    121: "_SET_MODEL_LIGHT_COLOR",
    122: "_SET_ALPHA",
    123: "_SET_SCALE",
    124: "_SET_INDEX_ALPHA",
    125: "_SET_PALLET_ANIM",
    126: "_RESET_PALLET_ANIM",
    127: "_SET_ATTRIB",
    128: "_SET_STATUS",
    129: "_SET_INT_FLAG",
    130: "_SET_ACT_STATUS",
    131: "_SET_MUTEKI",
    132: "_SET_GRAVITY",
    133: "_SET_COLLISION",
    134: "_GET_GEKIRIN",
    135: "_GET_PRIORITY",
    136: "_SET_CLIP_DIST",
    137: "_SET_PIYORI_MARK",
    138: "_CHECK_PIYORI",
    139: "_GET_SCALE",
    140: "_GET_MONS_WIDTH",
    150: "_BLOW_START",
    151: "_SET_DEAD_START",
    152: "_SET_DEAD_OFF",
    153: "_SET_SHROW_END",
    160: "_GET_BASE_ATTACK",
    161: "_SET_DEF_RATE",
    162: "_SET_MONSTER_LIFE",
    163: "_GET_MONSTER_LIFE",
    164: "_GET_NO_DAMAGE_CNT",
    165: "_GET_ACTIVE_MONS_LIFEI",
    166: "_GET_ACTIVE_MONS_LIFEF",
    167: "_SET_ACTIVE_MONS_LIFEI",
    168: "_SET_ACTIVE_MONS_LIFEF",
    169: "_GET_ACTIVE_MONS_MAX_LIFE",
    170: "_SET_DAMAGE_SCORE",
    171: "_GET_MONS_GRADE",
    172: "_SET_GUARD_RATE",
    173: "_SET_ESCAPE_RATE",
    174: "_SET_EXT_PARAM_RATE",
    175: "_GET_BOSS_FLAG",
    176: "_SET_INDEXOBJ_SIZE",
    177: "_GET_INDEXOBJ_SIZE",
    180: "_RESET_MOTION",
    182: "_SET_MOS",
    183: "_CHECK_MOS_END",
    184: "_NOW_MOS_WAIT",
    185: "_GET_MOS_STATUS",
    191: "_ESM_CREATE",
    192: "_ESM_FINISH",
    193: "_ESM_DELETE",
    194: "_ESM_SET_VECT1",
    195: "_ESM_GET_VECT1",
    196: "_ESM_SET_VECT2",
    197: "_ESM_GET_VECT2",
    198: "_ESM_SET_TARGET_ID",
    199: "_ESM_GET_TARGET_ID",
    200: "_ESM_SET_USER_ID",
    201: "_ESM_GET_USER_ID",
    202: "_ESM_SET_VALUE",
    203: "_SW_EFFECT",
    204: "_ESM_GET_NOTUESD_TEXB",
    205: "_ESM_ADD_TEXB",
    206: "_SHOT_ROCKET_LAUNCHER",
    207: "_ESM_ALL_CLEAR",
}


class SB2Decompiler:
    def __init__(self, data: bytes):
        self.data = data
        self.parse_header()
    
    def parse_header(self):
        """Parse SB2 header."""
        magic = self.data[0:4]
        if magic != b'SB2\x00':
            raise ValueError(f"Invalid magic: {magic}")
        
        # Header fields
        self.total_size = struct.unpack_from('<I', self.data, 0x04)[0]
        self.string_table_off = struct.unpack_from('<I', self.data, 0x08)[0]
        self.func_table_off = struct.unpack_from('<I', self.data, 0x0C)[0]
        self.func_count = struct.unpack_from('<I', self.data, 0x10)[0]
        self.global_count = struct.unpack_from('<I', self.data, 0x18)[0]
    
    def get_string(self, offset: int) -> str:
        """Get null-terminated string from string table."""
        abs_off = self.string_table_off + offset
        end = self.data.find(b'\x00', abs_off)
        if end == -1:
            end = abs_off + 64
        return self.data[abs_off:end].decode('ascii', errors='replace')
    
    def get_functions(self) -> list:
        """Get list of (func_id, funcdata_offset) tuples."""
        funcs = []
        for i in range(self.func_count):
            off = self.func_table_off + i * 8
            func_id, funcdata_off = struct.unpack_from('<II', self.data, off)
            funcs.append((func_id, funcdata_off))
        return funcs
    
    def get_funcdata(self, offset: int) -> dict:
        """Parse funcdata structure. Returns None if out of bounds."""
        if offset + 16 > len(self.data):
            return None
        code_rel, field_04, local_count, param_count = struct.unpack_from('<IIII', self.data, offset)
        code_offset = self.string_table_off + code_rel
        # Check if code is within bounds
        if code_offset + 12 > len(self.data):
            return None
        return {
            'code_offset': code_offset,
            'local_count': local_count,
            'param_count': param_count,
        }
    
    def decompile_function(self, func_id: int, funcdata_off: int) -> list:
        """Decompile a single function to pseudo-code lines."""
        fd = self.get_funcdata(funcdata_off)
        lines = []
        lines.append(f"// Function 0x{func_id:04X} ({func_id})")
        
        if fd is None:
            lines.append(f"// EXTERNAL: funcdata at 0x{funcdata_off:X} is outside this script")
            lines.append(f"// (likely defined in another script file loaded at runtime)")
            lines.append("")
            return lines
        
        lines.append(f"// Locals: {fd['local_count']}, Params: {fd['param_count']}")
        lines.append(f"func_{func_id:04X}() {{")
        
        pc = fd['code_offset']
        end_pc = len(self.data)
        indent = "    "
        
        # Track labels for jumps
        labels = set()
        
        # First pass: find all jump targets
        scan_pc = pc
        while scan_pc + 12 <= end_pc:
            op, arg1, arg2 = struct.unpack_from('<III', self.data, scan_pc)
            if op in (0x10, 0x11, 0x12):  # JMP, JZ, JNZ
                target = self.string_table_off + arg1
                labels.add(target)
            if op == 0x0F or op == 0x1B:  # RET or END
                break
            scan_pc += 12
        
        # Second pass: decompile with stack tracking
        stack = []  # Track pushed values for EXT resolution
        
        while pc + 12 <= end_pc:
            if pc in labels:
                lines.append(f"label_{pc:05X}:")
                stack = []  # Clear stack at labels (conservative)
            
            op, arg1, arg2 = struct.unpack_from('<III', self.data, pc)
            op_name = OPCODES.get(op, f"UNK_{op:02X}")
            
            if op == 0x03:  # PUSH
                if arg1 == 1:  # int
                    stack.append(('int', arg2))
                    lines.append(f"{indent}push {arg2}")
                elif arg1 == 2:  # float
                    fval = struct.unpack('<f', struct.pack('<I', arg2))[0]
                    stack.append(('float', fval))
                    lines.append(f"{indent}push {fval:.4f}")
                elif arg1 == 3:  # string
                    s = self.get_string(arg2)
                    stack.append(('str', s))
                    lines.append(f'{indent}push "{s}"')
                else:
                    stack.append(('unk', arg2))
                    lines.append(f"{indent}push type={arg1} val=0x{arg2:X}")
            
            elif op == 0x01:  # LOAD
                vtype = VAR_TYPES.get(arg2, f"type_{arg2:X}")
                stack.append(('var', f"{vtype}[{arg1}]"))
                lines.append(f"{indent}load {vtype}[{arg1}]")
            
            elif op == 0x02:  # LOAD_REF
                vtype = VAR_TYPES.get(arg2, f"type_{arg2:X}")
                stack.append(('ref', f"{vtype}[{arg1}]"))
                lines.append(f"{indent}load_ref {vtype}[{arg1}]")
            
            elif op == 0x05:  # ASSIGN
                if len(stack) >= 2:
                    stack.pop()
                    stack.pop()
                lines.append(f"{indent}assign")
            
            elif op in (0x06, 0x07, 0x08, 0x09, 0x0A):  # Arithmetic
                if len(stack) >= 2:
                    stack.pop()
                    stack.pop()
                    stack.append(('result', None))
                lines.append(f"{indent}{op_name.lower()}")
            
            elif op == 0x0E:  # CMP
                cmp_op = CMP_OPS.get(arg1, f"cmp_{arg1:X}")
                if len(stack) >= 2:
                    stack.pop()
                    stack.pop()
                    stack.append(('bool', None))
                lines.append(f"{indent}cmp {cmp_op}")
            
            elif op == 0x10:  # JMP
                target = self.string_table_off + arg1
                lines.append(f"{indent}jmp label_{target:05X}")
                stack = []
            
            elif op == 0x11:  # JZ
                target = self.string_table_off + arg1
                if stack:
                    stack.pop()
                lines.append(f"{indent}jz label_{target:05X}")
            
            elif op == 0x12:  # JNZ
                target = self.string_table_off + arg1
                if stack:
                    stack.pop()
                lines.append(f"{indent}jnz label_{target:05X}")
            
            elif op == 0x13:  # CALL
                target_fd = self.string_table_off + arg2
                for fid, foff in self.get_functions():
                    if foff == target_fd:
                        lines.append(f"{indent}call func_{fid:04X}  // {arg1} args")
                        break
                else:
                    lines.append(f"{indent}call funcdata@0x{target_fd:X}  // {arg1} args")
                # Pop args, push result
                for _ in range(arg1):
                    if stack:
                        stack.pop()
                stack.append(('result', None))
            
            elif op == 0x15:  # EXT - external function call
                # arg1 = number of stack values to pop (includes function ID as first)
                # The function ID is the first value pushed (bottom of the arg stack)
                func_name = "ext_?"
                if len(stack) >= arg1 and arg1 > 0:
                    # Function ID is arg1 positions back
                    func_id_entry = stack[-(arg1)]
                    if func_id_entry[0] == 'int':
                        ext_id = func_id_entry[1]
                        func_name = EXT_FUNCS.get(ext_id, f"ext_{ext_id}")
                # Pop all args
                for _ in range(arg1):
                    if stack:
                        stack.pop()
                stack.append(('result', None))
                lines.append(f"{indent}{func_name}({arg1 - 1} args)")
            
            elif op == 0x0F:  # RET
                lines.append(f"{indent}return")
                break
            
            elif op == 0x1B:  # END
                lines.append(f"{indent}end")
                break
            
            elif op == 0x04:  # POP
                if stack:
                    stack.pop()
                lines.append(f"{indent}pop")
            
            elif op == 0x17:  # WAIT
                lines.append(f"{indent}wait")
            
            elif op == 0x1C:  # RESUME
                lines.append(f"{indent}resume")
            
            elif op == 0x18:  # AND
                if len(stack) >= 2:
                    stack.pop()
                    stack.pop()
                    stack.append(('result', None))
                lines.append(f"{indent}and")
            
            elif op == 0x19:  # OR
                if len(stack) >= 2:
                    stack.pop()
                    stack.pop()
                    stack.append(('result', None))
                lines.append(f"{indent}or")
            
            elif op == 0x1A:  # NOT
                lines.append(f"{indent}not")
            
            elif op == 0x0B:  # NEG
                lines.append(f"{indent}neg")
            
            elif op == 0x0C:  # ITOF
                lines.append(f"{indent}itof")
            
            elif op == 0x0D:  # FTOI
                lines.append(f"{indent}ftoi")
            
            elif op == 0x1D:  # SIN
                lines.append(f"{indent}sin")
            
            elif op == 0x1E:  # COS
                lines.append(f"{indent}cos")
            
            else:
                lines.append(f"{indent}{op_name} arg1=0x{arg1:X} arg2=0x{arg2:X}")
            
            pc += 12
        
        lines.append("}")
        return lines
    
    def decompile_all(self) -> str:
        """Decompile all functions."""
        output = []
        output.append(f"// SB2 Script Decompilation")
        output.append(f"// Total size: 0x{self.total_size:X}")
        output.append(f"// String table: 0x{self.string_table_off:X}")
        output.append(f"// Functions: {self.func_count}")
        output.append(f"// Globals: {self.global_count}")
        output.append("")
        
        # Count local vs external
        local_funcs = []
        external_funcs = []
        for func_id, funcdata_off in self.get_functions():
            fd = self.get_funcdata(funcdata_off)
            if fd is None:
                external_funcs.append((func_id, funcdata_off))
            else:
                local_funcs.append((func_id, funcdata_off))
        
        output.append(f"// Local functions: {len(local_funcs)}")
        output.append(f"// External references: {len(external_funcs)}")
        output.append("")
        
        # List external function IDs
        if external_funcs:
            output.append("// External function IDs (defined in other scripts):")
            ext_ids = [f"0x{fid:04X}" for fid, _ in external_funcs]
            output.append(f"//   {', '.join(ext_ids)}")
            output.append("")
        
        for func_id, funcdata_off in self.get_functions():
            output.extend(self.decompile_function(func_id, funcdata_off))
            output.append("")
        
        return "\n".join(output)


def main():
    if len(sys.argv) < 2:
        print("Usage: decompile_script.py <script.bin> [output.txt]")
        print("       decompile_script.py <script.bin> --func <func_id>")
        sys.exit(1)
    
    script_path = Path(sys.argv[1])
    data = script_path.read_bytes()
    
    dec = SB2Decompiler(data)
    
    if len(sys.argv) >= 4 and sys.argv[2] == '--func':
        # Decompile single function
        func_id = int(sys.argv[3], 0)
        for fid, foff in dec.get_functions():
            if fid == func_id:
                lines = dec.decompile_function(fid, foff)
                print("\n".join(lines))
                break
        else:
            print(f"Function 0x{func_id:X} not found")
            print("Available functions:")
            for fid, _ in dec.get_functions():
                print(f"  0x{fid:04X} ({fid})")
    else:
        # Decompile all
        output = dec.decompile_all()
        
        if len(sys.argv) >= 3:
            out_path = Path(sys.argv[2])
            out_path.write_text(output)
            print(f"Wrote {out_path}")
        else:
            print(output)


if __name__ == "__main__":
    main()
