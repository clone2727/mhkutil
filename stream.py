# mhkutil - A utility for dealing with Mohawk archives
#
# mhkutil is the legal property of its developers, whose names
# can be found in the AUTHORS file distributed with this source
# distribution.
#
# mhkutil is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# mhkutil is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with mhkutil. If not, see <http://www.gnu.org/licenses/>.

import os
import struct

# TODO: Find a better place for this
def makeTag(text):
	if len(text) != 4:
		raise Exception('Invalid text size {0}'.format(len(text)))

	return struct.unpack('>L', text)[0]

# TODO: Find a better place for this
def tagToString(tag):
	return struct.pack('>L', tag)

class Stream:
	def readByte(self):
		return struct.unpack('B', self.read(1))[0]

	def readSByte(self):
		return struct.unpack('b', self.read(1))[0]

	def readUint16LE(self):
		return struct.unpack('<H', self.read(2))[0]

	def readSint16LE(self):
		return struct.unpack('<h', self.read(2))[0]

	def readUint16BE(self):
		return struct.unpack('>H', self.read(2))[0]

	def readSint16BE(self):
		return struct.unpack('>h', self.read(2))[0]

	def readUint32LE(self):
		return struct.unpack('<L', self.read(4))[0]

	def readSint32LE(self):
		return struct.unpack('<l', self.read(4))[0]

	def readUint32BE(self):
		return struct.unpack('>L', self.read(4))[0]

	def readSint32BE(self):
		return struct.unpack('>l', self.read(4))[0]

	def readCString(self):
		text = ''

		while True:
			char = self.readByte()
			if char == 0:
				break

			text += chr(char)

		return text

class WriteStream:
	def writeByte(self, x):
		self.write(struct.pack('B', x))

	def writeSByte(self, x):
		self.write(struct.pack('b', x))

	def writeUint16LE(self, x):
		self.write(struct.pack('<H', x))

	def writeSint16LE(self, x):
		self.write(struct.pack('<h', x))

	def writeUint16BE(self, x):
		self.write(struct.pack('>H', x))

	def writeSint16BE(self, x):
		self.write(struct.pack('>h', x))

	def writeUint32LE(self, x):
		self.write(struct.pack('<L', x))

	def writeSint32LE(self, x):
		self.write(struct.pack('<l', x))

	def writeUint32BE(self, x):
		self.write(struct.pack('>L', x))

	def writeSint32BE(self, x):
		self.write(struct.pack('>l', x))

class FileStream(Stream):
	def __init__(self, handle):
		self._handle = handle
		handle.seek(0, os.SEEK_END)
		self._size = handle.tell()
		handle.seek(0)

	def tell(self):
		return self._handle.tell()

	def size(self):
		return self._size

	def seek(self, offset, whence=os.SEEK_SET):
		return self._handle.seek(offset, whence)

	def read(self, size):
		return bytearray(self._handle.read(size))

class FileWriteStream(WriteStream):
	def __init__(self, handle):
		self._handle = handle

	def write(self, x):
		self._handle.write(x)

class ByteStream(Stream):
	def __init__(self, data):
		self._data = data
		self._pos = 0

	def tell(self):
		return self._pos

	def size(self):
		return len(self._data)

	def seek(self, offset, whence=os.SEEK_SET):
		if whence == os.SEEK_CUR:
			self._pos += offset
		elif whence == os.SEEK_END:
			self._pos = len(self._data) + offset
		else:
			self._pos = offset

	def read(self, size):
		if size == 0:
			return bytearray()

		start = self._pos
		end = start + size
		self._pos = end
		return self._data[start:end]
