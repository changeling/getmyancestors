#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
   mergemyancestors.py - Merge GEDCOM data from FamilySearch Tree
   Copyright (C) 2014-2016 Giulio Genovese (giulio.genovese@gmail.com)

   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <http://www.gnu.org/licenses/>.

   Written by Giulio Genovese <giulio.genovese@gmail.com>
   and by Benoît Fontaine <benoitfontaine.ba@gmail.com>
"""

from __future__ import print_function

# global import
import os
import sys
import argparse

# local import
from shared_classes import Tree, Gedcom, Indi, Fam

sys.path.append(os.path.dirname(sys.argv[0]))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Merge GEDCOM data from FamilySearch Tree (4 Jul 2016)', add_help=False, usage='mergemyancestors.py -i input1.ged input2.ged ... [options]')
    try:
        parser.add_argument('-i', metavar='<FILE>', nargs='+', type=argparse.FileType('r', encoding='UTF-8'), default=sys.stdin, help='input GEDCOM files [stdin]')
        parser.add_argument('-o', metavar='<FILE>', nargs='?', type=argparse.FileType('w', encoding='UTF-8'), default=sys.stdout, help='output GEDCOM files [stdout]')
    except TypeError:
        sys.stderr.write('Python >= 3.4 is required to run this script\n')
        sys.stderr.write('(see https://docs.python.org/3/whatsnew/3.4.html#argparse)\n')
        exit(2)

    # extract arguments from the command line
    try:
        parser.error = parser.exit
        args = parser.parse_args()
    except SystemExit:
        parser.print_help()
        exit(2)

    tree = Tree()

    indi_counter = 0
    fam_counter = 0

    # read the GEDCOM data
    for file in args.i:
        ged = Gedcom(file, tree)

        # add informations about individuals
        for num in ged.indi:
            fid = ged.indi[num].fid
            if fid not in tree.indi:
                indi_counter += 1
                tree.indi[fid] = Indi(tree=tree, num=indi_counter)
                tree.indi[fid].tree = tree
                tree.indi[fid].fid = ged.indi[num].fid
            tree.indi[fid].fams_fid |= ged.indi[num].fams_fid
            tree.indi[fid].famc_fid |= ged.indi[num].famc_fid
            tree.indi[fid].name = ged.indi[num].name
            tree.indi[fid].birthnames = ged.indi[num].birthnames
            tree.indi[fid].nicknames = ged.indi[num].nicknames
            tree.indi[fid].aka = ged.indi[num].aka
            tree.indi[fid].married = ged.indi[num].married
            tree.indi[fid].gender = ged.indi[num].gender
            tree.indi[fid].facts = ged.indi[num].facts
            tree.indi[fid].notes = ged.indi[num].notes
            tree.indi[fid].sources = ged.indi[num].sources
            tree.indi[fid].memories = ged.indi[num].memories
            tree.indi[fid].baptism = ged.indi[num].baptism
            tree.indi[fid].confirmation = ged.indi[num].confirmation
            tree.indi[fid].endowment = ged.indi[num].endowment
            if not (tree.indi[fid].sealing_child and tree.indi[fid].sealing_child.famc):
                tree.indi[fid].sealing_child = ged.indi[num].sealing_child

        # add informations about families
        for num in ged.fam:
            husb, wife = (ged.fam[num].husb_fid, ged.fam[num].wife_fid)
            if (husb, wife) not in tree.fam:
                fam_counter += 1
                tree.fam[(husb, wife)] = Fam(husb, wife, tree, fam_counter)
                tree.fam[(husb, wife)].tree = tree
            tree.fam[(husb, wife)].chil_fid |= ged.fam[num].chil_fid
            if ged.fam[num].fid:
                tree.fam[(husb, wife)].fid = ged.fam[num].fid
            if ged.fam[num].facts:
                tree.fam[(husb, wife)].facts = ged.fam[num].facts
            if ged.fam[num].notes:
                tree.fam[(husb, wife)].notes = ged.fam[num].notes
            if ged.fam[num].sources:
                tree.fam[(husb, wife)].sources = ged.fam[num].sources
            tree.fam[(husb, wife)].sealing_spouse = ged.fam[num].sealing_spouse

    # merge notes by text
    tree.notes = sorted(tree.notes, key=lambda x: x.text)
    for i, n in enumerate(tree.notes):
        if i == 0:
            n.num = 1
            continue
        if n.text == tree.notes[i - 1].text:
            n.num = tree.notes[i - 1].num
        else:
            n.num = tree.notes[i - 1].num + 1

    # compute number for family relationships and print GEDCOM file
    tree.reset_num()
    tree.print(args.o)
