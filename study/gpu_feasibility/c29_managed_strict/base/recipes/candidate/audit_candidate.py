#!/usr/bin/env python3
"""Source/input audit and optional receipt publication; NEVER a process runner."""
import sys
sys.dont_write_bytecode=True
from admission_audit import main
if __name__=='__main__':
    main()
