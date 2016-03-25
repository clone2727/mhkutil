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
import json

def parseRivenNameList(stream):
	# Read the header
	nameCount = stream.readUint16BE()
	stringOffsets = [stream.readUint16BE() for i in range(nameCount)]
	# (There are another nameCount set of uint16s here, but their meaning is unknown)
	strings = []

	# Read each of the strings
	# Strip 0xBD characters. No idea what they are. Having either the 1/2
	# character (CP-1252) or the omega symbol (MacRoman) makes no sense.
	for offset in stringOffsets:
		stream.seek(offset + nameCount * 4 + 2)
		strings.append(stream.readCString().strip('\xBD'))

	return strings

def convertRivenNames(archive, resType, resID, options):
	# Get the resource from the file
	resource = archive.getResource(resType, resID)

	stream = ByteStream(resource)

	# Decode the stream
	stringList = parseRivenNameList(stream)

	# Encode it out to JSON
	# The text needs to be ASCII
	jsonText = json.JSONEncoder(encoding='ascii').encode(stringList)

	# Write it to a file
	output = open('{0}_{1}.json'.format(resType, resID), 'wb')
	with output:
		output.write(jsonText)
		
