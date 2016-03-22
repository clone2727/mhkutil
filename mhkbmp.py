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
from mhkarch import MohawkArchive
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
	if bitsPerPixel not in (8, 24):
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
	DrawType.Raw: drawRaw,
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
	stream.readUint32BE() # Skip buffer size

	output = bytearray()

	subCommands = []

	while stream.tell() < stream.size():
		code = stream.readByte()

		if code == 0x00:
			# End of data
			break
		elif code in range(0x01, 0x40):
			# Word Verbatim
			output.extend(stream.read(code * 2))
		elif code in range(0x40, 0x80):
			# Word Repeat
			data = output[-2:]

			for i in range(code - 0x40):
				output.extend(data)
		elif code in range(0x80, 0xC0):
			# Double Word Repeat
			data = output[-4:]

			for i in range(code - 0x80):
				output.extend(data)
		else:
			# Specialized Commands
			for i in range(code - 0xC0):
				subCode = stream.readByte()

				if subCode in range(0x01, 0x10):
					output.append(output[-(subCode * 2)])
					output.append(output[-(subCode * 2)])
				elif subCode == 0x10:
					output.append(output[-2])
					output.append(stream.readByte())
				elif subCode in range(0x11, 0x20):
					output.append(output[-2])
					output.append(output[-(subCode & 0x0F)])
				elif subCode in range(0x20, 0x30):
					output.append(output[-2])
					output.append((output[-2] + (subCode & 0x0F)) & 0xFF)
				elif subCode in range(0x30, 0x40):
					output.append(output[-2])
					output.append((output[-2] - (subCode & 0x0F)) & 0xFF)
				elif subCode == 0x40:
					output.append(stream.readByte())
					output.append(output[-2])
				elif subCode in range(0x41, 0x50):
					output.append(output[-(subCode & 0x0F)])
					output.append(output[-2])
				elif subCode == 0x50:
					output.extend(stream.read(2))
				elif subCode in range(0x51, 0x58):
					output.append(output[-(subCode & 0x07)])
					output.append(stream.readByte())
				elif subCode in range(0x59, 0x60):
					output.append(stream.readByte())
					output.append(output[-(subCode & 0x07)])
				elif subCode in range(0x60, 0x70):
					output.append(stream.readByte())
					output.append((output[-2] + (subCode & 0x0F)) & 0xFF)
				elif subCode in range(0x70, 0x80):
					output.append(stream.readByte())
					output.append((output[-2] - (subCode & 0x0F)) & 0xFF)
				elif subCode in range(0x80, 0x90):
					output.append((output[-2] + (subCode & 0x0F)) & 0xFF)
					output.append(output[-2])
				elif subCode in range(0x90, 0xA0):
					output.append((output[-2] + (subCode & 0x0F)) & 0xFF)
					output.append(stream.readByte())
				elif subCode == 0xA0:
					pattern = stream.readByte()
					output.append((output[-2] + (pattern >> 4)) & 0xFF)
					output.append((output[-2] + (pattern & 0x0F)) & 0xFF)
				elif subCode in range(0xA4, 0xA8):
					distance = ((subCode & 0x03) << 8) | stream.readByte()

					for j in range(3):
						output.append(output[-distance])

					output.append(stream.readByte())
				elif subCode in range(0xA8, 0xAC):
					distance = ((subCode & 0x03) << 8) | stream.readByte()

					for j in range(4):
						output.append(output[-distance])
				elif subCode in range(0xAC, 0xB0):
					distance = ((subCode & 0x03) << 8) | stream.readByte()

					for j in range(5):
						output.append(output[-distance])

					output.append(stream.readByte())
				elif subCode == 0xB0:
					pattern = stream.readByte()
					output.append((output[-2] + (pattern >> 4)) & 0xFF)
					output.append((output[-2] - (pattern & 0x0F)) & 0xFF)
				elif subCode in range(0xB4, 0xB8):
					distance = ((subCode & 0x03) << 8) | stream.readByte()

					for j in range(6):
						output.append(output[-distance])
				elif subCode in range(0xB8, 0xBC):
					distance = ((subCode & 0x03) << 8) | stream.readByte()

					for j in range(7):
						output.append(output[-distance])

					output.append(stream.readByte())
				elif subCode in range(0xBC, 0xC0):
					distance = ((subCode & 0x03) << 8) | stream.readByte()

					for j in range(8):
						output.append(output[-distance])
				elif subCode in range(0xC0, 0xD0):
					output.append((output[-2] - (subCode & 0x0F)) & 0xFF)
					output.append(output[-2])
				elif subCode in range(0xD0, 0xE0):
					output.append((output[-2] - (subCode & 0x0F)) & 0xFF)
					output.append(stream.readByte())
				elif subCode == 0xE0:
					pattern = stream.readByte()
					output.append((output[-2] - (pattern >> 4)) & 0xFF)
					output.append((output[-2] + (pattern & 0x0F)) & 0xFF)
				elif subCode in range(0xE4, 0xE8):
					distance = ((subCode & 0x03) << 8) | stream.readByte()

					for j in range(9):
						output.append(output[-distance])

					output.append(stream.readByte())
				elif subCode in range(0xE8, 0xEC):
					distance = ((subCode & 0x03) << 8) | stream.readByte()

					for j in range(10):
						output.append(output[-distance])
				elif subCode in range(0xEC, 0xF0):
					distance = ((subCode & 0x03) << 8) | stream.readByte()

					for j in range(11):
						output.append(output[-distance])

					output.append(stream.readByte())
				elif subCode in (0xF0, 0xFF):
					pattern = stream.readByte()
					output.append((output[-2] - (pattern >> 4)) & 0xFF)
					output.append((output[-2] - (pattern & 0x0F)) & 0xFF)
				elif subCode in range(0xF4, 0xF8):
					distance = ((subCode & 0x03) << 8) | stream.readByte()

					for j in range(12):
						output.append(output[-distance])
				elif subCode in range(0xF8, 0xFC):
					distance = ((subCode & 0x03) << 8) | stream.readByte()

					for j in range(13):
						output.append(output[-distance])

					output.append(stream.readByte())
				elif subCode == 0xFC:
					code1 = stream.readByte()
					code2 = stream.readByte()
					distance = ((code1 & 0x03) << 8) | code2
					length = ((code1 >> 3) + 1) * 2 + 1

					for j in range(length):
						output.append(output[-distance])

					if (code1 & (1 << 2)) == 0:
						output.append(stream.readByte())
					else:
						output.append(output[-distance])
				else:
					raise Exception('Unknown Riven pack subcode 0x{0:02X}'.format(subCode))

	return output

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

