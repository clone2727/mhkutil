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
import png

# LZ decompression constants
lzLengthBits = 6
lzMinString = 3
lzPosBits = 16 - lzLengthBits
lzMaxString = (1 << lzLengthBits) + lzMinString - 1
lzBufferSize = 1 << lzPosBits
lzPosMask = lzBufferSize - 1

def decompressLZ(stream, uncompressedSize):
	flags = 0
	bytesOut = 0
	insertPos = 0

	# Create a buffer for output
	outBufSize = max(uncompressedSize, lzBufferSize)
	outputData = bytearray([0 for x in range(outBufSize)])
	dst = 0
	buf = 0

	while stream.tell() < stream.size():
		flags >>= 1

		if (flags & 0x100) == 0:
			flags = stream.readByte() | 0xFF00

		if (flags & 0x01) == 1:
			bytesOut += 1
			if bytesOut > uncompressedSize:
				break

			outputData[dst] = stream.readByte()
			dst += 1

			insertPos += 1
			if insertPos > lzPosMask:
				insertPos = 0
				buf += lzBufferSize
		else:
			offLen = stream.readUint16BE()
			stringLen = (offLen >> lzPosBits) + lzMinString
			stringPos = (offLen + lzMaxString) & lzPosMask

			bytesOut += stringLen
			if bytesOut > uncompressedSize:
				stringLen -= bytesOut - uncompressedSize

			strPtr = buf + stringPos
			if stringPos > insertPos:
				if bytesOut >= lzBufferSize:
					strPtr -= lzBufferSize
				elif stringPos + stringLen > lzPosMask:
					for i in range(stringLen):
						outputData[dst] = outputData[strPtr]
						dst += 1
						strPtr += 1

						stringPos += 1
						if stringPos > lzPosMask:
							stringPos = 0
							strPtr = 0

					insertPos = (insertPos + stringLen) & lzPosMask
					if bytesOut >= uncompressedSize:
						break

					continue

			insertPos += stringLen

			if insertPos > lzPosMask:
				insertPos &= lzPosMask
				buf += lzBufferSize

			for i in range(stringLen):
				outputData[dst] = outputData[strPtr]
				dst += 1
				strPtr += 1

			if bytesOut >= uncompressedSize:
				break

	# Slice out only the uncompressed data
	return outputData[:uncompressedSize]

def getBitsPerPixel(format):
	try:
		return [1, 4, 8, 16, 24][format & 0x07]
	except IndexError:
		raise Exception('Invalid bytes per pixel: {}'.format(format & 0x07))

class PackType:
	Raw = 0
	LZ = 1
	Riven = 4

class DrawType:
	Raw = 0
	RLE8 = 1

def drawRaw(stream, width, height, pitch, bitsPerPixel):
	if bytesPerPixel not in (8, 24):
		raise Exception('drawRaw only works on 8-bit and 24-bit images')

	surface = []

	for y in range(height):
		row = []

		if bitsPerPixel == 8:
			row.extend(stream.read(width))
			stream.seek(pitch - width, os.SEEK_CUR)
		else:
			for x in range(width):
				b = stream.readByte()
				g = stream.readByte()
				r = stream.readByte()
				row.extend([r, g, b])

			stream.seek(pitch - width * 3, os.SEEK_CUR)

		surface.append(row)

	return surface

def drawRLE8(stream, width, height, pitch, bitsPerPixel, isLE=False):
	if bitsPerPixel != 8:
		raise Exception('drawRLE8 only works on 8-bit images')

	surface = []

	for y in range(height):
		if isLE:
			rowByteCount = stream.readUint16LE()
		else:
			rowByteCount = stream.readUint16BE()

		startPos = stream.tell()
		remaining = width
		row = []

		while remaining > 0:
			code = stream.readByte()
			runLen = (code & 0x7F) + 1

			if runLen > remaining:
				runLen = remaining

			if (code & 0x80) == 0:
				row.extend(stream.read(runLen))
			else:
				val = stream.readByte()
				row.extend([val] * runLen)

			remaining -= runLen

		surface.append(row)
		stream.seek(startPos + rowByteCount)

	return surface

# All drawing functions
drawFuncs = {
	DrawType.RLE8: drawRLE8
}

def unpackRaw(stream):
	return stream.read(stream.size() - stream.tell())

def unpackLZ(stream):
	uncompressedSize = stream.readUint32BE()
	stream.readUint32BE() # compressed size
	dictSize = stream.readUint16BE()

	if dictSize != lzBufferSize:
		raise Exception('Unsupported LZ dictionary size: {0}'.format(dictSize))

	return decompressLZ(stream, uncompressedSize)

def unpackRiven(stream):
	raise Exception('TODO: Unhandled Riven compression')

# All unpackers
unpackFuncs = {
	PackType.Raw: unpackRaw,
	PackType.LZ: unpackLZ,
	PackType.Riven: unpackRiven
}

def decodePalette(stream):
	# Read the header
	colorStart = stream.readUint16BE()
	colorCount = stream.readUint16BE()

	palette = []

	# Start with all black
	for i in range(colorStart):
		palette.append((0, 0, 0))

	# Read in the actual entries
	for i in range(colorCount):
		r = stream.readByte()
		g = stream.readByte()
		b = stream.readByte()
		stream.readByte()
		palette.append((r, g, b))

	# Backfill with black too
	for i in range(256 - (colorStart + colorCount)):
		palette.append((0, 0, 0))

	return palette

def convertMohawkBitmap(archive, resType, resID, options):
	# Get the resource from the file
	resource = archive.getResource(resType, resID)

	stream = ByteStream(resource)

	width = stream.readUint16BE() & 0x3FFF
	height = stream.readUint16BE() & 0x3FFF
	pitch = stream.readUint16BE() & 0x3FFE
	format = stream.readUint16BE()

	bitsPerPixel = getBitsPerPixel(format)
	hasPalette = (format & 0x0080) != 0
	drawType = (format & 0x00F0) >> 4
	packType = (format & 0x0F00) >> 8

	# Read in the palette
	if hasPalette or packType == PackType.Riven:
		stream.readUint16BE() # Table size
		stream.readByte() # Bit size
		stream.readByte() # Color count

		palette = []
		for i in range(256):
			b = stream.readByte()
			g = stream.readByte()
			r = stream.readByte()
			palette.append((r, g, b))
	else:
		palette = None

	# We need a palette if we're less than 16-bit color
	if bitsPerPixel < 16 and not palette:
		# See if we have the option set
		paletteID = options['palette']
		if paletteID is None:
			raise Exception('{0} {1} has no palette; please specify one'.format(resType, resID))

		# Decode the palette
		palette = decodePalette(ByteStream(archive.getResource('tPAL', paletteID)))

	# Figure out the unpacker
	try:
		unpackFunc = unpackFuncs[packType]
	except KeyError:
		raise Exception('Unknown pack type {0}'.format(packType))

	# Decode the stream
	stream = ByteStream(unpackFunc(stream))

	# Figure out the drawing function
	try:
		drawFunc = drawFuncs[drawType]
	except KeyError:
		raise Exception('Unknown draw type {0}'.format(drawType))

	# Draw the image to a surface
	surface = drawFunc(stream, width, height, pitch, bitsPerPixel)

	# Write to a file
	f = open('{0}_{1}.png'.format(resType, resID), 'wb')
	with f:
		writer = png.Writer(width, height, bitdepth=bitsPerPixel, palette=palette, compression=9)
		writer.write(f, surface)
