# pylint: disable=invalid-name
# pylint: disable=line-too-long
from array import array as Array
import time
import struct
import sys
import traceback
from pyftdi import ftdi
import flashdevice_defs

class IO:
    def __init__(self, do_slow = False, debug = 0, simulation_mode = False):
        self.Debug = debug
        self.PageSize = 0
        self.OOBSize = 0
        self.PageCount = 0
        self.BlockCount = 0
        self.PagePerBlock = 0
        self.BitsPerCell = 0
        self.WriteProtect = True
        self.CheckBadBlock = True
        self.RemoveOOB = False
        self.UseSequentialMode = False
        self.UseAnsi = False
        self.Slow = do_slow
        self.Identified = False
        self.SimulationMode = simulation_mode

        try:
            self.ftdi = ftdi.Ftdi()
        except:
            print("Error openging FTDI device")
            self.ftdi = None

        if self.ftdi is not None:
            try:
                self.ftdi.open(0x0403, 0x6010, interface = 1)
            except:
                traceback.print_exc(file = sys.stdout)

            if self.ftdi.is_connected:
                self.ftdi.set_bitmode(0, self.ftdi.BITMODE_MCU)

                if self.Slow:
                    # Clock FTDI chip at 12MHz instead of 60MHz
                    self.ftdi.write_data(Array('B', [ftdi.Ftdi.ENABLE_CLK_DIV5]))
                else:
                    self.ftdi.write_data(Array('B', [ftdi.Ftdi.DISABLE_CLK_DIV5]))

                self.ftdi.set_latency_timer(self.ftdi.LATENCY_MIN)
                self.ftdi.purge_buffers()
                self.ftdi.write_data(Array('B', [ftdi.Ftdi.SET_BITS_HIGH, 0x0, 0x1]))

        self.__wait_ready()
        
        if not self.__get_id():
            print(f"E: Unable to read the device information")
            sys.exit(-1)

    def __wait_ready(self):
        if self.ftdi is None or not self.ftdi.is_connected:
            print(f"E: Ftdi device not found")
            return

        print(f"I: Ftdi found, waiting")
        while 1:
            print(f".", end =" ")
            self.ftdi.write_data(Array('B', [ftdi.Ftdi.GET_BITS_HIGH]))
            data = self.ftdi.read_data_bytes(1)
            if not data or len(data) <= 0:
                raise Exception('FTDI device Not ready. Try restarting it.')

            if  data[0] & 2 == 0x2:
                return

            if self.Debug > 0:
                print('Not Ready', data)

        return

    def __read(self, cl, al, count):
        cmds = []
        cmd_type = 0
        if cl == 1:
            cmd_type |= flashdevice_defs.ADR_CL
        if al == 1:
            cmd_type |= flashdevice_defs.ADR_AL

        cmds += [ftdi.Ftdi.READ_EXTENDED, cmd_type, 0]

        for _ in range(1, count, 1):
            cmds += [ftdi.Ftdi.READ_SHORT, 0]

        cmds.append(ftdi.Ftdi.SEND_IMMEDIATE)

        if self.ftdi is None or not self.ftdi.is_connected:
            return

        self.ftdi.write_data(Array('B', cmds))
        if self.is_slow_mode():
            data = self.ftdi.read_data_bytes(count*2)
            data = data[0:-1:2]
        else:
            data = self.ftdi.read_data_bytes(count)
        return bytes(data)

    def __write(self, cl, al, data):
        cmds = []
        cmd_type = 0
        if cl == 1:
            cmd_type |= flashdevice_defs.ADR_CL
        if al == 1:
            cmd_type |= flashdevice_defs.ADR_AL
        if not self.WriteProtect:
            cmd_type |= flashdevice_defs.ADR_WP

        cmds += [ftdi.Ftdi.WRITE_EXTENDED, cmd_type, 0, ord(data[0])]

        for i in range(1, len(data), 1):
            #if i == 256:
            #    cmds += [Ftdi.WRITE_SHORT, 0, ord(data[i])]
            cmds += [ftdi.Ftdi.WRITE_SHORT, 0, ord(data[i])]

        if self.ftdi is None or not self.ftdi.is_connected:
            return

        self.ftdi.write_data(Array('B', cmds))

    def __write_bin(self, cl, al, data_bin):
        cmds = []
        cmd_type = 0
        if cl == 1:
            cmd_type |= flashdevice_defs.ADR_CL
        if al == 1:
            cmd_type |= flashdevice_defs.ADR_AL
        if not self.WriteProtect:
            cmd_type |= flashdevice_defs.ADR_WP

        cmds += [ftdi.Ftdi.WRITE_EXTENDED, cmd_type, 0, data_bin[0]]
        
        for i in range(1, len(data_bin), 1):
            cmds += [ftdi.Ftdi.WRITE_SHORT, 0, data_bin[i]]

        if self.ftdi is None or not self.ftdi.is_connected:
            return

        self.ftdi.write_data(Array('B', cmds))

    def __send_cmd(self, cmd):
        self.__write(1, 0, chr(cmd))

    def __send_address(self, addr, count):
        data = ''

        for _ in range(0, count, 1):
            data += chr(addr & 0xff)
            addr = addr>>8

        self.__write(0, 1, data)

    def __get_status(self):
        self.__send_cmd(0x70)
        status = self.__read_data(1)[0]
        return status

    def __read_data(self, count):
        return self.__read(0, 0, count)

    def __write_data(self, data):
        return self.__write(0, 0, data)

    def __write_data_bin(self, data):
        return self.__write_bin(0, 0, data)

    def __get_id(self):
        self.Name = ''
        self.ID = 0
        self.PageSize = 0
        self.ChipSizeMB = 0
        self.EraseSize = 0
        self.Options = 0
        self.AddrCycles = 0

        self.__send_cmd(flashdevice_defs.NAND_CMD_READID)
        self.__send_address(0, 1)
        flash_identifiers = self.__read_data(8)

        if not flash_identifiers:
            print(f"E: Could not read ID from address 0")
            return False

