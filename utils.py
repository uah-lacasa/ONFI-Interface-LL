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
		fd.write(page_data)
		fd.close()
	else:
		print_str = ''
		for each_byte in page_data:
			print_str += f'{hex(each_byte)},'
		fd = open(output_file,'w')
		fd.write(print_str)
		fd.close()