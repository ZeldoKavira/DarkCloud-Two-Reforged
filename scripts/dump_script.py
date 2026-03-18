#!/usr/bin/env python3
"""Dump the current event script from memory for analysis."""

import sys
sys.path.insert(0, 'src')

from core.pine_ipc import PineIPC
from core.memory import Memory

def main():
    ipc = PineIPC()
    if not ipc.connect():
        print("Failed to connect to PCSX2")
        return
    
    mem = Memory(ipc)
    
    # ScriptBuffer is a mgCMemory at gp - 0x1610 = 0x0037CEE0
    # The actual script data is at ScriptBuffer + 0x20 (the allocation pointer)
    script_buffer = 0x2037CEE0
    
    # Read the mgCMemory struct to find the script data pointer
    # +0x20 = data pointer, +0x24 = used size
    data_ptr_raw = mem.read_int(script_buffer + 0x20)
    used_size = mem.read_int(script_buffer + 0x24)
    
    # Convert to PINE address
    data_ptr = 0x20000000 + (data_ptr_raw & 0x1FFFFFFF) if data_ptr_raw else 0
    
    print(f"ScriptBuffer: 0x{script_buffer:08X}")
    print(f"Data pointer (raw): 0x{data_ptr_raw:08X}")
    print(f"Data pointer (PINE): 0x{data_ptr:08X}")
    print(f"Used size: {used_size} (0x{used_size:X})")
    
    if data_ptr and used_size > 0 and used_size < 0x100000:
        # Dump first 256 bytes of script header
        dump_size = min(256, used_size)
        print(f"\nFirst {dump_size} bytes of script:")
        
        data = []
        for i in range(0, dump_size, 4):
            val = mem.read_int(data_ptr + i)
            data.append(val)
        
        # Print as hex dump
        for i in range(0, len(data), 4):
            addr = i * 4
            line = f"{addr:04X}: "
            for j in range(4):
                if i + j < len(data):
                    line += f"{data[i+j]:08X} "
            print(line)
        
        # Save full dump to file
        print(f"\nDumping full script ({used_size} bytes) to script_dump.bin...")
        full_data = bytearray()
        for i in range(0, used_size, 4):
            val = mem.read_int(data_ptr + i)
            full_data.extend(val.to_bytes(4, 'little'))
        
        with open('script_dump.bin', 'wb') as f:
            f.write(full_data[:used_size])
        print("Done!")
    else:
        print("No valid script loaded or invalid size")
    
    ipc.disconnect()

if __name__ == "__main__":
    main()
