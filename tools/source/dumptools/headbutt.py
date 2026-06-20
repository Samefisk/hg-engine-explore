import sys
import os
import struct

dump = True

def GrabSpeciesDict(speciesDict: dict):
    speciesEntry = 0
    with open("include/constants/species.h") as f:
        for line in f:
            if len(line.split()) > 1:
                test = line.split()[1].strip()
                if 'SPECIES' in test and not '_START' in test and not '_SPECIES_H' in test and not '_NUM (' in line and not 'MAX_' in test:
                    if dump:
                        speciesDict[speciesEntry] = test
                    else:
                        speciesDict[test] = speciesEntry
                    speciesEntry += 1


def headbuttdumper(narcPath: str, outputPath: str):
    speciesDict = {}
    GrabSpeciesDict(speciesDict)
    output = open(outputPath, "w")

    output.write(""".include "armips/include/constants.s"
.include "armips/include/macros.s"

.include "asm/include/species.inc"
                 
.nds
.thumb

// headbutt trees
// headbuttheader header, numberOfNormalTrees, numberOfSpecialTrees
// compact treecoords store a live pair count followed by that many x/y pairs.
// dumped armips output is padded back to 6 pairs with -1's.

""")
    for file in range(0, len(os.listdir(narcPath))):
        fixedName = narcPath + "/2_{:03d}".format(file)
        compactName = narcPath + "/{:03d}".format(file)
        headbuttFile = open(fixedName if os.path.exists(fixedName) else compactName, "rb")
        normalTrees = struct.unpack("<H", headbuttFile.read(2))[0]
        specialTrees = struct.unpack("<H", headbuttFile.read(2))[0]
        treeCount = normalTrees + specialTrees
        output.write("headbuttheader {:3d}, {:3d}, {:3d}\n".format(file, normalTrees, specialTrees))
        if (normalTrees != 0 or specialTrees != 0):
            output.write("    // normal slots\n")
            for encounter in range(0, 12):
                output.write("    headbuttencounter {}, {}, {}\n".format(speciesDict[struct.unpack("<H", headbuttFile.read(2))[0]], struct.unpack("<B", headbuttFile.read(1))[0], struct.unpack("<B", headbuttFile.read(1))[0]))
            output.write("    // special slots\n")
            for encounter in range(0, 6):
                output.write("    headbuttencounter {}, {}, {}\n".format(speciesDict[struct.unpack("<H", headbuttFile.read(2))[0]], struct.unpack("<B", headbuttFile.read(1))[0], struct.unpack("<B", headbuttFile.read(1))[0]))
            # tree coordinates
            legacyFixedTreecoords = is_legacy_fixed_treecoords(headbuttFile, treeCount)
            if (normalTrees != 0):
                output.write("    // normal trees\n")
                for encounter in range(0, normalTrees):
                    output.write("    treecoords {}\n".format(read_treecoords(headbuttFile, legacyFixedTreecoords)))
            if (specialTrees != 0):
                output.write("    // special trees\n")
                for encounter in range(0, specialTrees):
                    output.write("    treecoords {}\n".format(read_treecoords(headbuttFile, legacyFixedTreecoords)))
        output.write(".close\n\n")


def is_legacy_fixed_treecoords(headbuttFile, treeCount):
    current = headbuttFile.tell()
    headbuttFile.seek(0, os.SEEK_END)
    remaining = headbuttFile.tell() - current
    headbuttFile.seek(current)
    return remaining == treeCount * 6 * 4


def read_treecoords(headbuttFile, legacyFixedTreecoords):
    if legacyFixedTreecoords:
        return read_fixed_treecoords(headbuttFile)

    return read_compact_treecoords(headbuttFile)


def read_fixed_treecoords(headbuttFile):
    coords = []
    for _ in range(0, 6):
        coords.append(struct.unpack("<h", headbuttFile.read(2))[0])
        coords.append(struct.unpack("<h", headbuttFile.read(2))[0])

    return ", ".join(str(coord) for coord in coords)


def read_compact_treecoords(headbuttFile):
    coordCount = struct.unpack("<B", headbuttFile.read(1))[0]
    headbuttFile.read(1)

    coords = []
    for _ in range(0, coordCount):
        coords.append(struct.unpack("<h", headbuttFile.read(2))[0])
        coords.append(struct.unpack("<h", headbuttFile.read(2))[0])

    while len(coords) < 12:
        coords.append(-1)

    return ", ".join(str(coord) for coord in coords)

if __name__ == '__main__':
    args = sys.argv[1:]
    if (len(args) == 3 and args[0].strip() == '--dump'):
        dump = True
        headbuttdumper(args[1].strip(), args[2].strip())
    else:
        raise Exception("Usage: python3 headbutt.py --dump narcPath armipsFilePath")