# This section uses a "HACK" to populate flash properties
# .. self.Name, self.ID, self.PageSize, self.ChipSizeMB, self.EraseSize, self.Options, self.AddrCycles
# .. we will populate through ONFI page data read
        # for device_description in flashdevice_defs.DEVICE_DESCRIPTIONS:
        #     if device_description[1] == flash_identifiers[0]:
        #         (self.Name, self.ID, self.PageSize, self.ChipSizeMB, self.EraseSize, self.Options, self.AddrCycles) = device_description
        #         self.Identified = True
        #         break

        # if not self.Identified:
        #     return False

        #Check ONFI
        self.__send_cmd(flashdevice_defs.NAND_CMD_READID)
        self.__send_address(0x20, 1)
        onfitmp = self.__read_data(4)

        onfi = (onfitmp[0]==0x4F and onfitmp[1]==0x4E and onfitmp[2]==0x46 and onfitmp[3]==0x49)

        # if it is ONFI, it is identified
        if onfi:
            self.Identified = True
            self.__send_cmd(flashdevice_defs.NAND_CMD_ONFI)
            self.__send_address(0, 1)
            self.__wait_ready()
            onfi_data = self.__read_data(0x100)
            onfi = onfi_data[0:4] == [0x4F, 0x4E, 0x46, 0x49]
        else:
            # print(f"E: Its not ONFI. Read values are {chr(onfitmp[0]),chr(onfitmp[1]),chr(onfitmp[2]),chr(onfitmp[3])}")
            print(f"E: Its not ONFI. Read values are {(onfitmp[0]),(onfitmp[1]),(onfitmp[2]),(onfitmp[3])}")
            self.Identified = False
            return False

        if flash_identifiers[0] == 0x98:
            self.Manufacturer = 'Toshiba'
        elif flash_identifiers[0] == 0xec:
            self.Manufacturer = 'Samsung'
        elif flash_identifiers[0] == 0x04:
            self.Manufacturer = 'Fujitsu'
        elif flash_identifiers[0] == 0x8f:
            self.Manufacturer = 'National Semiconductors'
        elif flash_identifiers[0] == 0x07:
            self.Manufacturer = 'Renesas'
        elif flash_identifiers[0] == 0x20:
            self.Manufacturer = 'ST Micro'
        elif flash_identifiers[0] == 0xad:
            self.Manufacturer = 'Hynix'
        elif flash_identifiers[0] == 0x2c:
            self.Manufacturer = 'Micron'
        elif flash_identifiers[0] == 0x01:
            self.Manufacturer = 'AMD'
        elif flash_identifiers[0] == 0xc2:
            self.Manufacturer = 'Macronix'
        else:
            self.Manufacturer = 'Unknown'

