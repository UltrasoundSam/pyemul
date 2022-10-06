# -*- coding: utf-8 -*-
"""
Created on Fri Sep 16 18:15:16 2022

@author: SamHill

An initial test programme to trial out 6502 emulator. Inspiration taken,
especially for assembly code, from Ben Eater video on converting from binary
to decimal: https://www.youtube.com/watch?v=v3-a-zqKfgA
"""

from pyemul.cpu import Processor
from pyemul.mmu import MMU
import os

# Read in compiled programme from file
cwd = os.getcwd()
filename = os.path.join(cwd, 'files', 'dividenumber.out')
with open(filename, 'rb') as fi:
    instructions = fi.read()

mems = MMU(((0, 0x3fff, 'RAM', False), 
            (0x8000, len(instructions)-1, 'ROM', True, instructions)))

divide = Processor(mems)

for _ in range(230):
    divide.step()
    