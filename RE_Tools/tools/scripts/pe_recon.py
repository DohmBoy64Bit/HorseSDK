"""PE header / import / section recon for Horsey.exe (Phase 1)."""
import math
import sys

import pefile


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    freq: dict[int, int] = {}
    for b in data:
        freq[b] = freq.get(b, 0) + 1
    entropy = 0.0
    for count in freq.values():
        p = count / len(data)
        entropy -= p * math.log2(p)
    return entropy


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python pe_recon.py <path_to_exe>")
        sys.exit(1)
    exe_path = sys.argv[1]
    pe = pefile.PE(exe_path)

    print("=== PE Header Info ===")
    print(f"Machine: {pe.FILE_HEADER.Machine} (0x{pe.FILE_HEADER.Machine:04x})")
    print(
        f"Linker Version: {pe.OPTIONAL_HEADER.MajorLinkerVersion}."
        f"{pe.OPTIONAL_HEADER.MinorLinkerVersion}"
    )
    print(f"Compile Timestamp: {pe.FILE_HEADER.TimeDateStamp} (UTC)")
    print(f"Entry Point RVA: 0x{pe.OPTIONAL_HEADER.AddressOfEntryPoint:08x}")
    print(f"Image Base: 0x{pe.OPTIONAL_HEADER.ImageBase:016x}")

    print("\n=== Section Analysis ===")
    for section in pe.sections:
        sec_data = section.get_data()
        entropy = shannon_entropy(sec_data)
        name = section.Name.decode().rstrip("\x00")
        packed = " (High - possible packing)" if entropy > 7.0 else ""
        print(f"Section: {name}")
        print(f"  Virtual Size: 0x{section.Misc_VirtualSize:08x}")
        print(f"  Raw Size: 0x{section.SizeOfRawData:08x}")
        print(f"  Permissions: 0x{section.Characteristics:08x}")
        print(f"  Entropy: {entropy:.2f}{packed}")

    print("\n=== Imports (Top 20 per DLL) ===")
    if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            print(f"\nDLL: {entry.dll.decode()}")
            for i, imp in enumerate(entry.imports):
                if i >= 20:
                    print("  ... (truncated)")
                    break
                if imp.name:
                    print(f"  {imp.name.decode()}")

    print("\n=== Exports (first 30) ===")
    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        symbols = pe.DIRECTORY_ENTRY_EXPORT.symbols
        for exp in symbols[:30]:
            name = exp.name.decode() if exp.name else "N/A"
            print(f"  Ordinal: {exp.ordinal}, Name: {name}")
        if len(symbols) > 30:
            print(f"  ... ({len(symbols)} total exports)")
    else:
        print("No exports found.")

    print("\n=== Rich Header ===")
    if hasattr(pe, "RICH_HEADER"):
        print("Rich header present (MSVC indicator)")
    else:
        print("No Rich header found.")


if __name__ == "__main__":
    main()
