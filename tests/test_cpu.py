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


def test_clearflags(divide_mmu):
    '''
    Tests that all flags are clear by clear flag instruction
    '''
    # Create basic setup
    cpu = Processor(divide_mmu)

    # Clear flag
    cpu.r.clear_flags()

    # Check that everything is clear
    assert ((cpu.r.p >> 0) & 1) == 0
    assert ((cpu.r.p >> 1) & 1) == 0
    assert ((cpu.r.p >> 2) & 1) == 0
    assert ((cpu.r.p >> 3) & 1) == 0
    assert ((cpu.r.p >> 4) & 1) == 0
    assert ((cpu.r.p >> 5) & 1) == 1
    assert ((cpu.r.p >> 6) & 1) == 0
    assert ((cpu.r.p >> 7) & 1) == 0


def test_reset(divide_mmu):
    '''
    Tests that reset sequence is functioning correctly
    '''
    # Setup computer
    cpu = Processor(divide_mmu)

    # Run a few instructions
    for _ in range(10):
        cpu.step()

    # Reset the registers
    cpu.r.reset(program_counter=0x8000)

    # Check registers are correct value
    assert cpu.r.a == 0
    assert cpu.r.x == 0
    assert cpu.r.y == 0

    assert cpu.r.p == cpu.r.flagbyte['?'] | cpu.r.flagbyte['I']
    assert cpu.r.sp == 0xff

    assert cpu.r.pc == 0x8000


@pytest.mark.parametrize("value, expected", [(0, (True, False)), (-10, (False, True)), (24, (False, False))])
def test_ZN(divide_mmu, value, expected):
    '''
    Tests that the zero and negative flag test works as it should
    '''
    # Setup computer
    cpu = Processor(divide_mmu)

    # Run ZN checks
    cpu.r.ZN(value)

    # Check values are correct
    assert cpu.r.get_flag('Z') == expected[0]
    assert cpu.r.get_flag('N') == expected[1]
