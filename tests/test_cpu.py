#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  test_cpu.py
#
#  Copyright 2022 Sam Hill <sam@pariou>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#
'''
Tests various aspects of the CPU class
'''
import os
import pytest

from pyemul.cpu import Processor, InvalidInstructionError
from pyemul.mmu import MMU


@pytest.fixture
def divide_mmu():
    '''
    Read in compiled programme from file
    '''
    cwd = os.getcwd()
    filename = os.path.join(cwd, 'docs', 'files', 'dividenumber.out')

    with open(filename, 'rb') as fi:
        instructions = fi.read()

    # Use this to setup memory device
    mems = MMU(((0, 0x3fff, 'RAM', False),
                (0x8000, len(instructions)-1, 'ROM',
                True, instructions)))
    return mems


def test_setup_cpu(divide_mmu):
    '''
    Tests that CPU can be setup with valid 6502 assembly loaded into
    memory. Given that it will read the start address from the reset
    vector, it should take 9 CPU cycles
    '''
    divide = Processor(divide_mmu)
    assert divide.cycles == 9


def test_setup_cpu_programme_counter(divide_mmu):
    '''
    Sets up 6502 - but defines the programme counter to be 0x1000
    '''
    divide = Processor(divide_mmu, program_counter=0x1000)
    # Number of cycles should only be 7 now
    assert divide.cycles == 7
    assert divide.r.pc == 0x1000


def test_invalid_instruction():
    '''
    Sets up 6502 and passes invalid instruction
    '''
    # Set up blank memory (set to 0xff)
    mems = MMU(((0, 0x3fff, 'RAM', False),
               (0x8000, 0x7fff, 'ROM', True, 0x7fff*[0xff])))
    cpu = Processor(mems, program_counter=0x8000)
    with pytest.raises(InvalidInstructionError):
        cpu.step()
