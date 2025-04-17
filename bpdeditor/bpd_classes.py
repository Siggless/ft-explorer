from __future__ import annotations
import copy
import struct
from enum import Enum

'''
Enums from GearboxFramework.BehaviorProviderDefinition unreal script
'''
class VariableLinkTypes(Enum):
    BVARLINK_Unknown=0
    BVARLINK_Context=1
    BVARLINK_Input=2
    BVARLINK_Output=3
    BVARLINK_MAX=4

class VariableTypes(Enum):
    BVAR_None = 0
    BVAR_Bool = 1
    BVAR_Int = 2
    BVAR_Float = 3
    BVAR_Vector = 4
    BVAR_Object = 5
    BVAR_AllPlayers = 6
    BVAR_Attribute = 7
    BVAR_InstanceData = 8
    BVAR_NamedVariable = 9
    BVAR_NamedKismetVariable = 10
    BVAR_DirectionVector = 11
    BVAR_AttachmentLocation = 12
    BVAR_UnaryMath = 13
    BVAR_BinaryMath = 14
    BVAR_Flag = 15
    BVAR_MAX = 16
    

'''
Functions from bpd_dot.py
'''
 
def parse_arrayindexandlength(number):
    """
    Returns an array index and length tuple for the given number.
    """
    # Could just use >> and & for this, but since we have to be more
    # careful with LinkIdAndLinkedBehavior anyway, since that one's
    # weirder, we may as well just use struct here, as well.
    number = int(number)
    byteval = struct.pack('>i', number)
    return struct.unpack('>HH', byteval)

def parse_linkidandlinkedbehavior(number):
    """
    Returns a link ID index and behavior tuple for the given number.
    """
    number = int(number)
    byteval = struct.pack('>i', number)
    (linkid, junk, behavior) = struct.unpack('>bbH', byteval)
    return (linkid, behavior)

def pack_arrayindexandlength(index:int, length:int):
    """
    Returns an ArrayIndexAndLength for the given index and length.
    IDK how this works, just reversing the parse function.
    """
    byteval = struct.pack('>HH', index, length)
    return struct.unpack('>i', byteval)[0]

def pack_linkidandlinkedbehavior(linkId:int, behaviorIndex:int):
    """
    Returns a LinkIdAndLinkedBehavior for the given linkId and behavior index.
    """
    byteval = struct.pack('>bbH', linkId, 0, behaviorIndex)
    return struct.unpack('>i', byteval)[0]


'''
I use QStandardItemModels mapping the column indexes to the item fields,
 so that I can use a QDataWidgetMapper to handle the widget inputs.
The views also use the QStandardItems directly where possible.
'''


