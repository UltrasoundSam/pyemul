# -*- coding: utf-8 -*-
"""
Created on Mon Sep  5 18:09:53 2022

@author: SamHill
"""
import math

class Registers:
    '''
    An object for holding all the information about the 6502 CPU registers
    '''
    def __init__(self, program_counter=0):
        '''
        Initialise the registers by performing a reset.
        '''
        # Define values for status flag register
        self.flagbyte = {
            'N': 128,       # Negative flat
            'V': 64,        # Overflow flag
            '?': 32,        # Has no effect - always 1
            'B': 16,        # Break flag
            'D': 8,         # Decimal mode
            'I': 4,         # IRQ interrupt disable
            'Z': 2,         # Zero flag
            'C': 1,         # Carry flag
        }
        # Reset register
        self.reset(program_counter)

    def __repr__(self):
        '''
        Representation of object, showing content of all registers
        '''
        fmt = (f'A: 0x{self.a:02x} X: 0x{self.x:02x} Y: 0x{self.y:02x} '
               f'S: 0x{self.sp:02x} PC: 0x{self.pc:04x} Flags: {self.p:>08b}')
        return fmt

    def reset(self, program_counter=0):
        '''
        Simulate a register by setting the X and Y register as well as the
        accumulator, a, to zero. Set the stack pointer to the default ff.
        Program counter can be set to desired value, but defaults to 0.

        Note all registers are 8 bit. Program counter is 16 bits
        '''
        # Set accumulator, X and Y registers to zero
        self.a = 0
        self.x = 0
        self.y = 0

        # Return stack point to default value
        self.sp = 0xff

        # Reset program counter
        self.pc = program_counter

        # Set status flag register
        self.p = self.flagbyte['?'] | self.flagbyte['I']

    def get_flag(self, flag):
        '''
        Return a boolean that describes the state of the flag in the status
        register.
        '''
        return bool(self.p & self.flagbyte[flag])

    def set_flag(self, flag, value=True):
        '''
        Set particular flag to a value (either True or False)
        '''
        if value:
            # Set bit on
            self.p = self.p | self.flagbyte[flag]
        else:
            # Flip bits of flagbyte so we can set flag to zero, but keep
            # everything else - 00001000 -> 11110111
            invert = 0xff - self.flagbyte[flag]
            # And status register and inverted mask to set flag to False
            self.p = self.p & invert

    def ZN(self, value):
        '''
        Zero and Negative flag often get set together and have standard
        criteria. Function to conveniently set both together
        '''
        # Zero flag is set if value is zero
        self.set_flag('Z', value == 0)

        # Using twos-complement, number is negative if MSB is set
        self.set_flag('N', value & 0x80)

    def clear_flags(self):
        '''
        Clears all the flags in the process status register
        '''
        # Bit 6 is always on - but set all others to off
        self.p = self.flagbyte['?']


