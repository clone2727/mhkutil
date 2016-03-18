#!/usr/bin/env python
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

import optparse
import sys

from mhkarch import MohawkArchive
from mhkbmp import convertMohawkBitmap, convertMystBitmap
from mhksound import convertMohawkWave, convertMystSound

def dumpResource(archive, resType, resID, fileName=None):
	if not fileName:
		fileName = '{0}_{1}.dat'.format(resType, resID)

	try:
		output = open(fileName, 'wb')
	except Exception as ex:
		sys.stderr.write('Failed to open \'{0}\' for writing: {1}\n'.format(fileName, ex))
		sys.exit(1)

	try:
		resource = archive.getResource(resType, resID)
	except Exception as ex:
		sys.stderr.write('Failed to get resource {0} {1}: {2}\n'.format(resType, resID, ex))
		sys.exit(1)

	try:
		with output:
			output.write(resource)
	except Exception as ex:
		sys.stderr.write('Failed to write the resource: {0}\n'.format(ex))
		sys.exit(1)

# TODO: Other types:
#	- STRL
#	- tBMH
#	- tMID
# 	- tMOV
#   - (etc.)
convertTypes = {
	'MSND': convertMystSound,
	'PICT': convertMystBitmap,
	'tBMP': convertMohawkBitmap,
	'tWAV': convertMohawkWave,
	'WDIB': convertMystBitmap
}

def listResources(archive, resType, resID):
	if resType is None:
		types = archive.getTypes()
	else:
		types = [resType]

	for type in sorted(types):
		idList = sorted(archive.getResourceList(type))

		if resID is not None:
			if resID in idList:
				idList = [resID]
			else:
				sys.stderr.write('No such resource: {0} {1}\n'.format(resType, resID))
				sys.exit(1)

		for id in idList:
			sys.stdout.write('{0} {1}\n'.format(type, id))

def hexDumpResource(archive, resType, resID):
	try:
		resource = archive.getResource(resType, resID)
	except Exception as ex:
		sys.stderr.write('Failed to get resource {0} {1}: {2}\n'.format(resType, resID, ex))
		sys.exit(1)

	for offset in xrange(0, len(resource), 16):
		sys.stdout.write('{0:08X}: '.format(offset))

		for x in range(16):
			if offset + x < len(resource):
				sys.stdout.write('{0:02X} '.format(resource[offset + x]))
			else:
				sys.stdout.write('   ')

			if x % 4 == 3:
				sys.stdout.write(' ')

		sys.stdout.write(' |')

		for x in range(16):
			if offset + x < len(resource):
				val = resource[offset + x]
				if val < 32 or val >= 127:
					sys.stdout.write('.')
				else:
					sys.stdout.write(chr(val))
			else:
				sys.stdout.write(' ')

		sys.stdout.write('|\n')

def convertResource(archive, resType, resID, options):
	try:
		resource = archive.getResource(resType, resID)
	except Exception as ex:
		sys.stderr.write('Failed to get resource {0} {1}: {2}\n'.format(resType, resID, ex))
		sys.exit(1)

	# Try to get the convert function
	try:
		convertFunc = convertTypes[resType]
	except KeyError:
		sys.stderr.write('Cannot convert resource type {0}\n'.format(resType))
		sys.exit(1)

	# Actually convert it
	try:
		convertFunc(archive, resType, resID, options)
	except Exception as ex:
		sys.stderr.write('Error converting resource: {0}\n'.format(ex))
		sys.exit(1)

def main():
	# TODO: Probably some sort of output file name option
	# TODO: Help text
	parser = optparse.OptionParser()
	parser.add_option('-p', '--palette', dest='palette',
				      help='The palette ID to use if no palette is present ' +
					       'in the converted image',
					  metavar='ID', type='int')
	options, args = parser.parse_args()

	if len(args) < 1:
		sys.stderr.write('Missing command\n')
		parser.print_help(sys.stderr)
		sys.exit(1)

	if len(args) < 2:
		sys.stderr.write('Missing file name\n')
		parser.print_help(sys.stderr)
		sys.exit(1)

	# Parse the args
	mode = args[0]
	fileName = args[1]

	# Load the archive
	try:
		archive = MohawkArchive(fileName)
	except Exception as ex:
		sys.stderr.write('Failed to open \'{0}\': {1}\n'.format(fileName, ex))
		sys.exit(1)

	# Parse the mode
	if mode == 'list':
		# If there's an extra param, treat it as the res type
		resType = None if len(args) < 3 else args[2]
		resID = None if len(args) < 4 else int(args[3])

		# Run the list printer
		listResources(archive, resType, resID)
	elif mode == 'dump':
		# Need to have two more params
		if len(args) < 3:
			sys.stderr.write('Missing resource type\n')
			sys.exit(1)

		if len(args) < 4:
			sys.stderr.write('Missing resource ID\n')
			sys.exit(1)

		resType = args[2]
		resID = int(args[3])

		# Dump the file
		dumpResource(archive, resType, resID)
	elif mode == 'hexdump':
		# Need to have two more params
		if len(args) < 3:
			sys.stderr.write('Missing resource type\n')
			sys.exit(1)

		if len(args) < 4:
			sys.stderr.write('Missing resource ID\n')
			sys.exit(1)

		resType = args[2]
		resID = int(args[3])

		# Dump the file
		hexDumpResource(archive, resType, resID)
	elif mode == 'convert':
		# Need to have two more params
		if len(args) < 3:
			sys.stderr.write('Missing resource type\n')
			sys.exit(1)

		if len(args) < 4:
			sys.stderr.write('Missing resource ID\n')
			sys.exit(1)

		resType = args[2]
		resID = int(args[3])

		# Write the file
		convertResource(archive, resType, resID, vars(options))
	else:
		sys.stderr.write('Unknown mode: \'{0}\'\n'.format(mode))
		sys.exit(1)


if __name__ == '__main__':
	main()