def decodeImage(stream, archive, resType, resID, options):
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

		# See if the palette file override is set
		paletteFile = options['paletteFile']
		if paletteFile is None:
			palArchive = archive
		else:
			palArchive = MohawkArchive(paletteFile)

		# Decode the palette
		palette = decodePalette(ByteStream(palArchive.getResource('tPAL', paletteID)))

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
	return width, height, palette, drawFunc(stream, width, height, pitch, bitsPerPixel)

def convertMohawkBitmap(archive, resType, resID, options):
	# Get the resource from the file
	resource = archive.getResource(resType, resID)

	stream = ByteStream(resource)

	# Decode the image
	width, height, palette, surface = decodeImage(stream, archive, resType, resID, options)

	# Write to a file
	f = open('{0}_{1}.png'.format(resType, resID), 'wb')
	with f:
		writer = png.Writer(width, height, bitdepth=8, palette=palette, compression=9)
		writer.write(f, surface)

def convertMohawkBitmapSet(archive, resType, resID, options):
	# Get the resource from the file
	resource = archive.getResource(resType, resID)

	stream = ByteStream(resource)

	imageCount = stream.readUint16BE() & 0x3FFF
	stream.seek(4, os.SEEK_CUR)
	format = stream.readUint16BE()

	packType = (format & 0x0F00) >> 8

	# Figure out the unpacker
	try:
		unpackFunc = unpackFuncs[packType]
	except KeyError:
		raise Exception('Unknown pack type {0}'.format(packType))

	# Decode the offsets
	stream = ByteStream(unpackFunc(stream))
	offsets = [stream.readUint32BE() - 8 for i in range(imageCount)]

	# Decode all the surfaces
	surfaces = []
	for i in range(imageCount):
		stream.seek(offsets[i])

		# Calculate the length of the subimage
		if i == imageCount - 1:
			length = stream.size() - offsets[i]
		else:
			length = offsets[i + 1] - offsets[i]

		# Read in the subimage
		subStream = ByteStream(stream.read(length))

		# Decode that image
		surfaces.append(decodeImage(subStream, archive, resType, resID, options))

	# Write the images to files
	for i in range(imageCount):
		width, height, palette, surface = surfaces[i]

		f = open('{0}_{1}_{2}.png'.format(resType, resID, i), 'wb')
		with f:
			writer = png.Writer(width, height, bitdepth=8, palette=palette, compression=9)
			writer.write(f, surface)

def convertMystBitmap(archive, resType, resID, options):
	# Get the resource from the file
	resource = archive.getResource(resType, resID)

	stream = ByteStream(resource)

	# Attempt to detect if this is a PICT or compressed BMP
	if stream.size() > (512 + 10 + 4):
		stream.seek(512 + 10)
		pictTag = stream.readUint32BE()
		if pictTag == 0x001102FF:
			# PICT image
			raise Exception('TODO: Unhandled Myst PICT image')
		else:
			# BMP image
			stream.seek(0)

	# Decompress the BMP
	uncompressedSize = stream.readUint32LE()
	bmp = decompressLZ(stream, uncompressedSize)

	# Write the BMP raw
	output = open('{0}_{1}.bmp'.format(resType, resID), 'wb')
	with output:
		output.write(bmp)