class Processor:
    '''
    Processor of the 6502
    '''
    def __init__(self, memory_mgt_unit, program_counter=None, stack_page=0x1):
        '''
        Initialise the 6502 computer. Will be started with a program in ROM
        via the memory management unit.

        Normally, program counter does not need to be set. If left as None,
        the CPU will get the program start from reset vector $FFFD and $FFFC.
        '''
        # Assign memory to CPU
        self.mmu = memory_mgt_unit

        # Initialise registers and set stack page
        self.stack_page = stack_page

        # Define hard-coded addresses for interrupts
        self.interrupts = {'ABORT': 0xfff8,
                           'COP':   0xfff4,
                           'IRQ':   0xfffe,
                           'BRK':   0xfffe,
                           'NMI':   0xfffa,
                           'RESET': 0xfffc}

        # Count number of cycles
        self.cycles = 0

        # 6502 performs 7 clock cycles on power up to sort out internals
        self.cycles += 7

        # Initialise program counter using info from mmu
        if program_counter is not None:
            # Initialise registers with defined start point for pc
            self.r = Registers(program_counter)
        else:
            # Initialise registers and initialise value for pc from reset
            # vector in mmu
            reset_vec = self.interrupts['RESET']
            self.r = Registers(reset_vec)

            # Read in address from reset vector
            low_addr = self.read_byte()
            high_addr = self.read_byte()
            addr = (high_addr << 8) + low_addr
            self.cycles += 2

            # Set program counter to this address - ready to execute
            self.r.pc = addr

        # Now define dictionary to hold each op-code. Value for each key is a
        # 4-tuple of (name string, function to call, addressing mode, #cycles)
        self._ops = {# ADC - Add with carry
                     0x69: ('ADC Im', self.ADC, self._load_im, 2),
                     0x65: ('ADC Z', self.ADC, self._zero_page_value, 3),
                     0x75: ('ADC Z,x', self.ADC, self._zero_page_x_value, 4),
                     0x6d: ('ADC A', self.ADC, self._load_addr_value, 4),
                     0x7d: ('ADC A,x', self.ADC, self._load_addr_x_value, 4),
                     0x79: ('ADC A,y', self.ADC, self._load_addr_y_value, 4),
                     0x61: ('ADC I,x', self.ADC, self._load_ix_value, 6),
                     0x71: ('ADC I,y', self.ADC, self._load_iy_value, 5),
                     # AND - And with Accumulator
                     0x29: ('AND Im', self.AND, self._load_im, 2),
                     0x25: ('AND Z', self.AND, self._zero_page_value, 3),
                     0x35: ('AND Z,x', self.AND, self._zero_page_x_value, 4),
                     0x2d: ('AND A', self.AND, self._load_addr_value, 4),
                     0x3d: ('AND A,x', self.AND, self._load_addr_x_value, 4),
                     0x39: ('AND A,y', self.AND, self._load_addr_y_value, 4),
                     0x21: ('AND I,x', self.AND, self._load_ix_value, 6),
                     0x31: ('AND I,y', self.AND, self._load_iy_value, 5),
                     # ASL - Arithmatic Shift Left
                     0x0a: ('ASL Acc', self.ASL, 'a', 2),
                     0x06: ('ASL Z', self.ASL, self._zero_page, 5),
                     0x16: ('ASL Z,x', self.ASL, self._zero_page_x, 6),
                     0x0e: ('ASL A', self.ASL, self._load_addr, 6),
                     0x1e: ('ASL A,x', self.ASL, self._load_addr_x, 7),
                     # Bxx - Branching instructions
                     0x10: ('BPL', self.BRA, ('N', False), 2),
                     0x30: ('BMI', self.BRA, ('N', True), 2),
                     0x50: ('BVC', self.BRA, ('V', False), 2),
                     0x70: ('BVS', self.BRA, ('V', True), 2),
                     0x90: ('BCC', self.BRA, ('C', False), 2),
                     0xb0: ('BCS', self.BRA, ('C', True), 2),
                     0xd0: ('BNE', self.BRA, ('Z', False), 2),
                     0xf0: ('BEQ', self.BRA, ('Z', True), 2),
                     # BIT - Bit test
                     0x24: ('BIT Z', self.BIT, self._zero_page_value, 3),
                     0x2c: ('BIT A', self.BIT, self._load_addr_value, 4),
                     # BRK - Break Command
                     0x00: ('BRK', self.BRK, self._implied, 7),
                     # CLx - Clear Flag
                     0x18: ('CLC', self.CLR, 'C', 2),
                     0xd8: ('CLD', self.CLR, 'D', 2),
                     0x58: ('CLI', self.CLR, 'I', 2),
                     0xb8: ('CLV', self.CLR, 'V', 2),
                     # CMP - Compare with accumulator
                     0xc9: ('CMP Im', self.CMP, self._load_im, 2),
                     0xc5: ('CMP Z', self.CMP, self._zero_page_value, 3),
                     0xd5: ('CMP Z,x', self.CMP, self._zero_page_x_value, 4),
                     0xcd: ('CMP A', self.CMP, self._load_addr_value, 4),
                     0xdd: ('CMP A,x', self.CMP, self._load_addr_x_value, 4),
                     0xd9: ('CMP A,y', self.CMP, self._load_addr_y_value, 4),
                     0xc1: ('CMP I,x', self.CMP, self._load_ix_value, 6),
                     0xd1: ('CMP I,y', self.CMP, self._load_iy_value, 5),
                     # CPX - Compare with X-register
                     0xe0: ('CPX Im', self.CPX, self._load_im, 2),
                     0xe4: ('CPX Z', self.CPX, self._zero_page_value, 3),
                     0xec: ('CPX A', self.CPX, self._load_addr_value, 4),
                     # CPY - Compare with Y-register
                     0xc0: ('CPY Im', self.CPY, self._load_im, 2),
                     0xc4: ('CPY Z', self.CPY, self._zero_page_value, 3),
                     0xcc: ('CPY A', self.CPY, self._load_addr_value, 4),
                     # DEC - Decrement memory by 1
                     0xc6: ('DEC Z', self.DEC, self._zero_page, 5),
                     0xd6: ('DEC Z,x', self.DEC, self._zero_page_x, 6),
                     0xce: ('DEC A', self.DEC, self._load_addr, 6),
                     0xde: ('DEC A,x', self.DEC, self._load_addr_x, 7),
                     # DEX - Decrement contents of X register by 1
                     0xca: ('DEX', self.DEX, self._implied, 2),
                     # DEY - Decrement contents of Y register by 1
                     0x88: ('DEY', self.DEY, self._implied, 2),
                     # EOR - Exclusive OR with accumulator
                     0x49: ('EOR Im', self.EOR, self._load_im, 2),
                     0x45: ('EOR Z', self.EOR, self._zero_page_value, 3),
                     0x55: ('EOR Z,x', self.EOR, self._zero_page_x_value, 4),
                     0x4d: ('EOR A', self.EOR, self._load_addr_value, 4),
                     0x5d: ('EOR A,x', self.EOR, self._load_addr_x_value, 4),
                     0x59: ('EOR A,y', self.EOR, self._load_addr_y_value, 4),
                     0x41: ('EOR I,x', self.EOR, self._load_ix_value, 6),
                     0x51: ('EOR I,y', self.EOR, self._load_iy_value, 5),
                     # INC - Increment memory by 1
                     0xe6: ('INC Z', self.INC, self._zero_page, 5),
                     0xf6: ('INC Z,x', self.INC, self._zero_page_x, 6),
                     0xee: ('INC A', self.INC, self._load_addr, 6),
                     0xfe: ('INC A,x', self.INC, self._load_addr_x, 7),
                     # INX - Increment x register by 1
                     0xe8: ('INX', self.INX, self._implied, 2),
                     # INY - Increment y register by 1
                     0xc8: ('INY', self.INY, self._implied, 2),
                     # JMP - Jump to instruction
                     0x4c: ('JMP A', self.JMP, self._load_addr, 3),
                     0x6c: ('JMP Ind', self.JMP, self._load_indirect, 5),
                     # JSR - Jump to subroutine
                     0x20: ('JSR A', self.JSR, self._load_addr, 6),
                     # LDA - Load accumulator
                     0xa9: ('LDA Im', self.LDA, self._load_im, 2),
                     0xa5: ('LDA Z', self.LDA, self._zero_page_value, 3),
                     0xb5: ('LDA Z,x', self.LDA, self._zero_page_x_value, 4),
                     0xad: ('LDA A', self.LDA, self._load_addr_value, 4),
                     0xbd: ('LDA A,x', self.LDA, self._load_addr_x_value, 4),
                     0xb9: ('LDA A,y', self.LDA, self._load_addr_y_value, 4),
                     0xa1: ('LDA I,x', self.LDA, self._load_ix_value, 6),
                     0xb1: ('LDA I,y', self.LDA, self._load_iy_value, 5),
                     # LDX - Load value into x register
                     0xa2: ('LDX Im', self.LDX, self._load_im, 2),
                     0xa6: ('LDX Z', self.LDX, self._zero_page_value, 3),
                     0xb6: ('LDX Z,y', self.LDX, self._zero_page_y_value, 4),
                     0xae: ('LDX A', self.LDX, self._load_addr_value, 4),
                     0xbe: ('LDX A,y', self.LDX, self._load_addr_y_value, 4),
                     # LDY - Load value into y register
                     0xa0: ('LDY Im', self.LDY, self._load_im, 2),
                     0xa4: ('LDY Z', self.LDY, self._zero_page_value, 3),
                     0xb4: ('LDY Z,x', self.LDY, self._zero_page_x_value, 4),
                     0xac: ('LDY A', self.LDY, self._load_addr_value, 4),
                     0xbc: ('LDY A,x', self.LDY, self._load_addr_x_value, 4),
                     # LSR - Logical Shift right
                     0x4a: ('LSR Acc', self.LSR, 'a', 2),
                     0x46: ('LSR Z', self.LSR, self._zero_page, 5),
                     0x56: ('LSR Z,x', self.LSR, self._zero_page_x, 6),
                     0x4e: ('LSR A', self.LSR, self._load_addr, 6),
                     0x5e: ('LSR A,x', self.LSR, self._load_addr_x, 7),
                     # NOP - No operation
                     0xea: ('NOP', self.NOP, self._implied, 2),
                     # ORA - Logical Or with accumulator
                     0x09: ('ORA Im', self.ORA, self._load_im, 2),
                     0x05: ('ORA Z', self.ORA, self._zero_page_value, 3),
                     0x15: ('ORA Z,x', self.ORA, self._zero_page_x_value, 4),
                     0x0d: ('ORA A', self.ORA, self._load_addr_value, 4),
                     0x1d: ('ORA A,x', self.ORA, self._load_addr_x_value, 4),
                     0x19: ('ORA A,y', self.ORA, self._load_addr_y_value, 4),
                     0x01: ('ORA I,x', self.ORA, self._load_ix_value, 6),
                     0x11: ('ORA I,y', self.ORA, self._load_iy_value, 5),
                     # PHx - Push onto the stack - accumulator or status reg
                     0x48: ('PHA', self.PHS, self.r.a, 3),
                     0x08: ('PHP', self.PHS, self.r.p, 3),
                     # PLx - Pull from stack - accumulator or status reg
                     0x68: ('PLA', self.PLS, 'a', 4),
                     0x28: ('PLP', self.PLS, 'p', 4),
                     # ROL - Rotate left
                     0x2a: ('ROL Im', self.ROL, 'a', 2),
                     0x26: ('ROL Z', self.ROL, self._zero_page, 5),
                     0x36: ('ROL Z,x', self.ROL, self._zero_page_x, 6),
                     0x2e: ('ROL A', self.ROL, self._load_addr, 6),
                     0x3e: ('ROL A,x', self.ROL, self._load_addr_x, 7),
                     # ROR - Rotate right
                     0x6a: ('ROR Im', self.ROR, 'a', 2),
                     0x66: ('ROR Z', self.ROR, self._zero_page, 5),
                     0x76: ('ROR Z,x', self.ROR, self._zero_page_x, 6),
                     0x6e: ('ROR A', self.ROR, self._load_addr, 6),
                     0x7e: ('ROR A,x', self.ROR, self._load_addr_x, 7),
                     # RTI - Return from interrupt
                     0x40: ('RTI', self.RTI, self._implied, 6),
                     # RTS - Return from subroutine
                     0x60: ('RTS', self.RTS, self._implied, 6),
                     # SEx - Set Flag
                     0x38: ('SEC', self.SET, 'C', 2),
                     0xf8: ('SED', self.SET, 'D', 2),
                     0x78: ('SEI', self.SET, 'I', 2),
                     # SBC - Subtract with carry
                     0xe9: ('SBC Im', self.SBC, self._load_im, 2),
                     0xe5: ('SBC Z', self.SBC, self._zero_page_value, 3),
                     0xf5: ('SBC Z,x', self.SBC, self._zero_page_x_value, 4),
                     0xed: ('SBC A', self.SBC, self._load_addr_value, 4),
                     0xfd: ('SBC A,x', self.SBC, self._load_addr_x_value, 4),
                     0xf9: ('SBC A,y', self.SBC, self._load_addr_y_value, 4),
                     0xe1: ('SBC I,x', self.SBC, self._load_ix_value, 6),
                     0xf1: ('SBC I,y', self.SBC, self._load_iy_value, 5),
                     # STA - Store accumulator
                     0x85: ('STA Z', self.STA, self._zero_page, 3),
                     0x95: ('STA Z,x', self.STA, self._zero_page_x, 4),
                     0x8d: ('STA A', self.STA, self._load_addr, 4),
                     0x9d: ('STA A,x', self.STA, self._load_addr_x, 5),
                     0x99: ('STA A,y', self.STA, self._load_addr_y, 5),
                     0x81: ('STA I,x', self.STA, self._load_ix, 6),
                     0x91: ('STA I,y', self.STA, self._load_iy, 6),
                     # STX - Store x-register
                     0x86: ('STX Z', self.STX, self._zero_page, 3),
                     0x96: ('STX, Z,y', self.STX, self._zero_page_y, 4),
                     0x8e: ('STX A', self.STX, self._load_addr, 4),
                     # STY - Store y-register
                     0x84: ('STY Z', self.STY, self._zero_page, 3),
                     0x94: ('STY Z,x', self.STY, self._zero_page_x, 4),
                     0x8c: ('STY A', self.STY, self._load_addr, 4),
                     # Tab - Transfer from a to b
                     0xaa: ('TAX', self.TRA, ('a', 'x'), 2),
                     0x8a: ('TXA', self.TRA, ('x', 'a'), 2),
                     0xa8: ('TAY', self.TRA, ('a', 'y'), 2),
                     0x98: ('TYA', self.TRA, ('y', 'a'), 2),
                     0x9a: ('TXS', self.TRA, ('x', 's'), 2),
                     0xba: ('TSX', self.TRA, ('s', 'a'), 2)
                     }

    def read_byte(self):
        '''
        Read byte from address that program counter is currently set to
        '''
        value = self.mmu.read(self.r.pc)

        # Increment program counter and cycles
        self.r.pc += 1
        return value

    def read_word(self):
        '''
        Reads word from  address that program counter is currently set to
        '''
        # Read destination address
        low_byte = self.read_byte()
        high_byte = self.read_byte()
        value = (high_byte << 8) + low_byte
        return value

    def step(self):
        '''
        Steps through to the next instruction - fetches it from memory, decodes
        instruction and executes.
        '''
        # Fetch instruction
        opcode = self.read_byte()

        # Decode instruction
        name, instruction, argument, cycles = self._ops[opcode]
        try:
            # Call function to load argument to operation
            additional_value = argument()
        except TypeError:
            # The argument is a fixed value rather than function
            additional_value = argument

        # Print commands
        print(f'{name}\t{additional_value}')

        # Execute
        instruction(additional_value)

        # Count number of cycles
        self.cycles += cycles

    def stack_pull(self):
        '''
        Pull value from stack
        '''
        # Get stack address
        addr = self.stack_page*0x100 + ((self.r.sp + 1) & 0xff)

        # Read from stack
        value = self.mmu.read(addr)

        # Increment stack pointer
        self.r.sp = (self.r.sp + 1) & 0xff
        return value

    def stack_pull_word(self):
        '''
        Pull a word from the stack
        '''
        return self.stack_pull() + (self.stack_pull() << 8)

    def stack_push(self, value):
        '''
        Push value onto stack
        '''
        # Get stack address
        addr = self.stack_page*0x100 + ((self.r.sp + 1) & 0xff)

        # Write value to stack
        self.mmu.write(addr, value)

        # Decrement stack pointer
        self.r.sp = (self.r.sp - 1) & 0xff

    def stack_push_word(self, value):
        '''
        Push word onto stack (in two steps)
        '''
        self.stack_push(value >> 8)
        self.stack_push(value & 0xff)

    def interrupt_address(self, interrupt):
        '''
        Gets pre-defined interrupt address
        '''
        # Need to read word from location given by interrupt
        interrupt_addr = self.interrupts[interrupt]
        high_byte = self.mmu.read(interrupt_addr+1)
        low_byte = self.mmu.read(interrupt_addr)
        value = (high_byte << 8) + low_byte
        return value

    def from_BCD(self, value):
        '''
        Convert number from binary-coded decimal (BCD)
        '''
        return (((value & 0xf0) // 0x10) * 10) + (value & 0xf)

    def to_BCD(self, value):
        '''
        Converts number to BCD
        '''
        return int(math.floor(value/10))*16 + (value % 10)

    def from_twos_comp(self, value):
        '''
        Gets number from twos complement
        '''
        return (value & 0x7f) - (value & 0x80)

    ######## Addressing Modes ########
    def _load_im(self):
        '''
        Load immediate: Next value in the program is the value to pass to the
        instruction as an additional parameter
        '''
        # Read value
        value = self.read_byte()
        return value

    def _zero_page(self):
        '''
        Loads in address from zero page memory location
        '''
        zero_page_addr = self.read_byte()
        return zero_page_addr

    def _zero_page_value(self):
        '''
        Returns value from address given by zero page memory location
        '''
        addr = self._zero_page()
        value = self.mmu.read(addr)
        return value

    def _zero_page_x(self):
        '''
        Loads in address from zero page memory location shifted by the current
        value in the x register
        '''
        zero_page_addr = self.read_byte()

        # Read in x register - incrementing pc
        offset = self.r.x

        zero_page_addr = (zero_page_addr + offset) & 0xff
        return zero_page_addr

    def _zero_page_x_value(self):
        '''
        Loads in value from zero page memory location shifted by the current
        value in the x register
        '''
        addr = self._zero_page_x()
        value = self.mmu.read(addr)
        return value

    def _zero_page_y(self):
        '''
        Loads in address from zero page memory location shifted by the current
        value in the x register
        '''
        zero_page_addr = self.read_byte()

        # Read in x register - incrementing pc
        offset = self.r.y

        zero_page_addr = (zero_page_addr + offset) & 0xff
        return zero_page_addr

    def _zero_page_y_value(self):
        '''
        Loads in value from zero page memory location shifted by the current
        value in the x register
        '''
        addr = self._zero_page_y()
        value = self.mmu.read(addr)
        return value

    def _load_addr(self):
        '''
        Loads address from full 16 bit address
        '''
        addr = self.read_word()
        return addr

    def _load_addr_value(self):
        '''
        Loads value from full 16 bit address
        '''
        addr = self._load_addr()
        value = self.mmu.read(addr)
        return value

    def _load_addr_x(self):
        '''
        Loads in address from full memory location shifted by the current
        value in the x register
        '''
        addr = self.read_word()

        # Read in x register - incrementing pc
        offset = self.r.x

        final_addr = (addr + offset) & 0xffff

        # Add extra cycle if cross page boundary
        if math.floor(addr/0xff) != math.floor(final_addr/0xff):
            self.cycles += 1

        return final_addr

    def _load_addr_x_value(self):
        '''
        Loads in value from full memory location shifted by the current
        value in the x register
        '''
        addr = self._load_addr_x()
        value = self.mmu.read(addr)
        return value

    def _load_addr_y(self):
        '''
        Loads in address from full memory location shifted by the current
        value in the x register
        '''
        addr = self.read_word()

        # Read in x register - incrementing pc
        offset = self.r.x

        final_addr = (addr + offset) & 0xffff

        # Add extra cycle if cross page boundary
        if math.floor(addr/0xff) != math.floor(final_addr/0xff):
            self.cycles += 1

        return final_addr

    def _load_addr_y_value(self):
        '''
        Loads in value from full memory location shifted by the current
        value in the x register
        '''
        addr = self._load_addr_y()
        value = self.mmu.read(addr)
        return value

    def _load_ix(self):
        '''
        Indirect loading using value in the x register to find address that
        should be read. A byte is read and added to the contents of the x
        register. This defines a zero-page memory address, which can be read
        to find the location of the data required.
        '''
        # Load in value in next byte and add contents of x register
        intermed = (self.read_byte() + self.r.x) & 0xff

        # Now we have address to go to in order to find address to read value
        # from to send as additional parameter
        high_byte = self.mmu.read((intermed+1) & 0xff)
        low_byte = self.mmu.read(intermed)
        addr = ((high_byte << 8) + low_byte) & 0xffff

        return addr

    def _load_ix_value(self):
        '''
        Indirect loading using value in the x register to find address that
        should be read. A byte is read and added to the contents of the x
        register. This defines a zero-page memory address, which can be read
        to find the location of the data required.
        '''
        addr = self._load_ix()
        value = self.mmu.read(addr)
        return value

    def _load_iy(self):
        '''
        Indirect loading using value in the y register. A byte is read to give
        the location in zero page memory to start reading an address. This
        address is added to the contents of the y register to give the final
        address. A value is loaded from this location.
        '''
        # Read in value
        intermed = self.read_byte()

        # Read in the memory location
        high_byte = self.mmu.read(intermed+1) & 0xff
        low_byte = self.mmu.read(intermed)
        addr = (high_byte << 8) + low_byte
        final_addr = addr + self.r.y

        # Check to see if we have crossed page boundary - add extra cycle if so
        if math.floor(addr/0xff) != math.floor(final_addr/0xff):
            self.cycles += 1

        return addr

    def _load_iy_value(self):
        '''
        Indirect loading using value in the y register. A byte is read to give
        the location in zero page memory to start reading an address. This
        address is added to the contents of the y register to give the final
        address. A value is loaded from this location.
        '''
        addr = self._load_iy()
        value = self.mmu.read(addr)
        return value

    def _load_indirect(self):
        '''
        Indirect loading using value at given address. Only used by indirect
        JMP instruction. Also, doesn't carry, so if low byte is in xxFF
        position, the high byte will be xx00 rather than xy00'
        '''
        addr1 = self.read_word()
        # Result doesn't carry
        if (addr1 & 0xff) == 0xff:
            addr2 = addr1 - 0xff
        else:
            addr2 = addr1 + 1

        result = (self.mmu.read(addr2) << 8) + self.mmu.read(addr1)
        return result & 0xffff

    def _implied(self):
        '''
        Implied addressing mode - no need to do anything
        '''
        return None

    # Define operation methods
    def ADC(self, value2):
        '''
        Add with carry. Adds (with carry) value2 to current contents of
        accumulator.
        '''
        # Get current accumulator value
        value1 = self.r.a

        # Check to see if in decimal mode or binary mode
        if self.r.get_flag('D'):
            # Convert numbers from BCD
            value1 = self.from_BCD(value1)
            value2 = self.from_BCD(value2)

            # Perform addition
            result = value1 + value2 + self.r.get_flag('C')
            self.r.a = self.to_BCD(result)

            # Set carry flag
            self.r.set_flag('C', result > 99)
        else:
            # Perform addition
            result = value1 + value2 + self.r.get_flag('C')

            # Put result in 8 bit accumulator register
            self.r.a = result & 0xff

            # Set carry flag if required
            self.r.set_flag('C', result > 0xff)

        # Set zero and negative flags
        self.r.ZN(self.r.a)

        # Set overflow flag
        self.r.set_flag('V', ((~(value1 ^ value2)) & (value1 ^ result) & 0x80))

    def AND(self, value2):
        '''
        And. Ands value2 with current contents of accumulator
        '''
        # Perform AND Operation between acummulator and value2
        calculation = self.r.a & value2

        # Put result back into 8 bit acummulator
        self.r.a = calculation & 0xff

        # Set zero and negative flags
        self.r.ZN(self.r.a)

    def ASL(self, addr):
        '''
        ASL shifts all bits left one position. 0 is shifted into bit 0 and
        the original bit 7 is shifted into the Carry.
        '''
        if addr == 'a':
            # Shift contents of accumulator left
            value = self.r.a << 1
            self.r.a = value & 0xff
        else:
            # Shift acting on value in memory location
            value = self.mmu.read(addr) << 1
            self.mmu.write(addr, value)

        # If shifted value is greater than 0xff, then original bit 7 was 1
        self.r.set_flag('C', value > 0xff)
        self.r.ZN(value & 0xff)

    def BRA(self, value2):
        '''
        Handles all the branching operations. Value 2 is a tuple of
        (flag, bool) that fully defines all branching operations. For example,
        branch carry clear (BCC) would have value2 set to ('C', False)
        '''
        # Get relative address value
        jump = self._load_im()

        flag, state = value2
        # Determine if we need to branch
        if self.r.get_flag(flag) is state:
            # Negative flag not set - calculate address to jump to
            current_pc = self.r.pc
            self.r.pc += self.from_twos_comp(jump)
            if math.floor(current_pc/0xff) == math.floor(self.r.pc/0xff):
                # Same page, only takes 1 clock cycle
                self.cycles += 1
            else:
                # Different page, takes two clock cycles
                self.cycles += 2

    def BIT(self, value2):
        '''
        Performs bit test with value2. Doesn't modify any registers, but
        does changes the flags depending on the result
        '''
        self.r.set_flag('Z', (self.r.a & value2) == 0)
        self.r.set_flag('N', value2 & 0x80)
        self.r.set_flag('V', value2 & 0x40)

    def BRK(self, _):
        '''
        Force break (software interrupt rather than hardware interrupt)
        '''
        # Need to set appropriate flag
        self.r.set_flag('B')

        # Push programme counter and status flag onto the stack
        self.stack_push_word(self.r.pc+1)
        self.stack_push(self.r.p)

        # Set interrupt flat
        self.r.set_flag('I')

        # Set programme counter to value defined in interrupt routine
        self.r.pc = self.interrupt_address('BRK')

    def CLR(self, flag):
        '''
        Clears the flag in the status register
        '''
        self.r.set_flag(flag, False)

    def __compare(self, register, value):
        '''
        Helper function to compare value with contents of given register. Used
        for CMP, CPX, CPY operations.
        '''
        result = (register - value) & 0xff
        self.r.set_flag('Z', result == 0)
        self.r.set_flag('C', value <= register)
        self.r.set_flag('N', result & 0x80)

    def CMP(self, value2):
        '''
        Compare value with contents of accumulator
        '''
        self.__compare(self.r.a, value2)

    def CPX(self, value2):
        '''
        Compare value with contents of X-register
        '''
        self.__compare(self.r.x, value2)

    def CPY(self, value2):
        '''
        Compare value with contents of Y-register
        '''
        self.__compare(self.r.y, value2)

    def DEC(self, addr):
        '''
        Decrement value in address by 1
        '''
        value = self.mmu.read(addr) - 1
        # Write value back to address
        self.mmu.write(value & 0xff)
        self.r.ZN(value & 0xff)

    def DEX(self, _):
        '''
        Decrement contents of x register by 1
        '''
        self.r.x = (self.r.x - 1) & 0xff
        self.r.ZN(self.r.x)

    def DEY(self, _):
        '''
        Decrement contents of y register by 1
        '''
        self.r.y = (self.r.y - 1 ) & 0xff
        self.r.ZN(self.r.y)

    def EOR(self, value2):
        '''
        Performs bitwise exclusive OR with contents of the accumulator
        '''
        self.r.a = self.r.a ^ value2
        self.r.ZN(self.r.a)

    def INC(self, addr):
        '''
        Increment value in address by 1
        '''
        value = self.mmu.read(addr) + 1
        # Write value back to address
        self.mmu.write(value & 0xff)
        self.r.ZN(value & 0xff)

    def INX(self, _):
        '''
        Increment contents of x register by 1
        '''
        self.r.x = (self.r.x + 1) & 0xff
        self.r.ZN(self.r.x)

    def INY(self, _):
        '''
        Increment contents of y register by 1
        '''
        self.r.y = (self.r.y + 1) & 0xff
        self.r.ZN(self.r.y)

    def JMP(self, addr):
        '''
        Jump to address
        '''
        self.r.pc = addr

    def JSR(self, addr):
        '''
        Jump to subroutine
        '''
        # Push return address to stack
        self.stack_push_word(self.r.pc-1)
        self.r.pc = addr

    def LDA(self, value2):
        '''
        Load value2 into the accumulator
        '''
        self.r.a = value2
        self.r.ZN(self.r.a)

    def LDX(self, value2):
        '''
        Load value into x register
        '''
        self.r.x = value2
        self.r.ZN(self.r.x)

    def LDY(self, value2):
        '''
        Load value into y register
        '''
        self.r.y = value2
        self.r.ZN(self.r.y)

    def LSR(self, addr):
        '''
        Shifts value in address to the right by 1 bit. If addr is 'a', this
        means that the operation acts on the accumulator
        '''
        if addr == 'a':
            # If LSB is True, set the carry flag
            self.r.set_flag('C', self.r.a & 0x01)
            value = self.r.a >> 1
            self.r.a = value
        else:
            # Acts on a memory location, so read it in
            value = self.mmu.read(addr)
            # If LSB is True, set carry flag
            self.r.set_flag('C', value & 0x01)
            # Shift value to the right and put back in memory
            value = value >> 1
            self.mmu.write(value)

        # Update zero and negative flags
        self.r.ZN(value)

    def NOP(self, _):
        '''
        No operation - do nothing
        '''
        pass

    def ORA(self, value2):
        '''
        Performs the logical OR operation between value2 and contents of the
        accumulator
        '''
        self.r.a = self.r.a | value2
        self.r.ZN(self.r.a)

    def PHS(self, value2):
        '''
        Pushes value2 (from either accumulator or process register) onto the
        stack
        '''
        self.stack_push(value2)

    def PLS(self, reg):
        '''
        Pulls value from stack and places it in appropriate place (reg)
        '''
        # Get value from stack
        value = self.stack_pull()
        if reg == 'a':
            # Place in the accumulator
            self.r.a = value
            # Update Z and N flag
            self.r.ZN(value)
        elif reg == 'p':
            self.r.p = value | 0b00100000

    def ROL(self, addr):
        '''
        Rotates a value in memory to the left by 1 bit
        '''
        if addr == 'a':
            # Operates on the accumulator
            original = self.r.a
            new = (original << 1) + self.r.get_flag('C')
            self.r.a = new & 0xff
        else:
            # Operates on values in memory location
            original = self.mmu.read(addr)
            new = (original << 1) + self.r.get_flag('C')
            self.mmu.write(addr, new & 0xff)

        # Set flags
        self.r.set_flag('C', original & 0x80)
        self.r.ZN(new & 0xff)

    def ROR(self, addr):
        '''
        Rotates a value in memory to the right by 1 bit
        '''
        if addr == 'a':
            # Operates on the accumulator
            original = self.r.a
            new = (original >> 1) + self.r.get_flag('C')*0x80
            self.r.a = new & 0xff
        else:
            # Operates on memory location
            original = self.mmu.read(addr)
            new = (original >> 1) + self.r.get_flag('C')*0x80
            self.mmu.write(addr, new & 0xff)

        # Set flags
        self.r.set_flag('C', original & 0x01)
        self.r.ZN(new & 0xff)

    def RTI(self, _):
        '''
        Return from interrupt routine
        '''
        # Retrieve process status
        self.r.p = self.stack_pull()
        # Retrieve return addresss
        self.r.pc = self.stack_pull_word()

    def RTS(self, _):
        '''
        Return from subroutine
        '''
        self.r.pc = (self.stack_pull_word() + 1 ) & 0xffff

    def SBC(self, value2):
        '''
        Performs subtract with carry operation between value2 and accumulator.
        '''
        value1 = self.r.a

        # Check if in decimal or binary mode
        if self.r.get_flag('D'):
            # Convert numbers from BCD
            value1 = self.from_BCD(value1)
            value2 = self.from_BCD(value2)

            # Perform subtraction
            result = value1 - value2 - (not self.r.get_flag('C'))
            self.r.a = self.to_BCD(result % 100)
        else:
            result = value1 - value2 - (not self.r.get_flag('C'))
            self.r.a = result & 0xff

        # Set flags
        self.r.set_flag('C', result >= 0)
        self.r.set_flag('V', ((value1 ^ value2) & (value1 ^ result) & 0x80))
        self.r.ZN(self.r.a)

    def SET(self, flag):
        '''
        Sets the appropriate flag
        '''
        self.r.set_flag(flag, True)

    def STA(self, addr):
        '''
        Stores accumulator into given address
        '''
        self.mmu.write(addr, self.r.a)

    def STX(self, addr):
        '''
        Stores x-register into given address
        '''
        self.mmu.write(addr, self.r.x)

    def STY(self, addr):
        '''
        Stores accumulator into given address
        '''
        self.mmu.write(addr, self.r.y)

    def TRA(self, regs):
        '''
        Transfers values between two registers, given in 2-tuple regs. So,
        transferring from X to A would be regs=('x', 'a')
        '''
        source, dest = regs
        source_value = getattr(self.r, source)
        # Set value to destination register
        setattr(self.r, dest, source_value)
        # Need to update Z and N flags (if destination is not stack)
        if dest != 's':
            self.r.ZN(source_value)
