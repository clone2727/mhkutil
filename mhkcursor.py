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

def convertMacCursor(archive, resType, resID, options):
	# Get the resource from the file
	resource = archive.getResource(resType, resID)

	stream = ByteStream(resource)

	# Read the b/w icon data
	iconData = stream.read(32)

	# Read the mask data
	maskData = stream.read(32)

	# Rewrite the mask data to be in Windows format
	for i in range(32):
		data = iconData[i]
		mask = maskData[i]
		iconData[i] = (~data & mask) & 0xFF
		maskData[i] = ~mask & 0xFF

	# Read the hotspot
	hotspotY = stream.readUint16BE()
	hotspotX = stream.readUint16BE()

	output = open('{0}_{1}.cur'.format(resType, resID), 'wb')
	with output:
		outStream = FileWriteStream(output)

		# Write the cursor header
		outStream.writeUint16LE(0) # Reserved
		outStream.writeUint16LE(2) # 2 = cursor
		outStream.writeUint16LE(1) # Number of images

		# Write the cursor image header
		outStream.writeByte(16) # Width
		outStream.writeByte(16) # Height
		outStream.writeByte(2) # Number of colors
		outStream.writeByte(0) # Reserved
		outStream.writeUint16LE(hotspotX)
		outStream.writeUint16LE(hotspotY)
		outStream.writeUint32LE(40 + 4 * 16 * 2 + 8) # Bitmap size
		outStream.writeUint32LE(6 + 16) # Offset

		# Write the bitmap header
		outStream.writeUint32LE(40) # Header size
		outStream.writeUint32LE(16) # Bitmap width
		outStream.writeUint32LE(16 * 2) # Bitmap height (* 2 for the xor map)
		outStream.writeUint16LE(1) # Planes
		outStream.writeUint16LE(1) # Bits per pixel
		outStream.writeUint32LE(0) # Compression
		outStream.writeUint32LE(4 * 16 * 2) # Image size
		outStream.writeUint32LE(0) # Horizontal resolution
		outStream.writeUint32LE(0) # Vertical resolution
		outStream.writeUint32LE(2) # Number of colors in the palette
		outStream.writeUint32LE(0) # Number of important colors in the palette

		# Write a palette
		outStream.writeUint32BE(0x000000FF)
		outStream.writeUint32BE(0xFFFFFFFF)

		# Write the image, flipping it in the y direction
		for y in xrange(30, -1, -2):
			outStream.write(iconData[y:y + 2])
			outStream.writeUint16LE(0) # 4-byte alignment

		# Write the mask, flipping it in the y direction
		for y in xrange(30, -1, -2):
			outStream.write(maskData[y:y + 2])
			outStream.writeUint16LE(0) # 4-byte alignment
