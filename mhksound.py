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
import sys

def decodeRaw(stream, bitsPerSample):
	if bitsPerSample not in (8, 16):
		raise Exception('Invalid bits per sample: {0}'.format(bitsPerSample))

	samples = []

	while stream.tell() < stream.size():
		if bitsPerSample == 8:
			samples.append(stream.readByte())
		else:
			samples.append(stream.readSint16LE())

	return samples

class ADPCMDecodeState:
	def __init__(self):
		self.last = 0
		self.stepIndex = 0

imaIndexTable = [
	-1, -1, -1, -1, 2, 4, 6, 8,
	-1, -1, -1, -1, 2, 4, 6, 8
]

imaStepTable = [
	7, 8, 9, 10, 11, 12, 13, 14, 16, 17,
	19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
	50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
	130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
	337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
	876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
	2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358,
	5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
	15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767
]

def decodeIMASample(data, state):
	# Decode based on the current step
	diff = (2 * (data & 0x07) + 1) * imaStepTable[state.stepIndex] // 8

	# For the high bit, negate the sample
	if (data & 0x08) != 0:
		diff *= -1

	# Apply the diff to the last sample, clipping it to 16-bit signed
	sample = max(-32768, min(state.last + diff, 32767))

	# Update the state
	state.last = sample
	state.stepIndex = max(0, min(state.stepIndex + imaIndexTable[data], len(imaStepTable) - 1))

	return sample

def decodeADPCM(stream, channels):
	if channels not in (1, 2):
		raise Exception('Invalid channel count: {0}'.format(channels))

	samples = []
	state = [ADPCMDecodeState(), ADPCMDecodeState()]

	while stream.tell() < stream.size():
		data = stream.readByte()
		samples.append(decodeIMASample((data >> 4) & 0x0F, state[0]))
		samples.append(decodeIMASample(data & 0x0F, state[0 if channels == 1 else 1]))

	return samples

def writeWave(output, samples, channels, bitsPerSample, sampleRate):
	if bitsPerSample not in (8, 16):
		raise Exception('Unhandled wave bits per sample: {0}'.format(bitsPerSample))

	# Calculate the data size
	dataSize = len(samples) * bitsPerSample / 8

	# Write the RIFF header
	output.write('RIFF')
	output.writeUint32LE(4 + (8 + 16) + (8 + dataSize)) # RIFF size
	output.write('WAVE')

	# Write the fmt header
	output.write('fmt ')
	output.writeUint32LE(16) # fmt size
	output.writeUint16LE(1) # 1 = PCM
	output.writeUint16LE(channels)
	output.writeUint32LE(sampleRate)
	output.writeUint32LE(sampleRate * channels * bitsPerSample / 8) # Byte rate
	output.writeUint16LE(channels * bitsPerSample / 8) # Block align
	output.writeUint16LE(bitsPerSample)

	# Write the data chunk
	output.write('data')
	output.writeUint32LE(len(samples) * bitsPerSample / 8) # data size

	# Encode all the samples
	for sample in samples:
		if bitsPerSample == 8:
			output.writeByte(sample)
		else:
			output.writeSint16LE(sample)

