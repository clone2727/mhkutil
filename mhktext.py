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

def convertStringList(archive, resType, resID, options):
	# Get the resource from the file
	resource = archive.getResource(resType, resID)

	stream = ByteStream(resource)

	# First byte is the count
	stringCount = stream.readByte()

	# Read in each of the strings
	stringList = [stream.readCString().replace('\r', '\n') for i in range(stringCount)]

	# Encode it out to JSON
	# The source is Windows English text, so CP-1252
	jsonText = json.JSONEncoder(encoding='cp1252').encode(stringList)

	# Write it to a file
	output = open('{0}_{1}.json'.format(resType, resID), 'wb')
	with output:
		output.write(jsonText)
