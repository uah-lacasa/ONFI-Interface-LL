import numpy as np

def print_page(page_data):
	# the data into this function 'page_data' must be a bytearray
	# print(f"{page_data}")
	print_str = ''
	for each_byte in page_data:
		print_str += f'{hex(each_byte)},'
	print(f"{print_str}")

def write_to_file(output_file,page_data, write_binary = False):
	if write_binary:
		fd = open(output_file,'wb')
		fd.write(bytes(page_data))
		fd.close()
	else:
		print_str = ''
		for each_byte in page_data:
			print_str += f'{hex(each_byte)},'
		fd = open(output_file,'w')
		fd.write(print_str)
		fd.close()

def compute_ber(file1,is_file1_binary,file2,is_file2_binary):
	# let us read file 1 first
	data1 = []
	data2 = []
	if is_file1_binary:
		fd1 = open(file1,'rb')
		data1 = fd1.read()
		fd1.close()
	else:
		# add other conditions later
		return -1

	if is_file2_binary:
		fd2 = open(file2,'rb')
		data2 = fd2.read()
		fd2.close()
	else:
		# add other conditions later
		return -1

	ber = 0.0
	for idx,each_byte in enumerate(data1):
		if(each_byte!=data2[idx]):
			ber += 1

	print(f"I: BER comparing {file1} and {file2} is {ber/len(data1)}")

def create_array(array_pattern, array_size, filename=""):
	'''Creates numpy array with values following specified pattern, optionally writing it to a file if a filename is specified.'''
	if array_pattern == "zeros":
		new_array = np.zeros(array_size, dtype=np.uint8)

	elif array_pattern == "ones":
		new_array = np.ones(array_size, dtype=np.uint8)

	elif array_pattern == "checkered":
		new_array = np.empty(array_size, dtype=np.uint8)
		new_array[::2] = 0
		new_array[1::2] = 1

	elif array_pattern == "random":
		new_array = np.random.randint(256, size=array_size, dtype=np.uint8)

	if filename:
		new_array.tofile(filename)

	return new_array