# Code added by Prawar 17 Feb 2021
        self.IDString = ''
        for id_idx in range(44,64,1):
            self.IDString += chr(onfi_data[id_idx])

        self.ID = onfi_data[64] # 64th byte in ONFI page is Manufacturer ID
        self.PageSize = onfi_data[80] + 256 * onfi_data[81] + 256 * 256 * onfi_data[82] +  256 * 256 * 256 * onfi_data[83]
        self.OOBSize = onfi_data[84] + 256 * onfi_data[85]
        self.RawPageSize = self.PageSize+self.OOBSize
        self.Options = 1
        self.PagePerBlock = onfi_data[92] + 256 * onfi_data[93] + 256 * 256 * onfi_data[94] +  256 * 256 * 256 * onfi_data[95]
        self.BlockSize = self.PagePerBlock*self.RawPageSize
        self.RawBlockSize = self.BlockSize
        self.EraseSize = self.BlockSize# size of Block in bytes
        self.LUNS = onfi_data[100]
        self.BlockPerLUN = onfi_data[96] + 256 * onfi_data[97] + 256 * 256 * onfi_data[98] +  256 * 256 * 256 * onfi_data[99]
        self.BlockCount = self.LUNS * self.BlockPerLUN
        self.PageCount = self.BlockCount * self.PagePerBlock
        self.ChipSizeMB = self.PageCount * self.RawPageSize//(1024*1024)

        self.AddrCycles = 5
        self.BitsPerCell = onfi_data[102]

        return True

    def is_initialized(self):
        return self.Identified

    def set_use_ansi(self, use_ansi):
        self.UseAnsi = use_ansi

    def is_slow_mode(self):
        return self.Slow

    def get_bits_per_cell(self):
        return self.BitsPerCell

    def dump_info(self):
        print('Full ID:\t', self.IDString)
        print('ID:\t\t0x%x' % self.ID)
        print('Total Size:\t\t0x{0:x}({0:d}) MBytes'.format(self.ChipSizeMB))
        print('Page size:\t 0x{0:x}({0:d}) Bytes'.format(self.PageSize))
        print('OOB size:\t0x{0:x} ({0:d}) Bytes'.format(self.OOBSize))
        print('Block size:\t0x{0:x} ({0:d}) Pages'.format(self.PagePerBlock))
        print('Block size:\t0x{0:x} ({0:d}) Bytes'.format(self.BlockSize))
        print('Erase size:\t0x%x Bytes' % self.EraseSize)
        print('Num of LUNS:\t0x{0:x} ({0:d})'.format(self.LUNS))
        print('Blocks per LUN:\t0x{0:x} ({0:d})'.format(self.BlockPerLUN))
        print('Block count:\t', self.BlockCount)
        print('Total Page count:\t0x%x' % self.PageCount)
        print('Options:\t', self.Options)
        print('Address cycle:\t', self.AddrCycles)
        print('Bits per Cell:\t', self.BitsPerCell)
        print('Manufacturer:\t', self.Manufacturer)
        print('')

    def check_bad_blocks(self):
    # """
    # Iterates through the entire flash memory to find bad block.
    # - Goes to each block from 0 to self.BlockCount
    # - Reads the OOB part. If the byte is not 0xff ,the block is bad
    # (every location in first page of bad block is marked with anything besides 0xff)
    # """
        bad_blocks = list()

        first_page_idx = 0
        for block_idx in range(0, self.BlockCount):

            first_page_data = self.read_page(first_page_idx)

            # the first byte in spare area of first page is not 0xff if bad block
            if first_page_data[self.PageSize] != b'\xff':
                print('Bad block found:', block_idx)
                bad_blocks.append(block_idx)

            first_page_idx += self.PagePerBlock

        print('Checked %d blocks and found %d bad blocks' % (self.BlockCount, len(bad_blocks)))
        return bad_blocks

    def read_oob(self, pageno):
        bytes_to_send = bytearray()
        if self.Options & flashdevice_defs.LP_OPTIONS:
            self.__send_cmd(flashdevice_defs.NAND_CMD_READ0)
            self.__send_address((pageno<<16), self.AddrCycles)
            self.__send_cmd(flashdevice_defs.NAND_CMD_READSTART)
            self.__wait_ready()
            bytes_to_send += self.__read_data(self.OOBSize)
        else:
            self.__send_cmd(flashdevice_defs.NAND_CMD_READ_OOB)
            self.__wait_ready()
            self.__send_address(pageno<<8, self.AddrCycles)
            self.__wait_ready()
            bytes_to_send += self.__read_data(self.OOBSize)

        data = ''

        for ch in bytes_to_send:
            data += chr(ch)
        return data

    # This function will read page indexed 'pageno'
    # .. the index of the page is in global scope
    def read_page(self, pageno, remove_oob = False):

        bytes_to_read = []

        if self.Options & flashdevice_defs.LP_OPTIONS:
            length = (self.PageSize) if remove_oob else (self.PageSize + self.OOBSize)
            print(f"I: Reading page {pageno}, Options = 1, {length} bytes")
            self.__send_cmd(flashdevice_defs.NAND_CMD_READ0)
            self.__send_address(pageno<<16, self.AddrCycles)
            self.__send_cmd(flashdevice_defs.NAND_CMD_READSTART)

            if self.PageSize > 0x1000:
                while length > 0:
                    read_len = 0x1000
                    if length < 0x1000:
                        read_len = length
                    bytes_to_read += self.__read_data(read_len)
                    length -= 0x1000
            else:
                bytes_to_read = self.__read_data(length)

            #d: Implement remove_oob
        else:
            print(f"I: Reading page {pageno}, Options = 0")
            self.__send_cmd(flashdevice_defs.NAND_CMD_READ0)
            self.__wait_ready()
            self.__send_address(pageno<<8, self.AddrCycles)
            self.__wait_ready()
            bytes_to_read += self.__read_data(self.PageSize/2)

            self.__send_cmd(flashdevice_defs.NAND_CMD_READ1)
            self.__wait_ready()
            self.__send_address(pageno<<8, self.AddrCycles)
            self.__wait_ready()
            bytes_to_read += self.__read_data(self.PageSize/2)

            if not remove_oob:
                self.__send_cmd(flashdevice_defs.NAND_CMD_READ_OOB)
                self.__wait_ready()
                self.__send_address(pageno<<8, self.AddrCycles)
                self.__wait_ready()
                bytes_to_read += self.__read_data(self.OOBSize)

        return bytes_to_read

    # This function will read the page indexed 'pageno' inside block indexed 'blockno'
    def read_page_from_block(self, pageno, blockno = 0, remove_oob = False):
        page_no_to_read = blockno*self.PagePerBlock+pageno
        return self.read_page(page_no_to_read,remove_oob)

    # 
    def read_seq(self, pageno, remove_oob = False, raw_mode = False):
        page = []
        self.__send_cmd(flashdevice_defs.NAND_CMD_READ0)
        self.__wait_ready()
        self.__send_address(pageno<<8, self.AddrCycles)
        self.__wait_ready()

        bad_block = False

        for i in range(0, self.PagePerBlock, 1):
            page_data = self.__read_data(self.RawPageSize)

            if i in (0, 1):
                if page_data[self.PageSize + 5] != 0xff:
                    bad_block = True

            if remove_oob:
                page += page_data[0:self.PageSize]
            else:
                page += page_data

            self.__wait_ready()

        if self.ftdi is None or not self.ftdi.is_connected:
            return ''

        self.ftdi.write_data(Array('B', [ftdi.Ftdi.SET_BITS_HIGH, 0x1, 0x1]))
        self.ftdi.write_data(Array('B', [ftdi.Ftdi.SET_BITS_HIGH, 0x0, 0x1]))

        data = ''

        if bad_block and not raw_mode:
            print('\nSkipping bad block at %d' % (pageno / self.PagePerBlock))
        else:
            for ch in page:
                data += chr(ch)

        return data

    # This function erases a block based on the index of page 'pageno'
    # .. pageno is the index in global scope
    def erase_block_by_page(self, pageno):
        self.WriteProtect = False
        self.__send_cmd(flashdevice_defs.NAND_CMD_ERASE1)
        # self.__send_address(pageno, self.AddrCycles)
        self.__send_address(pageno, 3)
        self.__send_cmd(flashdevice_defs.NAND_CMD_ERASE2)
        self.__wait_ready()
        err = self.__get_status()
        self.WriteProtect = True

        return err

    # This function can be used to set features
    # .. feature_address is the address of the feature to change
    # .. feature_values is a four-element list of hex values
    def set_features_bin(self, feature_address, feature_values):
        if len(feature_values) != 4:
            print(f"E: Error in Set Features. Please send a list of 4 feature values")
            sys.exit(-1)
        self.__send_cmd(flashdevice_defs.NAND_CMD_SET_FEATURES)
        self.__wait_ready()
        self.__send_address(feature_address,1)
        self.__wait_ready()
        # we need a delay
        time.sleep(0.05)
        self.__write_data_bin(feature_values)

        return

    def set_features(self, feature_address, feature_values):
        if len(feature_values) != 4:
            print(f"E: Error in Set Features. Please send a list of 4 feature values")
            sys.exit(-1)
        self.__send_cmd(flashdevice_defs.NAND_CMD_SET_FEATURES)
        self.__wait_ready()
        self.__send_address(feature_address,1)
        self.__wait_ready()
        # we need a delay
        time.sleep(0.05)
        data = ''

        for each_val in feature_values:
            data += chr(each_val & 0xff)

        self.__write(0, 0, data)
        self.__wait_ready()

        return
