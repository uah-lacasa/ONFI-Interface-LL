import sys
import numpy as np
from flashdevice import IO
import utils

input_file = 'input_dump.bin'

my_nand_instance = IO(False)
my_nand_instance.dump_info()

# create a binary file with random data. Can be used later to program a page
my_rand_array =  np.random.randint(230,size = (my_nand_instance.RawPageSize),dtype=np.uint8)
my_rand_array.tofile(input_file)

# use the following function call to find bab blocks
# bad_blocks = my_nand_instance.check_bad_blocks()

# use the following function to erase a block
# .. the two arguments are start block idx and end block idx
my_nand_instance.erase_blocks(0,0)

# use the following function to read a page from a block
# .. the first argument is page idx in block whose index is second argument
data_1 = my_nand_instance.read_page_from_block(1,0)
utils.write_to_file('output_dump1.bin',data_1,True)

# use the following function to write an arbitrary array into a page
fd = open(input_file,'rb')
data_read = fd.read()
# the internal function want str() so we have to do following
data = "".join(map(chr,data_read))
my_nand_instance.write_page_in_a_block(1, 0, str(data))

# use the following function to read a page from a block
# .. the first argument is page idx in block whose index is second argument
data_2 = my_nand_instance.read_page_from_block(1,0)
utils.write_to_file('output_dump2.bin',data_2,True)

# use the following function to erase a block
# .. the two arguments are start block idx and end block idx
my_nand_instance.erase_blocks(0,0)

# use the following function to read a page from a block
# .. the first argument is page idx in block whose index is second argument
data_3 = my_nand_instance.read_page_from_block(1,0)
utils.write_to_file('output_dump3.bin',data_3,True)

# use the following function to compute BER
utils.compute_ber(input_file,True,'output_dump2.bin',True)

print(f"SLC/MLC: {my_nand_instance.get_SLC_MLC()}")