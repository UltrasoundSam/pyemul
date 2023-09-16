# -*- coding: utf-8 -*-
"""
Created on Tue Sep  6 16:56:29 2022

@author: SamHill
"""
import array
from typing import Union


block_type = tuple[int, int, str, bool, Union[None, bytearray]]


class MMU:
    '''
    Memory management unit that defines all the addresses that the 6502 can
    interact with, including ROM, RAM and peripheral I/O
    '''
    def __init__(self, blocks: tuple[block_type, ...]) -> None:
        '''
        Initialise the various blocks of virtual memory that the 6502 can
        address.
        '''
        # Create array - know that it'll be $FFFF bytes long. Initialise all
        # values to zero for now
        self.memory = array.array('B', 0xffff*[0])

        # Also will want another mask to know whether it is read only
        self._read_only = array.array('B', 0xffff*[0])

        # Keep track of memory blocks
        self.blocks = []

        # Add each memory block
        for b in blocks:
            self.add_block(*b)

    def add_block(self, start_addr: int, length: int, name: str,
                  read_only: bool = False,
                  data: Union[None, bytearray] = None) -> None:
        '''
        Add block of memory to MMU. Need various information to define memory
        block.
        Inputs:
            start_addr      -   Start address of memory block
            length          -   Number of bytes of memory block
            name            -   Human readable name to know wha
            read_only       -   Boolean flag to say whether writes are allowed
            data            -   data to initialise datablock to.
        '''
        # First, check that there is no memory clash - loop through memory
        # blocks that have already be allocated
        end = start_addr + length
        for block in self.blocks:
            # Check that start of memory block is not between existing
            start_chk = (start_addr > block['start']) and (start_addr < (block['start'] + block['length']))
            end_chk = (end > block['start']) and (end < (block['start'] + block['length']))
            if start_chk or end_chk:
                # Overlap of memory - not free to allocate
                raise MemoryRangeError()

        # Free to allocate memory - store as an array
        new_mem = {'start': start_addr, 'length': length,
                   'name': name, 'read-only': read_only}

        # Define whether it is read only or not
        if read_only:
            for addr in range(start_addr, end):
                self._read_only[addr] = 1

        # If there is data to be initialised, do so:
        if data:
            for addr in range(start_addr, end):
                self.memory[addr] = data[addr - start_addr]

        # Add memory block to list of blocks
        self.blocks.append(new_mem)

    def read(self, addr: int) -> int:
        '''
        Reads byte of data from address addr
        '''
        return self.memory[addr]

    def write(self, addr: int, value: int):
        '''
        Writes value of data to address.
        '''
        # Check to see whether we are allowed to write to memory location
        if self._read_only[addr]:
            raise ReadOnlyError()

        self.memory[addr] = value


class MemoryRangeError(ValueError):
    pass


class ReadOnlyError(TypeError):
    pass
