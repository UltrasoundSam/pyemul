#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  test_mmu.py
#
#  Copyright 2022 Sam Hill <sam@pariou>
#
'''
Creates a unit test suite for the MMU component of the computer.
'''
import pytest

from pyemul.mmu import MMU, MemoryRangeError, ReadOnlyError


@pytest.fixture
def example_memory():
    '''
    Simple memory configuration that has 16k of RAM.
    '''
    return MMU(((0, 0x3fff, 'RAM', False),))


def test_address_length(example_memory):
    '''
    6502 uses 16-bit addresses, so total addressable MMU should have
    a 0xffff total number of addressable spaces
    '''
    mems = example_memory
    assert len(mems.memory) == 0xffff


def test_addblock(example_memory):
    '''
    Tests that valid new block can be added
    '''
    new_block = (0x5000, 0x1000, 'WriteOnly', True)
    example_memory.add_block(*new_block)
    assert example_memory.blocks[-1]['name'] == 'WriteOnly'


def test_addblock_data(example_memory):
    '''
    Tests that a valid new block can be added, along with its data
    '''
    new_block = (0x5000, 0x5, 'WriteWithData', True,
                 [0x42, 0x55, 0x11, 0xb5, 0xea])
    example_memory.add_block(*new_block)
    assert example_memory.memory[0x5000] == 0x42


def test_add_invalidblock(example_memory):
    '''
    Tests that block that will overwrite an existing block cannot
    be added
    '''
    new_block = (0x3500, 0x1000, 'WriteOnly', True)
    with pytest.raises(MemoryRangeError):
        example_memory.add_block(*new_block)


def test_write_valid(example_memory):
    '''
    Checks that data can be written to memory
    '''
    newvalue = 0xea
    addr = 0x1000
    example_memory.write(addr, newvalue)
    assert example_memory.read(addr) == newvalue


def test_write_invalid(example_memory):
    '''
    Checks that data can be written to memory
    '''
    # Add new read only block
    new_block = (0x5000, 0x1000, 'WriteOnly', True)
    example_memory.add_block(*new_block)

    # Values to write
    newvalue = 0xea
    addr = 0x5001

    with pytest.raises(ReadOnlyError):
        example_memory.write(addr, newvalue)
