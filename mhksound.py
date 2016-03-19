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
import wave

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
		audioData = stream.read(size - 20)

		if encoding == 0:
			# PCM
			output = open('{0}_{1}.wav'.format(resType, resID), 'wb')

			with output:
				waveout = wave.open(output, 'wb')
				waveout.setnchannels(channels)
				waveout.setsampwidth(bitsPerSample / 8)
				waveout.setframerate(sampleRate)
				waveout.writeframes(audioData)
				waveout.close()
		elif encoding == 1:
			# ADPCM
			raise Exception('TODO: ADPCM audio')
		elif encoding == 2:
			# MPEG Layer II
			output = open('{0}_{1}.mp3'.format(resType, resID), 'wb')

			with output:
				output.write(resource)
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

	# Next is the program number, likely patches
	# Skip this, at least for now
	prgTag = stream.read(4)
	if prgTag != 'Prg#':
		raise Exception('Failed to find the Prg# tag')

	prgSize = stream.readUint32BE()
	stream.seek(prgSize, os.SEEK_CUR)

	# Next are the MIDI tracks. Read them verbatim.
	trackData = stream.read(stream.size() - stream.tell())

	output = open('{0}_{1}.mid'.format(resType, resID), 'wb')
	with output:
		outStream = FileWriteStream(output)
		outStream.write('MThd')
		outStream.writeUint32BE(smfHeaderSize)
		outStream.write(smfHeaderData)
		outStream.write(trackData)
