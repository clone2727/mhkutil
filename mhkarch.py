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

from stream import *
import struct

class FileTableEntry:
	def __init__(self, offset, size, flags):
		self.offset = offset
		self.size = size
		self.flags = flags

class Resource:
	def __init__(self, offset, size, name):
		self.offset = offset
		self.size = size
		self.name = name

class MohawkArchive:
	def __init__(self, path):
		stream = FileStream(open(path, 'rb'))

		mhkTag = stream.readUint32BE()
		if mhkTag != makeTag('MHWK'):
			raise Exception('Not a valid Mohawk file')

		stream.readUint32BE() # File size

		mhkType = stream.readUint32BE()
		if mhkType != makeTag('RSRC'):
			raise Exception('Not a valid Mohawk resource file')

		version = stream.readUint16BE()
		if version != 0x100:
			raise Exception('Invalid Mohawk version: 0x{0:4X}'.format(version))

		stream.readUint16BE() # Compaction
		stream.readUint32BE() # RSRC size
		absOffset = stream.readUint32BE()
		fileTableOffset = stream.readUint16BE()
		stream.readUint16BE() # File table size

		# Seek to the file table
		stream.seek(absOffset + fileTableOffset)
		fileCount = stream.readUint32BE()
		fileTable = []

		# Read in each of the file table entries
		for i in range(fileCount):
			offset = stream.readUint32BE()
			size = stream.readUint16BE()
			size |= stream.readByte() << 16
			flags = stream.readByte()
			stream.readUint16BE() # Unknown
			size |= (flags & 0x07) << 24 # Bottom 3 bits of flags are top 3 bits of file size

			fileTable.append(FileTableEntry(offset, size, flags))

		# Get to the type table
		stream.seek(absOffset)
		stringTableOffset = stream.readUint16BE()
		typeCount = stream.readUint16BE()

		# Keep a set of all types
		typeMap = {}

		# Read each of the types
		for i in range(typeCount):
			resMap = {}

			tag = stream.readUint32BE()
			resTableOffset = stream.readUint16BE()
			nameTableOffset = stream.readUint16BE()

			# Read in the name table for the type
			stream.seek(absOffset + nameTableOffset)
			nameCount = stream.readUint16BE()
			nameTable = {}
	
			for j in range(nameCount):
				nameOffset = stream.readUint16BE()
				index = stream.readUint16BE()
				oldPos = stream.tell()

				# Seek to the name
				stream.seek(absOffset + stringTableOffset + nameOffset)
				name = stream.readCString()

				# Assign it to the table
				nameTable[index] = name

				# Get back to the next entry
				stream.seek(oldPos)

			# Read in the resource table for the type
			stream.seek(absOffset + resTableOffset)
			resCount = stream.readUint16BE()

			for j in range(resCount):
				resID = stream.readUint16BE()
				index = stream.readUint16BE()

				# Pull the name out of the name table
				try:
					name = nameTable[index]
				except KeyError:
					name = None

				# Get the file table entry
				fileTableEntry = fileTable[index - 1]
				offset = fileTableEntry.offset

				# Figure out the size
				# tMOV is stored with the wrong size, so base it on offsets for that case
				if tag == makeTag('tMOV'):
					if index == len(fileTable):
						size = stream.size() - offset
					else:
						size = fileTable[index].offset - offset
				else:
					size = fileTableEntry.size

				resMap[resID] = Resource(offset, size, name)

			typeMap[tagToString(tag)] = resMap

			# Seek to the next TypeTable entry
			stream.seek(absOffset + (i + 1) * 8 + 4)

		# Store the type map
		self._typeMap = typeMap
		self._stream = stream

	def getTypes(self):
		return self._typeMap.keys()

	def hasResource(self, type, id):
		try:
			return id in self._typeMap[type]
		except KeyError:
			return False

	def getResourceList(self, type):
		return self._typeMap[type].keys()

	def getResource(self, type, id):
		resource = self._typeMap[type][id]
		self._stream.seek(resource.offset)
		return self._stream.read(resource.size)

