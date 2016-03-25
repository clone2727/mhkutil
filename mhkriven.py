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

# All known opcode names
opcodeNames = {
	1: 'drawBitmap',
	2: 'changeCard',
	3: 'playScriptSLST',
	4: 'playSound',
	7: 'setVariable',
	8: 'switch',
	9: 'enableHotspot',
	10: 'disableHotspot',
	12: 'stopSound',
	13: 'changeCursor',
	14: 'delay',
	17: 'runExternalCommand',
	18: 'transition',
	19: 'refreshCard',
	20: 'disableScreenUpdate',
	21: 'enableScreenUpdate',
	24: 'incrementVariable',
	27: 'changeStack',
	28: 'disableMovie',
	29: 'disableAllMovies',
	31: 'enableMovie',
	32: 'playMovieBlocking',
	33: 'playMovie',
	34: 'stopMovie',
	36: 'unk36',
	37: 'fadeAmbientSounds',
	38: 'storeMovieOpcode',
	39: 'activatePLST',
	40: 'activateSLST',
	41: 'activateMLSTAndPlay',
	43: 'activateBLST',
	44: 'activateFLST',
	45: 'zipMode',
	46: 'activateMLST'
}

# Script type names
scriptTypeNames = {
	0: 'Mouse Down',
	2: 'Mouse Up',
	4: 'Mouse Inside',
	6: 'Card Load',
	7: 'Card Leave',
	9: 'Card Open',
	10: 'Card Update'
}

def decodeRivenCommands(stream, externalCommandNames, variableNames, stackNames, tabs=0):
	text = ''
	commandCount = stream.readUint16BE()

	for i in range(commandCount):
		command = stream.readUint16BE()
		varCount = stream.readUint16BE()
		text += '\t' * tabs

		if command == 7:
			# Assign Variable
			varIndex = stream.readUint16BE()
			immediateValue = stream.readUint16BE()
			text += '{0} = {1};\n'.format(variableNames[varIndex], immediateValue)
		elif command == 8:
			# Switch Statement
			varIndex = stream.readUint16BE()
			caseCount = stream.readUint16BE()

			text += 'switch ({0}) {{\n'.format(variableNames[varIndex])

			for i in range(caseCount):
				text += '\t' * tabs
				caseImmediate = stream.readUint16BE()

				# Write the case
				if caseImmediate == 0xFFFF:
					text += 'default:\n'
				else:
					text += 'case {0}:\n'.format(caseImmediate)

				# Decode the case's script
				text += decodeRivenCommands(stream, externalCommandNames, variableNames, stackNames, tabs + 1)

				# Add a break
				text += '\t' * (tabs + 1) + 'break;\n'

			text += '\t' * tabs + '}\n'
		elif command == 17:
			# External Command
			nameIndex = stream.readUint16BE()
			exVarCount = stream.readUint16BE()
			variables = [str(stream.readUint16BE()) for i in range(exVarCount)]
			text += externalCommandNames[nameIndex] + '(' + ', '.join(variables) + ');\n'
		elif command == 24:
			# Add to Variable
			varIndex = stream.readUint16BE()
			immediateValue = stream.readUint16BE()
			text += '{0} += {1};\n'.format(variableNames[varIndex], immediateValue)
		elif command == 27:
			# Change Stack
			stackIndex = stream.readUint16BE()
			rmapCode = stream.readUint32BE()
			text += 'changeStack({0}, {1});\n'.format(stackNames[stackIndex], rmapCode)
		else:
			# Default
			variables = [str(stream.readUint16BE()) for i in range(varCount)]
			text += opcodeNames[command] + '(' + ', '.join(variables) + ');\n'

	return text

def decodeRivenScript(stream, externalCommandNames, variableNames, stackNames, tabs=0):
	text = ''
	scriptCount = stream.readUint16BE()

	for i in range(scriptCount):
		if text:
			text += '\n'

		text += '\t' * tabs + '{0} Script:\n'.format(scriptTypeNames[stream.readUint16BE()])
		text += decodeRivenCommands(stream, externalCommandNames, variableNames, stackNames, tabs + 1)

	return text

def convertRivenCard(archive, resType, resID, options):
	# Get the resource from the file
	resource = archive.getResource(resType, resID)

	stream = ByteStream(resource)

	# Get the external command and variable name lists
	cardNames = parseRivenNameList(ByteStream(archive.getResource('NAME', 1)))
	externalCommandNames = parseRivenNameList(ByteStream(archive.getResource('NAME', 3)))
	variableNames = parseRivenNameList(ByteStream(archive.getResource('NAME', 4)))
	stackNames = parseRivenNameList(ByteStream(archive.getResource('NAME', 5)))

	# Parse the resource
	nameID = stream.readUint16BE()
	isZipModeDest = stream.readUint16BE()

	# See if we actually have a name
	if nameID == 0xFFFF:
		nameText = '<No Card Name>'
	else:
		nameText = cardNames[nameID]

	# Create a header with some basic info
	text = 'Card Name: {0}\nIs Zip Mode Destination? {1}\n\n'.format(nameText, 'Yes' if isZipModeDest else 'No')

	# Add in the decoded script
	text += decodeRivenScript(stream, externalCommandNames, variableNames, stackNames)

	# Write to a file
	output = open('{0}_{1}.txt'.format(resType, resID), 'wb')
	with output:
		output.write(text)
