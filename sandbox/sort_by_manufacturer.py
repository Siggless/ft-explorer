#!/usr/bin/python
# vim: set expandtab tabstop=4 shiftwidth=4:

import sys
from ftexplorer.data import Data

def get_manufacturers(baldef_name, data):
    manufs = set()
    baldef = data.get_struct_by_full_object(baldef_name)
    if 'Manufacturers' in baldef:
        for manuf in baldef['Manufacturers']:
            manufs.add(Data.get_attr_obj(manuf['Manufacturer']))
    elif 'BaseDefinition' in baldef:
        basedef_full = baldef['BaseDefinition']
        if basedef_full != 'None':
            manufs |= get_manufacturers(Data.get_attr_obj(baldef['BaseDefinition']), data)
    return manufs

data = Data('BL2')
baldef_names = data.get_all_by_type('WeaponBalanceDefinition') + data.get_all_by_type('InventoryBalanceDefinition')

no_manufacturer = []
manufacturer_map = {}
multi_manufacturers = set()
for baldef_name in baldef_names:
    if 'Default__' not in baldef_name:
        manufs = get_manufacturers(baldef_name, data)
        if len(manufs) == 0:
            print('WARNING: No manufacturers found for {}'.format(baldef_name))
            no_manufacturer.append(baldef_name)
        else:
            for manuf in manufs:
                if manuf not in manufacturer_map:
                    manufacturer_map[manuf] = []
                manufacturer_map[manuf].append(baldef_name)

        if len(manufs) > 1:
            multi_manufacturers.add(baldef_name)

#print(no_manufacturer)
#print(manufacturer_map)
#print(multi_manufacturer_map)

# Output as some Python structures
out_file = 'manufacturer_gear.py'
with open(out_file, 'w') as df:
    print('# Generated by sort_by_manufacturer.py', file=df)
    print('no_manufacturer = [', file=df)
    for baldef_name in sorted(no_manufacturer):
        print("        '{}',".format(baldef_name), file=df)
    print('        ]', file=df)
    print('', file=df)
    print('manufacturer_map = {', file=df)
    for manuf, baldef_names in sorted(manufacturer_map.items()):
        print("        '{}': [".format(manuf), file=df)
        for baldef_name in sorted(baldef_names):
            if baldef_name in multi_manufacturers:
                extra = ' # multi-manufacturer balance!'
            else:
                extra = ''
            print("            '{}',{}".format(baldef_name, extra), file=df)
        print('            ],', file=df)
    print('        }', file=df)
    print('', file=df)
print('Done, wrote to {}'.format(out_file))
