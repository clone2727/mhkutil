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
import os

def copyAtomToFile(stream, output, resOffset):
	# Read and copy the atom size/tag
	atomSize = stream.readUint32BE()
	atomTag = stream.read(4)
	output.writeUint32BE(atomSize)
	output.write(atomTag)

	if atomTag in ('moov', 'trak', 'mdia', 'minf', 'stbl'):
		# These atoms contain leaves that may contain 'stco'
		copyAtomToFile(stream, output, resOffset)
	elif atomTag == 'stco':
		# This atom needs to be rewritten
		output.write(stream.read(4)) # Version, flags
		chunkCount = stream.readUint32BE()
		output.writeUint32BE(chunkCount)

		for i in range(chunkCount):
			chunkOffset = stream.readUint32BE()
			newChunkOffset = chunkOffset - resOffset
			output.writeUint32BE(newChunkOffset)
	else:
		# Copy verbatim
		output.write(stream.read(atomSize - 8))

def convertQuickTimeMovie(archive, resType, resID, options):
	# Get the resource from the file
	resource = archive.getResource(resType, resID)
	stream = ByteStream(resource)

	# Get the offset, as we need to convert all internal offsets
	resOffset = archive.getResourceOffset(resType, resID)

	# Parse and write to the file
	output = open('{0}_{1}.mov'.format(resType, resID), 'wb')
	with output:
		outStream = FileWriteStream(output)

		while stream.tell() < stream.size():
			copyAtomToFile(stream, outStream, resOffset)
