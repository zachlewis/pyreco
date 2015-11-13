__FILENAME__ = render8dirs
import bpy
from math import radians

angle = 45
axis = 2 # z-axis
platform = bpy.data.objects["RenderPlatform"]
original_path = bpy.data.scenes[0].render.filepath

bpy.ops.render.view_show()

for i in range(0,8):
	
	# rotate the render platform and all children
	temp_rot = platform.rotation_euler
	temp_rot[axis] = temp_rot[axis] - radians(angle)
	platform.rotation_euler = temp_rot;
	
	# set the filename direction prefix
	bpy.data.scenes[0].render.filepath = original_path + str(i)
	
	# render animation for this direction
	bpy.ops.render.render(animation=True)

bpy.data.scenes[0].render.filepath = original_path

########NEW FILE########
__FILENAME__ = xgettext
#! /usr/bin/python
import os
import datetime
import codecs   # proper UTF8 handling with files

keys = []
comments = []
now = datetime.datetime.now()
header = r'''# Copyright (C) 2011 Clint Bellanger
# This file is distributed under the same license as the FLARE package.
#
# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.
msgid ""
msgstr ""
"Project-Id-Version: PACKAGE VERSION\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: {now}\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
"Language-Team: LANGUAGE <LL@li.org>\n"
"Language: \n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"

'''

POT_STRING = u'''\
#: {comment}
msgid "{msgid}"
msgstr ""

'''

# this extracts translatable strings from the flare data file
def extract(filename):
    if not os.path.exists(filename):
        return
    infile = codecs.open(filename, encoding='UTF-8', mode='r')
    triggers = [
        'msg', 'him', 'her', 'you', 'name', 'title', 'tooltip',
        'power_desc', 'quest_text', 'description', 'item_type',
        'slot_name', 'tab_title', 'resist', 'currency_name',
        'bonus', 'flavor', 'topic', 'option', 'caption'
    ]
    plain_text = [
        'msg', 'him', 'her', 'you', 'name', 'title', 'tooltip',
        'quest_text', 'description', 'topic', 'flavor', 'caption',
        ]
    for i, line in enumerate(infile, start=1):
        for trigger in triggers:
            if line.startswith(trigger + '='):
                line = line.split('=')[1]
                line = line.strip('\n')
                values = line.split(',')
                if (trigger in plain_text):
                   stat = line.replace("\"", "\\\"");
                elif len(values) == 1:
                   # {key}={value}
                   stat, = values
                elif len(values) == 2:
                   # bonus={stat},{value}
                   stat, value = values
                elif len(values) == 3:
                   # bonus={set_level},{stat},{value}
                   set_level, stat, value = values
                elif len(values) == 4:
                   # option=base,head,portrait,name
                   stat = values[-1]
                comment = filename + ':' + str(i)
                comments.append(comment)
                keys.append(stat.rstrip())

# this removes duplicates from keys in a clean way (without screwing up the order)
def remove_duplicates():
    global comments
    global keys
    tmp = []
    tmp_c = []
    for node_c,node in zip(comments,keys):
        if node not in tmp:
            tmp_c.append(node_c)
            tmp.append(node)
    comments = tmp_c
    keys = tmp

# this writes the list of keys to a gettext .po file
def save(filename):
    outfile = codecs.open('data.pot', encoding='UTF-8', mode='w')
    outfile.write(header.format(now=now.strftime('%Y-%m-%d %H:%M+%z')))
    remove_duplicates()
    for line_c,line in zip(comments,keys):
        outfile.write(POT_STRING.format(comment=line_c, msgid=line))

# this extracts the quest files from the quests directory
def get_quests():
    quests = set()
    infile = open('../quests/index.txt', 'r')
    for line in infile.readlines():
        quests.add(line.strip('\n'))
    infile.close()
    return quests


# HERE'S THE MAIN EXECUTION
extract('../items/items.txt')
extract('../items/types.txt')
extract('../items/sets.txt')
extract('../menus/inventory.txt')
extract('../menus/powers.txt')
extract('../powers/effects.txt')
extract('../powers/powers.txt')
extract('../engine/elements.txt')
extract('../engine/loot.txt')
extract('../engine/classes.txt')
extract('../engine/hero_options.txt')
extract('../engine/titles.txt')
extract('../engine/equip_flags.txt')

