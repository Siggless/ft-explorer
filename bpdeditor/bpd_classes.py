from __future__ import annotations
import copy
from enum import Enum
import struct

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
Python classes to populate from the node data.
The node data is deep copied now so that we can edit it.
So after doing it all with these, IDK why I didn't just keep it as a dict.
I guess this could be used as a view model to handle the updates instead of the GUI... but it doesn't......
'''
   
class VariableData:
    def __init__(self, nodeData, sequence:BehaviorSequence):
        self.sequence = sequence
        self.Name:str = nodeData['Name'].strip('"')
        self.Type:VariableTypes = VariableTypes[nodeData['Type']]


class VariableLinkData:
    def __init__(self, nodeData, sequence:BehaviorSequence):
        self.sequence = sequence
        self.PropertyName:str=nodeData['PropertyName'].strip('"')
        self.VariableLinkType:VariableLinkTypes = VariableLinkTypes[nodeData['VariableLinkType']]
        self.ConnectionIndex = int(nodeData['ConnectionIndex'])
        '''Used on some Output variables - seems to be only Events - the parameter index passed to the output?'''
        self.LinkedVariables:int = int(nodeData['LinkedVariables']['ArrayIndexAndLength'])
        '''ArrayIndexAndLength pointing to ConsolidatedLinkedVariables'''
        self.CachedProperty = str(nodeData['CachedProperty'])
        
        # Save the linked VariableData objects
        self.LinkedVariableIndexes=[]
        self.LinkedVariableList=[]
        if self.sequence:
            (index, length) = parse_arrayindexandlength(self.LinkedVariables)
            self.LinkedVariableIndexes = [self.sequence.ConsolidatedLinkedVariables[i] for i in range(index, index+length)]
            self.LinkedVariableList = [self.sequence.VariableData[self.sequence.ConsolidatedLinkedVariables[i]] if i >=0 else None for i in range(index, index+length)]

    def PrintDump(self) -> str:
        stringy:str = f'(PropertyName=\"{self.PropertyName}\",'
        stringy += f'VariableLinkType={self.VariableLinkType._name_},'
        stringy += f'ConnectionIndex={str(self.ConnectionIndex)},'
        stringy += f'LinkedVariables=(ArrayIndexAndLength={self.LinkedVariables}),'
        stringy += f'CachedProperty={str(self.CachedProperty)})'
        return stringy

class OutputLinkData:
    def __init__(self, nodeData, sequence:BehaviorSequence):
        self.sequence = sequence
        self.LinkIdAndLinkedBehavior=int(nodeData['LinkIdAndLinkedBehavior'])
        self.ActiveDelay:float=float(nodeData['ActivateDelay'])
        (linkID, behaviorIndex) = parse_linkidandlinkedbehavior(self.LinkIdAndLinkedBehavior)
        self.LinkId:int = linkID
        self.LinkIndex:int = behaviorIndex
        
        # Save the linked BehaviorData object
        self.LinkedBehavior:BehaviorData = self.sequence.BehaviorData2[self.LinkIndex]


class EventData:    
    def __init__(self, nodeData, sequence:BehaviorSequence):
        self.sequence = sequence
        self.NodeData = nodeData
        self.UserData:dict = nodeData['UserData']
        self.LinkedVariables:int = int(nodeData['OutputVariables']['ArrayIndexAndLength'])
        self.OutputLinks:int = int(nodeData['OutputLinks']['ArrayIndexAndLength'])
        
        self.Outputs=[]
        """ List of OutputLinkDatas from the OutputLinks ArrayIndexAndLength """
        self.Variables=[]
        """ List of VariableLinkDatas from CVLD """
        (index, length) = parse_arrayindexandlength(self.LinkedVariables)
        self.Variables=[sequence.ConsolidatedVariableLinkData[i] for i in range(index, index+length)]
    
    def PrintDump(self) -> str:
        stringy:str = f'UserData=('
        for key, value in self.UserData.items():
            stringy += f'{str(key)}={str(value)},'

        stringy = stringy.removesuffix(',')
        stringy += f'),OutputVariables=(ArrayIndexAndLength={self.LinkedVariables}),OutputLinks=(ArrayIndexAndLength={self.OutputLinks})'
        return stringy
    
    
class BehaviorData:
    def __init__(self, nodeData, sequence:BehaviorSequence):
        self.sequence = sequence
        self.NodeData = nodeData
        self.Behavior:str = nodeData['Behavior']
        self.BehaviorClass:str = 'None'
        self.BehaviorObject:str = 'None'
        if self.Behavior != 'None':     # GD_ConstructorRoland.Projectiles.Proj_Ep6_ReinforcementFlare:BehaviorProviderDefinition_0
            self.BehaviorClass:str = self.Behavior.split('\'')[0]
            self.BehaviorObject:str = self.Behavior.split('\'')[1]
        self.LinkedVariables:int = int(nodeData['LinkedVariables']['ArrayIndexAndLength'])
        self.OutputLinks:int = int(nodeData['OutputLinks']['ArrayIndexAndLength'])
        
        self.Outputs=[]
        """ List of OutputLinkDatas from the OutputLinks ArrayIndexAndLength """
        self.Variables=[]
        """ List of VariableLinkDatas from CVLD """
        (index, length) = parse_arrayindexandlength(self.LinkedVariables)
        self.Variables=[sequence.ConsolidatedVariableLinkData[i] for i in range(index, index+length)]
    
    def PrintDump(self) -> str:
        stringy:str = f'Behavior={self.BehaviorClass}\'{self.BehaviorObject}\','
        stringy += f'LinkedVariables=(ArrayIndexAndLength={self.LinkedVariables}),OutputLinks=(ArrayIndexAndLength={self.OutputLinks})'
        return stringy


class BehaviorSequence:
    EventData2 = []
    BehaviorData2 = []
    VariableData = []
    '''Array of the actual variables used'''
    ConsolidatedOutputLinkData = []
    '''OutputLinkData array of links to subsequent behaviors'''
    ConsolidatedVariableLinkData = []
    '''VariableLinkData array of links to ConsolidatedLinkedVariables'''
    ConsolidatedLinkedVariables = []
    '''Array of indexes pointing to VariableData'''
    
    def __init__(self, seq):
        self.NodeData = copy.deepcopy(seq)
        if 'BehaviorSequenceName' in seq:
            self.Name:str = seq['BehaviorSequenceName'].strip('"')
        
        # Parse variables first so we have objects to link
        self.VariableData = [VariableData(i, self) for i in seq['VariableData']]
        self.ConsolidatedLinkedVariables = []
        if seq['ConsolidatedLinkedVariables'] != '':
            self.ConsolidatedLinkedVariables = [int(i) for i in seq['ConsolidatedLinkedVariables'].split(',')]
        self.ConsolidatedVariableLinkData = [VariableLinkData(i, self) for i in seq['ConsolidatedVariableLinkData']]
        
        self.EventData2 = [EventData(i, self) for i in seq['EventData2']]
        self.BehaviorData2 = [BehaviorData(i, self) for i in seq['BehaviorData2']]
        self.ConsolidatedOutputLinkData = [OutputLinkData(i, self) for i in seq['ConsolidatedOutputLinkData']]

        # Now store all the output links in the objects
        if len(self.ConsolidatedOutputLinkData)>0:   # Dark_Forest_Combat.TheWorld:PersistentLevel.Main_Sequence.InterpData_0.InterpGroup_0.InterpTrackBehaviors_0.BehaviorProviderDefinition_0
            for i in self.EventData2 + self.BehaviorData2:
                (index, length) = parse_arrayindexandlength(i.OutputLinks)       
                for j in range(index, index+length):
                    linkData = self.ConsolidatedOutputLinkData[j]
                    i.Outputs.append(linkData)
    
    """
    The following reconsolidation and export will only be usable
    if the ConsolidatedVariableLinkData is actually editable,
    which the online Wiki says it isn't - time to test this!
    """
    
    def Reconsolidate(self, graph):
        """
        Reconsolidate the COLD, CVLD and CLV data based on the current graph connections.
        EventData, BehaviorData and VariableData should already be updated to any changes
        """
        # Alright suckas lets do this
        from bpdeditor.bpd_gui import SequenceNode, EventNode, BehaviorNode
        
        # Step 1 - Jump on ya bike
        #   I'm making my own CLV list to combine simple links
        #   The first part of the list is just indexes in order. These are shared between any linked with single variables (I haven't seen any with multiple yet)
        #   After this we just append any sequences from links with multiple variables.
        self.ConsolidatedLinkedVariables = [*range(len(self.VariableData))]
        self.ConsolidatedVariableLinkData = []
        self.ConsolidatedOutputLinkData = []
        
        # Step 2 - Do a backflip or two
        for node in graph.sequenceNodes:
            
            data = node.data
            # Variable links - just need to update the LinkedVariables ArrayIndexAndLength
            data.Variables=[]
            data.VariableIndexes=[]
            linkIndex = len(self.ConsolidatedVariableLinkData)
            validLinks = [i.link for i in node.varLinkList.items if any(j.currentIndex()>=0 for j in i.varDropdownList)]
            data.Variables = validLinks
            linkLength = len(validLinks)
            if linkLength > 0:
                data.LinkedVariables = pack_arrayindexandlength(linkIndex, linkLength)
                for link in validLinks:
                    validIndexes = [i for i in link.LinkedVariableIndexes if i >= 0]
                    length = len(validIndexes)
                    if length == 0:
                        link.LinkedVariables = 0
                        continue
                    
                    self.ConsolidatedVariableLinkData.append(link)
                    if length == 1:
                        # If only one, just point to fixed index in CLVs
                        index = validIndexes[0]
                    else:
                        # If multiple, append these onto CLVs
                        index = len(validIndexes)
                        self.ConsolidatedLinkedVariables = self.ConsolidatedLinkedVariables + validIndexes
                    link.LinkedVariables = pack_arrayindexandlength(index, length)
                data.VariableIndexes = validIndexes
            else:
                data.LinkedVariables = 0

            # Output links
            data.Outputs=[]
            index = len(self.ConsolidatedOutputLinkData)
            validOutputs = [i for i in node.outLinkList.items if i.dropdown.currentIndex() >= 0]
            length = len(validOutputs)
            if length > 0:
                data.OutputLinks = pack_arrayindexandlength(index, length)
                for item in validOutputs:
                    output = item.link
                    output.LinkIdAndLinkedBehavior=pack_linkidandlinkedbehavior(output.LinkId,output.LinkIndex)
                    output.LinkedBehavior = output.sequence.BehaviorData2[output.LinkIndex]
                    data.Outputs.append(output)
                    self.ConsolidatedOutputLinkData.append(output)
            else:
                data.OutputLinks = 0

        # Step 3 - Vibe on your cool moves


    def PrintDump(self) -> str:
        """ Prints the BPD sequence in object dump (hotfix) format """
        stringy:str = "EventData2=("
        for i in self.EventData2:
            stringy += '(' + i.PrintDump() + '),'
        stringy = stringy.removesuffix(',')
        stringy += '),BehaviorData2=('
        for i in self.BehaviorData2:
            stringy += '(' + i.PrintDump() + '),'
        stringy = stringy.removesuffix(',')
        stringy += '),VariableData=('
        for i in self.VariableData:
            stringy += f'(Name={ f'\"{i.Name}\"' if len(i.Name)>0 else '' },Type={i.Type.name}),'
        stringy = stringy.removesuffix(',')
        stringy += '),ConsolidatedOutputLinkData=('        
        for i in self.ConsolidatedOutputLinkData:
            stringy += f'(LinkIdAndLinkedBehavior={i.LinkIdAndLinkedBehavior},ActivateDelay={i.ActiveDelay}),'
        stringy = stringy.removesuffix(',')
        stringy += '),ConsolidatedVariableLinkData=('        
        for i in self.ConsolidatedVariableLinkData:
            stringy += i.PrintDump() + ','
        stringy = stringy.removesuffix(',')
        stringy += '),ConsolidatedLinkedVariables=('
        for i in self.ConsolidatedLinkedVariables:
            stringy += str(i) + ','
        stringy = stringy.removesuffix(',')
        stringy += ')'
        return stringy
    
    
    def ExportNodeStructure(self):
        """
        Exports our sequence object data back into node dictionary structure
        """
        node=self.NodeData
        node['EventData2'] = []
        for i in self.BehaviorData2:
            node['EventData2'].append({
                'UserData':{i.UserData},
                'OutputVariables':{'ArrayIndexAndLength':i.LinkedVariables},
                'OutputLinks':{'ArrayIndexAndLength':i.OutputLinks}
            })
        node['BehaviorData2'] = []
        for i in self.BehaviorData2:
            node['VariableData'].append({
                'Behavior': f'{i.BehaviorClass}\'{i.BehaviorObject}\'',
                'LinkedVariables': {'ArrayIndexAndLength':i.LinkedVariables,'OutputLinks':{'ArrayIndexAndLength':i.OutputLinks}}
                })
        node['VariableData'] = []
        for i in self.VariableData:
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
        