def convertMohawkWave(archive, resType, resID, options):
	# Get the resource from the file
	resource = archive.getResource(resType, resID)

	stream = ByteStream(resource)

	mhkTag = stream.readUint32BE()
	if mhkTag != makeTag('MHWK'):
		raise Exception('Not a valid Mohawk sound file')

	stream.readUint32BE() # Skip size

	mhkType = stream.readUint32BE()
	if mhkType != makeTag('WAVE'):
		raise Exception('Not a Mohawk sound file')

	while stream.tell() < stream.size():
		tag = stream.readUint32BE()
		size = stream.readUint32BE()

		if tag != makeTag('Data'):
			# Ignore. Don't care about the others.
			stream.seek(size, os.SEEK_CUR)
			continue

		sampleRate = stream.readUint16BE()
		stream.readUint32BE() # sample count
		bitsPerSample = stream.readByte()
		channels = stream.readByte()
		encoding = stream.readUint16BE()
		stream.readUint16BE() # loop count
		stream.readUint32BE() # loop start
		stream.readUint32BE() # loop end
		audioData = ByteStream(stream.read(size - 20))

		if encoding == 0:
			# PCM
			samples = decodeRaw(audioData, bitsPerSample)

			output = open('{0}_{1}.wav'.format(resType, resID), 'wb')
			with output:
				outStream = FileWriteStream(output)
				writeWave(outStream, samples, channels, bitsPerSample, sampleRate)
		elif encoding == 1:
			# ADPCM
			samples = decodeADPCM(audioData, channels)

			output = open('{0}_{1}.wav'.format(resType, resID), 'wb')
			with output:
				outStream = FileWriteStream(output)
				writeWave(outStream, samples, channels, 16, sampleRate)
		elif encoding == 2:
			# MPEG Layer II
			output = open('{0}_{1}.mp3'.format(resType, resID), 'wb')

			with output:
				output.write(audioData.read(audioData.size()))
		else:
			# Bad
			raise Exception('Unknown tWAV encoding {0}'.format(encoding))

def convertMystSound(archive, resType, resID, options):
	# Get the resource from the file
	resource = archive.getResource(resType, resID)

	stream = ByteStream(resource)

	tag = stream.read(4)
	if tag == 'RIFF':
		# Raw wave
		output = open('{0}_{1}.wav'.format(resType, resID), 'wb')
		with output:
			output.write(resource)
	else:
		# Has to be a Mohawk wave
		convertMohawkWave(archive, resType, resID, options)

def convertMohawkMIDI(archive, resType, resID, options):
	# Get the resource from the file
	resource = archive.getResource(resType, resID)

	stream = ByteStream(resource)

	mhkTag = stream.read(4)
	if mhkTag != 'MHWK':
		raise Exception('Not a valid Mohawk MIDI resource')

	stream.readUint32BE() # Skip size

	mhkType = stream.read(4)
	if mhkType != 'MIDI':
		raise Exception('Not a Mohawk MIDI resource')

	# Next is the SMF header
	smfHeaderTag = stream.read(4)
	if smfHeaderTag != 'MThd':
		raise Exception('Failed to find the MThd tag')

	smfHeaderSize = stream.readUint32BE()
	smfHeaderData = stream.read(smfHeaderSize)

	# Next, we need to parse through the file. MTrk are desired,
	# Prg# need to be skipped
	trackData = bytearray()
	while stream.tell() < stream.size():
		tag = stream.read(4)
		size = stream.readUint32BE()

		if tag == 'Prg#':
			# Skip the Prg# tag, at least for now
			stream.seek(size, os.SEEK_CUR)
		elif tag == 'MTrk':
			# Append the track data
			stream.seek(-8, os.SEEK_CUR)
			trackData += stream.read(size + 8)
		else:
			# Unknown type!
			raise Exception('Unknown Mohawk MIDI tag {0}'.format(tag))

		# If the chunk is not aligned, skip a byte
		# Mohawk MIDI needs to be aligned; SMF doesn't
		if (size & 1) != 0:
			stream.seek(1, os.SEEK_CUR)

	output = open('{0}_{1}.mid'.format(resType, resID), 'wb')
	with output:
		outStream = FileWriteStream(output)
		outStream.write('MThd')
		outStream.writeUint32BE(smfHeaderSize)
		outStream.write(smfHeaderData)
		outStream.write(trackData)

def convertMohawkSound(archive, resType, resID, options):
	# Get the resource from the file
	resource = archive.getResource(resType, resID)

	stream = ByteStream(resource)

	mhkTag = stream.read(4)
	if mhkTag != 'MHWK':
		raise Exception('Not a valid Mohawk sound resource')

	stream.readUint32BE() # Skip size

	mhkType = stream.read(4)
	if mhkType == 'MIDI':
		convertMohawkMIDI(archive, resType, resID, options)
	elif mhkType == 'WAVE':
		convertMohawkWave(archive, resType, resID, options)
	else:
		raise Exception('Unknown Mohawk sound type: {0}'.format(mhkType))