class BehaviorSequence:
    def __init__(self, seq):
        self.NodeData = seq
        if 'BehaviorSequenceName' in seq:
            self.Name: str = seq['BehaviorSequenceName'].strip('"')
        
        # Even though we have the models we still use these lists for exporting
        #  since we filter out any invalid model items (-1s if all removed)
        self.ConsolidatedOutputLinkData = []
        '''OutputLinkData array of links to subsequent behaviors'''
        self.ConsolidatedVariableLinkData = []
        '''VariableLinkData array of links to ConsolidatedLinkedVariables'''
        self.ConsolidatedLinkedVariables = []
        '''Array of indexes pointing to VariableData'''
        
        # Parse CLV first outside of models for lookup
        self.ConsolidatedLinkedVariables = []
        if seq['ConsolidatedLinkedVariables'] != '':
            self.ConsolidatedLinkedVariables = [int(i) for i in seq['ConsolidatedLinkedVariables'].split(',')]
                    
        # Now make the view models
        from PyQt5.QtCore import QStringListModel
        self.varTypeModel: QStringListModel = QStringListModel(VariableTypes._member_names_[0:VariableTypes.BVAR_MAX.value])
        self.linkTypeModel: QStringListModel = QStringListModel(VariableLinkTypes._member_names_[0:VariableLinkTypes.BVARLINK_MAX.value])

        from bpdeditor.model_variable import VariableItem, VariableItemModel
        self.varModel: VariableItemModel = VariableItemModel([VariableItem(self, i) for i in seq['VariableData']], self)
        from bpdeditor.model_varlink import VarLinkItem, VarLinkItemModel
        self.varLinkModel: VarLinkItemModel = VarLinkItemModel([VarLinkItem(self, i) for i in seq['ConsolidatedVariableLinkData']], self)
        from bpdeditor.model_event import EventItem, EventItemModel
        self.eventModel: EventItemModel = EventItemModel([EventItem(self, i) for i in seq['EventData2']], self)
        from bpdeditor.model_behavior import BehaviorItem, BehaviorItemModel
        self.behaviorModel: BehaviorItemModel = BehaviorItemModel([BehaviorItem(self, i) for i in seq['BehaviorData2']], self)
        # Out Links last to look up behaviorItemModel
        from bpdeditor.model_outlink import OutLinkItem, OutLinkItemModel
        self.outLinkModel: OutLinkItemModel = OutLinkItemModel([OutLinkItem(self, i) for i in seq['ConsolidatedOutputLinkData']], self, self.behaviorModel)
        self.eventModel.createLinks(self.outLinkModel, self.varLinkModel)
        self.behaviorModel.createLinks(self.outLinkModel, self.varLinkModel)
    
    
    def Reconsolidate(self):
        """
        Reconsolidate the COLD, CVLD and CLV data based on the current model links.
        The unpacked indexes are up-to-date, we just need to reorder the indexes to
         be consecutive, and then repack the ArrayIndexAndLengths.
        """
        from PyQt5.QtCore import QPersistentModelIndex
        
        # Step 1 - Jump on ya bike
        #   I'm making my own CLV list to combine simple links.
        #   The first part of the list is just indexes in order. These are shared between any links with single variables
        #   After this we just append any sequences from links with multiple variables.
        self.EventData2 = [self.eventModel.item(i) for i in range(self.eventModel.rowCount())]
        self.BehaviorData2 = [self.behaviorModel.item(i) for i in range(self.behaviorModel.rowCount())]
        self.VariableData = [self.varModel.item(i) for i in range(self.varModel.rowCount())]
        self.ConsolidatedLinkedVariables = [*range(self.varModel.rowCount())]
        self.ConsolidatedVariableLinkData = []
        self.ConsolidatedOutputLinkData = []
        
        # Step 2 - Do a backflip or two
        events = [self.eventModel.item(i) for i in range(self.eventModel.rowCount())]
        behaviors = [self.behaviorModel.item(i) for i in range(self.behaviorModel.rowCount())]
        for item in events + behaviors:
            
            # Variable links - need to make sure indexes are consecutive for ArrayIndexAndLength
            varLinkItems = item.GetAllVarLinkItems()
            validLinkItems = [i for i in varLinkItems if any(j >= 0 for j in i.GetAllVariableIndexes())]
            linkLength = len(validLinkItems)
            if linkLength > 0:
                linkIndex = len(self.ConsolidatedVariableLinkData)
                for link in validLinkItems:
                    indexes = link.GetAllVariableIndexes()
                    validIndexes = [i for i in indexes if i >= 0]
                    length = len(validIndexes)
                    if length == 0:
                        link._LinkedVariables = 0
                        link._LinkedVariableIndexes = []
                        continue
                    
                    self.ConsolidatedVariableLinkData.append(link)
                    if length == 1:
                        # If only one, just point to fixed index in CLVs
                        index = validIndexes[0]
                    else:
                        # If multiple, append these onto CLVs
                        index = len(validIndexes)
                        self.ConsolidatedLinkedVariables = self.ConsolidatedLinkedVariables + validIndexes
                    link._LinkedVariables = pack_arrayindexandlength(index, length)
                    link._LinkedVariableIndexes = [*range(index, index + length)]
                # Model list must be complete here to get the new indexes right
                item.LinkedVariables = pack_arrayindexandlength(linkIndex, linkLength)
                item._VariableIndexes = [QPersistentModelIndex(self.varLinkModel.index(i, 3 + idx)) for idx, i in enumerate(range(linkIndex, linkIndex + linkLength))]
            else:
                item.LinkedVariables = 0

            # Output links
            outLinkItems = item.GetAllOutLinkItems()
            validOutItems = [i for i in outLinkItems if i.LinkIndex >= 0]
            length = len(validOutItems)
            if length > 0:
                index = len(self.ConsolidatedOutputLinkData)
                # Shouldn't be necessary, but just in case...
                item.OutputLinks = pack_arrayindexandlength(index, length)
                for link in validOutItems:
                    # Again just in case...
                    link.LinkIdAndLinkedBehavior = pack_linkidandlinkedbehavior(link.LinkId, link.LinkIndex)
                    self.ConsolidatedOutputLinkData.append(link)
            else:
                item.OutputLinks = 0

        # Step 3 - Vibe on your cool moves


    def PrintDump(self) -> str:
        """ Prints the BPD sequence in object dump (hotfix) format """
        from bpdeditor.model_variable import VariableItem, VariableItemModel
        from bpdeditor.model_varlink import VarLinkItem, VarLinkItemModel
        from bpdeditor.model_event import EventItem, EventItemModel
        from bpdeditor.model_behavior import BehaviorItem, BehaviorItemModel
        from bpdeditor.model_outlink import OutLinkItem, OutLinkItemModel
        
        stringy:str = "EventData2=("
        for row in range(self.eventModel.rowCount()):
            i: EventItem = self.eventModel.item(row)
            stringy += '(' + str(i) + '),'
        stringy = stringy.removesuffix(',')
        
        stringy += '),BehaviorData2=('
        for row in range(self.behaviorModel.rowCount()):
            i: BehaviorItem = self.behaviorModel.item(row)
            stringy += '(' + str(i) + '),'
        stringy = stringy.removesuffix(',')
        
        stringy += '),VariableData=('
        for row in range(self.varModel.rowCount()):
            i: VariableItem = self.varModel.item(row)
            stringy += '(' + str(i) + '),'
        stringy = stringy.removesuffix(',')
        
        stringy += '),ConsolidatedOutputLinkData=('
        for i in self.ConsolidatedOutputLinkData:
            stringy += '(' + str(i) + '),'
        stringy = stringy.removesuffix(',')
        
        stringy += '),ConsolidatedVariableLinkData=('
        for i in self.ConsolidatedVariableLinkData:
            stringy += str(i) + ','
        stringy = stringy.removesuffix(',')
        
        stringy += '),ConsolidatedLinkedVariables=('
        for i in self.ConsolidatedLinkedVariables:
            stringy += str(i) + ','
        stringy = stringy.removesuffix(',')
        
        stringy += ')'
        return stringy
    
    
    def ExportNodeStructure(self):
        """ Exports our sequence object data back into data dictionary structure """
        from bpdeditor.model_variable import VariableItem, VariableItemModel
        from bpdeditor.model_varlink import VarLinkItem, VarLinkItemModel
        from bpdeditor.model_event import EventItem, EventItemModel
        from bpdeditor.model_behavior import BehaviorItem, BehaviorItemModel
        from bpdeditor.model_outlink import OutLinkItem, OutLinkItemModel
        
        node = copy.deepcopy(self.NodeData)
        node['EventData2'] = []
        for row in range(self.eventModel.rowCount()):
            i: EventItem = self.eventModel.item(row)
            node['EventData2'].append({
                'UserData':{i.UserData},
                'OutputVariables':{'ArrayIndexAndLength':i.LinkedVariables},
                'OutputLinks':{'ArrayIndexAndLength':i.OutputLinks}
            })
        
        node['BehaviorData2'] = []
        for row in range(self.behaviorModel.rowCount()):
            i: BehaviorItem = self.behaviorModel.item(row)
            node['VariableData'].append({
                'Behavior': f'{i.BehaviorClass}\'{i.BehaviorObject}\'',
                'LinkedVariables': {'ArrayIndexAndLength':i.LinkedVariables,'OutputLinks':{'ArrayIndexAndLength':i.OutputLinks}}
                })
        
        node['VariableData'] = []
        for row in range(self.varModel.rowCount()):
            i: VariableItem = self.varModel.item(row)
            node['VariableData'].append({
                'Name': f'\"{i.Name}\"' if len(i.Name)>0 else '',
                'Type': i.Type.name
                })
        
        node['ConsolidatedOutputLinkData'] = []
        for i in self.ConsolidatedOutputLinkData:
            node['ConsolidatedOutputLinkData'].append({
                'ActivateDelay': i.LinkIdAndLinkedBehavior,
                'Type': i.ActiveDelay
                })
        
        node['ConsolidatedVariableLinkData'] = []
        for i in self.ConsolidatedVariableLinkData:
            node['ConsolidatedVariableLinkData'].append({
                'PropertyName': i.PropertyName,
                'VariableLinkType': i.VariableLinkType._name_,
                'ConnectionIndex': str(i.ConnectionIndex),
                'LinkedVariables': {'ArrayIndexAndLength':i.LinkedVariables},
                'CachedPropery': str(i.CachedProperty)
                })
        
        node['ConsolidatedLinkedVariables'] = ''
        for i in self.ConsolidatedLinkedVariables:
            node['ConsolidatedLinkedVariables'] += str(i) + ','
        
        node['ConsolidatedLinkedVariables']=node['ConsolidatedLinkedVariables'].removesuffix(',')
        return node
    