# page_data = self.__read_data(self.RawPageSize)
    
    #This function can be used to get feature values
    # .. feature address is the address of the feature address to read
    # .. the return value is a four element array
    def get_features(self, feature_address):
        self.__send_cmd(flashdevice_defs.NAND_CMD_GET_FEATURES)
        self.__wait_ready()
        self.__send_address(feature_address,1)
        self.__wait_ready()
        # we need a delay
        time.sleep(0.05)
        return self.__read_data(4)

    # this function write a page of flash memory
    # .. the pageno is index of page in global scope
    def write_page(self, pageno, data):
        err = 0
        self.WriteProtect = False

        if self.Options & flashdevice_defs.LP_OPTIONS:
            self.__send_cmd(flashdevice_defs.NAND_CMD_SEQIN)
            self.__wait_ready()
            self.__send_address(pageno<<16, self.AddrCycles)
            self.__wait_ready()
            self.__write_data(data)
            self.__send_cmd(flashdevice_defs.NAND_CMD_PAGEPROG)
            self.__wait_ready()
        else:
            while 1:
                self.__send_cmd(flashdevice_defs.NAND_CMD_READ0)
                self.__send_cmd(flashdevice_defs.NAND_CMD_SEQIN)
                self.__wait_ready()
                self.__send_address(pageno<<8, self.AddrCycles)
                self.__wait_ready()
                self.__write_data(data[0:256])
                self.__send_cmd(flashdevice_defs.NAND_CMD_PAGEPROG)
                err = self.__get_status()
                if err & flashdevice_defs.NAND_STATUS_FAIL:
                    print('Failed to write 1st half of ', pageno, err)
                    continue
                break

            while 1:
                self.__send_cmd(flashdevice_defs.NAND_CMD_READ1)
                self.__send_cmd(flashdevice_defs.NAND_CMD_SEQIN)
                self.__wait_ready()
                self.__send_address(pageno<<8, self.AddrCycles)
                self.__wait_ready()
                self.__write_data(data[self.PageSize/2:self.PageSize])
                self.__send_cmd(flashdevice_defs.NAND_CMD_PAGEPROG)
                err = self.__get_status()
                if err & flashdevice_defs.NAND_STATUS_FAIL:
                    print('Failed to write 2nd half of ', pageno, err)
                    continue
                break

            while 1:
                self.__send_cmd(flashdevice_defs.NAND_CMD_READ_OOB)
                self.__send_cmd(flashdevice_defs.NAND_CMD_SEQIN)
                self.__wait_ready()
                self.__send_address(pageno<<8, self.AddrCycles)
                self.__wait_ready()
                self.__write_data(data[self.PageSize:self.RawPageSize])
                self.__send_cmd(flashdevice_defs.NAND_CMD_PAGEPROG)
                err = self.__get_status()
                if err & flashdevice_defs.NAND_STATUS_FAIL:
                    print('Failed to write OOB of ', pageno, err)
                    continue
                break

        self.WriteProtect = True
        return err

    def convert_to_SLC_mode(self, block_idx):
        data = ""
        for each_byte_in_page in range(self.PageSize):
            data += chr(0)
        self.write_all_pages_in_a_block(block_idx,data)

        to_set_features = [1,1,0,0]
        self.set_features(0x91,to_set_features)

        self.erase_blocks(block_idx,block_idx)

    def get_SLC_MLC(self):
        my_values = self.get_features(0x91)
        if(my_values[0] == 1):
            return "SLC"
        elif my_values[0]== 2:
            return "MLC"
        else:
            return "Unknown"

    def revert_to_MLC(self):
        to_set_features = [2,1,0,0]
        self.set_features(0x91,to_set_features)

    def write_all_pages_in_a_block(self,block_idx,data):
        for each_pages in range(self.PagePerBlock):
            self.write_page_in_a_block(each_pages, block_idx, data)

    # this function write a page of flash memory
    # .. the pageno is index of page in block of index block_idx
    def write_page_in_a_block(self, pageno, block_idx, data):
        page_no_to_write = (block_idx*self.PagePerBlock)+pageno
        return self.write_page(page_no_to_write,data)

    def write_pages(self, filename, offset = 0, start_page = -1, end_page = -1, add_oob = False, add_jffs2_eraser_marker = False, raw_mode = False):
        fd = open(filename, 'rb')
        fd.seek(offset)
        data = fd.read()

        if start_page == -1:
            start_page = 0

        if end_page == -1:
            end_page = self.PageCount-1

        end_block = end_page/self.PagePerBlock

        if end_page % self.PagePerBlock > 0:
            end_block += 1

        start = time.time()
        ecc_calculator = ecc.Calculator()

        page = start_page
        block = page / self.PagePerBlock
        current_data_offset = 0
        length = 0

        while page <= end_page and current_data_offset < len(data) and block < self.BlockCount:
            oob_postfix = b'\xff' * 13
            if page%self.PagePerBlock == 0:

                if not raw_mode:
                    bad_block_found = False
                    for pageoff in range(0, 2, 1):
                        oob = self.read_oob(page+pageoff)

                        if oob[5] != b'\xff':
                            bad_block_found = True
                            break

                    if bad_block_found:
                        print('\nSkipping bad block at ', block)
                        page += self.PagePerBlock
                        block += 1
                        continue

                if add_jffs2_eraser_marker:
                    oob_postfix = b"\xFF\xFF\xFF\xFF\xFF\x85\x19\x03\x20\x08\x00\x00\x00"

                self.erase_block_by_page(page)

            if add_oob:
                orig_page_data = data[current_data_offset:current_data_offset + self.PageSize]
                current_data_offset += self.PageSize
                length += len(orig_page_data)
                orig_page_data += (self.PageSize - len(orig_page_data)) * b'\x00'
                (ecc0, ecc1, ecc2) = ecc_calculator.calc(orig_page_data)

                oob = struct.pack('BBB', ecc0, ecc1, ecc2) + oob_postfix
                page_data = orig_page_data+oob
            else:
                page_data = data[current_data_offset:current_data_offset + self.RawPageSize]
                current_data_offset += self.RawPageSize
                length += len(page_data)

            if len(page_data) != self.RawPageSize:
                print('Not enough source data')
                break

            current = time.time()

            if end_page == start_page:
                progress = 100
            else:
                progress = (page-start_page) * 100 / (end_page-start_page)

            lapsed_time = current-start

            if lapsed_time > 0:
                if self.UseAnsi:
                    sys.stdout.write('Writing %d%% Page: %d/%d Block: %d/%d Speed: %d bytes/s\n\033[A' % (progress, page, end_page, block, end_block, length/lapsed_time))
                else:
                    sys.stdout.write('Writing %d%% Page: %d/%d Block: %d/%d Speed: %d bytes/s\n' % (progress, page, end_page, block, end_block, length/lapsed_time))
            self.write_page(page, page_data)

            if page%self.PagePerBlock == 0:
                block = page / self.PagePerBlock
            page += 1

        fd.close()

        print('\nWritten %x bytes / %x byte' % (length, len(data)))

    def erase(self):
        block = 0
        while block < self.BlockCount:
            self.erase_block_by_page(block * self.PagePerBlock)
            block += 1

    def erase_blocks(self, start_block, end_block):
        print('Erasing Block: 0x%x ~ 0x%x' % (start_block, end_block))
        for block in range(start_block, end_block+1, 1):
            print("Erasing block", block)
            self.erase_block_by_page(block * self.PagePerBlock)
