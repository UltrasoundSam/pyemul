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

from pyemul.mmu import MMU

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
    Tests that new block can be added
    '''
    new_block = (0x5000, 0x1000, 'WriteOnly', True)
    example_memory.add_block(*new_block)
    assert example_memory.blocks[-1]['name'] == 'WriteOnly'
    
