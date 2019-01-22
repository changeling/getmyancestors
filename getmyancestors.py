#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
   getmyancestors.py - Retrieve GEDCOM data from FamilySearch Tree
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

# global import
from __future__ import print_function
import sys
import argparse
import getpass
import time
import asyncio
import re

# Local import
from shared_classes import Session, Tree

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Retrieve GEDCOM data from FamilySearch Tree (4 Jul 2016)', add_help=False, usage='getmyancestors.py -u username -p password [options]')
    parser.add_argument('-u', metavar='<STR>', type=str, help='FamilySearch username')
    parser.add_argument('-p', metavar='<STR>', type=str, help='FamilySearch password')
    parser.add_argument('-i', metavar='<STR>', nargs='+', type=str, help='List of individual FamilySearch IDs for whom to retrieve ancestors')
    parser.add_argument('-a', metavar='<INT>', type=int, default=4, help='Number of generations to ascend [4]')
    parser.add_argument('-d', metavar='<INT>', type=int, default=0, help='Number of generations to descend [0]')
    parser.add_argument('-m', action="store_true", default=False, help='Add spouses and couples information [False]')
    parser.add_argument('-r', action="store_true", default=False, help='Add list of contributors in notes [False]')
    parser.add_argument('-c', action="store_true", default=False, help='Add LDS ordinances (need LDS account) [False]')
    parser.add_argument("-v", action="store_true", default=False, help="Increase output verbosity [False]")
    parser.add_argument('-t', metavar='<INT>', type=int, default=60, help='Timeout in seconds [60]')
    try:
        parser.add_argument('-o', metavar='<FILE>', type=argparse.FileType('w', encoding='UTF-8'), default=sys.stdout, help='output GEDCOM file [stdout]')
        parser.add_argument('-l', metavar='<FILE>', type=argparse.FileType('w', encoding='UTF-8'), default=sys.stderr, help='output log file [stderr]')
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

    if args.i:
        for fid in args.i:
            if not re.match(r'[A-Z0-9]{4}-[A-Z0-9]{3}', fid):
                exit('Invalid FamilySearch ID: ' + fid)

    username = args.u if args.u else input("Enter FamilySearch username: ")
    password = args.p if args.p else getpass.getpass("Enter FamilySearch password: ")

    time_count = time.time()

    # initialize a FamilySearch session and a family tree object
    print('Login to FamilySearch...')
    fs = Session(username, password, args.v, args.l, args.t)
    if not fs.logged:
        exit(2)
    _ = fs._
    tree = Tree(fs)

    # check LDS account
    if args.c and fs.get_url('/platform/tree/persons/%s/ordinances.json' % fs.get_userid()) == 'error':
        exit(2)

    # add list of starting individuals to the family tree
    todo = args.i if args.i else [fs.get_userid()]
    print(_('Download starting individuals...'))
    tree.add_indis(todo)

    # download ancestors
    todo = set(todo)
    done = set()
    for i in range(args.a):
        if not todo:
            break
        done |= todo
        print(_('Download ') + num2words(i + 1, to='ordinal_num', lang=fs.lang) + _(' generation of ancestors...'))
        todo = tree.add_parents(todo) - done

    # download descendants
    todo = set(tree.indi.keys())
    done = set()
    for i in range(args.d):
        if not todo:
            break
        done |= todo
        print(_('Download ') + num2words(i + 1, to='ordinal_num', lang=fs.lang) + _(' generation of descendants...'))
        todo = tree.add_children(todo) - done

    # download spouses
    if args.m:
        print(_('Download spouses and marriage information...'))
        todo = set(tree.indi.keys())
        tree.add_spouses(todo)

    # download ordinances, notes and contributors
    async def download_stuff(loop):
        futures = set()
        for fid, indi in tree.indi.items():
            futures.add(loop.run_in_executor(None, indi.get_notes))
            if args.c:
                futures.add(loop.run_in_executor(None, tree.add_ordinances, fid))
            if args.r:
                futures.add(loop.run_in_executor(None, indi.get_contributors))
        for fam in tree.fam.values():
            futures.add(loop.run_in_executor(None, fam.get_notes))
            if args.r:
                futures.add(loop.run_in_executor(None, fam.get_contributors))
        for future in futures:
            await future

    loop = asyncio.get_event_loop()
    print(_('Download notes') + (((',' if args.r else _(' and')) + _(' ordinances')) if args.c else '') + (_(' and contributors') if args.r else '') + '...')
    loop.run_until_complete(download_stuff(loop))

    # compute number for family relationships and print GEDCOM file
    tree.reset_num()
    tree.print(args.o)
    print(_('Downloaded %s individuals, %s families, %s sources and %s notes in %s seconds with %s HTTP requests.') % (str(len(tree.indi)), str(len(tree.fam)), str(len(tree.sources)), str(len(tree.notes)), str(round(time.time() - time_count)), str(fs.counter)))