for folder in ['enemies', 'maps', 'quests', 'npcs', 'cutscenes']:
    target = os.path.join('..', folder)
    if os.path.exists(target):
        for filename in sorted(os.listdir(target)):
            extract(os.path.join(target, filename))

save('data.pot')

########NEW FILE########
__FILENAME__ = xgettext
#! /usr/bin/python
import os
import datetime
import codecs   # proper UTF8 handling with files

keys = []
comments = []
now = datetime.datetime.now()
header = r'''# Copyright (C) 2011 Clint Bellanger
# This file is distributed under the same license as the FLARE package.
#
# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.
msgid ""
msgstr ""
"Project-Id-Version: PACKAGE VERSION\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: {now}\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
"Language-Team: LANGUAGE <LL@li.org>\n"
"Language: \n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"

'''

POT_STRING = u'''\
#: {comment}
msgid "{msgid}"
msgstr ""

'''

# this extracts translatable strings from the flare data file
def extract(filename):
    if not os.path.exists(filename):
        return
    infile = codecs.open(filename, encoding='UTF-8', mode='r')
    triggers = [
        'msg', 'him', 'her', 'you', 'name', 'title', 'tooltip',
        'power_desc', 'quest_text', 'description', 'item_type',
        'slot_name', 'tab_title', 'resist', 'currency_name',
        'bonus', 'flavor', 'topic', 'option', 'caption'
    ]
    plain_text = [
        'msg', 'him', 'her', 'you', 'name', 'title', 'tooltip',
        'quest_text', 'description', 'topic', 'flavor', 'caption',
        ]
    for i, line in enumerate(infile, start=1):
        for trigger in triggers:
            if line.startswith(trigger + '='):
                line = line.split('=')[1]
                line = line.strip('\n')
                values = line.split(',')
                if (trigger in plain_text):
                   stat = line.replace("\"", "\\\"");
                elif len(values) == 1:
                   # {key}={value}
                   stat, = values
                elif len(values) == 2:
                   # bonus={stat},{value}
                   stat, value = values
                elif len(values) == 3:
                   # bonus={set_level},{stat},{value}
                   set_level, stat, value = values
                elif len(values) == 4:
                   # option=base,head,portrait,name
                   stat = values[-1]
                comment = filename + ':' + str(i)
                comments.append(comment)
                keys.append(stat.rstrip())

# this removes duplicates from keys in a clean way (without screwing up the order)
def remove_duplicates():
    global comments
    global keys
    tmp = []
    tmp_c = []
    for node_c,node in zip(comments,keys):
        if node not in tmp:
            tmp_c.append(node_c)
            tmp.append(node)
    comments = tmp_c
    keys = tmp

# this writes the list of keys to a gettext .po file
def save(filename):
    outfile = codecs.open('data.pot', encoding='UTF-8', mode='w')
    outfile.write(header.format(now=now.strftime('%Y-%m-%d %H:%M+%z')))
    remove_duplicates()
    for line_c,line in zip(comments,keys):
        outfile.write(POT_STRING.format(comment=line_c, msgid=line))

# this extracts the quest files from the quests directory
def get_quests():
    quests = set()
    infile = open('../quests/index.txt', 'r')
    for line in infile.readlines():
        quests.add(line.strip('\n'))
    infile.close()
    return quests


# HERE'S THE MAIN EXECUTION
extract('../items/items.txt')
extract('../items/types.txt')
extract('../items/sets.txt')
extract('../menus/inventory.txt')
extract('../menus/powers.txt')
extract('../powers/effects.txt')
extract('../powers/powers.txt')
extract('../engine/elements.txt')
extract('../engine/loot.txt')
extract('../engine/classes.txt')
extract('../engine/hero_options.txt')
extract('../engine/titles.txt')
extract('../engine/equip_flags.txt')

for folder in ['enemies', 'maps', 'quests', 'npcs', 'cutscenes']:
    target = os.path.join('..', folder)
    if os.path.exists(target):
        for filename in sorted(os.listdir(target)):
            extract(os.path.join(target, filename))

save('data.pot')

########NEW FILE########
