from __future__ import annotations
from dataclasses import dataclass
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


'''
Python classes to populate from the parsed node data
This is a more object-oriented approach than bpd_dot's generate_dot method
It is also a copy of the data, in case we want to actually edit and reconsolidate it
'''
   
class VariableData:
    def __init__(self, nodeData):
        self.Name:str = nodeData['Name'].strip('"')
        self.Type:VariableTypes = VariableTypes[nodeData['Type']]


@dataclass
class VariableLinkData:
    def __init__(self, nodeData, consolidatedList, variableList):
        self.PropertyName:str=nodeData['PropertyName'].strip('"')
        self.VariableLinkType:VariableLinkTypes = VariableLinkTypes[nodeData['VariableLinkType']]
        self.ConnectionIndex = int(nodeData['ConnectionIndex'])
        '''Used on some Output variables - seems to be only Events - the parameter index passed to the output?'''
        self.LinkedVariables:int = int(nodeData['LinkedVariables']['ArrayIndexAndLength'])
        '''ArrayIndexAndLength pointing to VariableData'''
        self.CachedPropery = None
        
        # Save the linked VariableData objects
        self.LinkedVariableList=[]
        if consolidatedList and variableList:
            (index, length) = parse_arrayindexandlength(self.LinkedVariables)
            self.LinkedVariableList = [variableList[consolidatedList[i]] for i in range(index, index+length)]
                
        # For easy access from the nodes
        self.consolidatedList = consolidatedList
        self.variableList = variableList


@dataclass
class OutputLinkData:
    def __init__(self, nodeData, behaviorList = None):
        self.LinkIdAndLinkedBehavior=int(nodeData['LinkIdAndLinkedBehavior'])
        self.ActiveDelay:float=float(nodeData['ActivateDelay'])
        (linkID, behaviorIndex) = parse_linkidandlinkedbehavior(self.LinkIdAndLinkedBehavior)
        self.LinkId:int = linkID
        self.LinkIndex:int = behaviorIndex
        if behaviorList:
            self.LinkedBehavior:BehaviorData = behaviorList[behaviorIndex]
        else:
            self.LinkedBehavior:BehaviorData = None


@dataclass
class EventUserData:
    def __init__(self, nodeData):
        self.NodeData = nodeData
        self.EventName:str = nodeData['EventName'].strip('"')
        self.bEnabled:bool = nodeData['bEnabled'] == 'True'
        self.bReplicate:bool = nodeData['bReplicate'] == 'True'
        self.MaxTriggerCount:int = int(nodeData['MaxTriggerCount'])
        self.ReTriggerDelay:float = float(nodeData['ReTriggerDelay'])
        self.FilterObject = None
@dataclass
class EventData:    
    def __init__(self, nodeData, cvld):
        self.NodeData=nodeData
        self.UserData:EventUserData = EventUserData(nodeData['UserData'])
        self.LinkedVariables:int = int(nodeData['OutputVariables']['ArrayIndexAndLength'])
        self.OutputLinks:int = int(nodeData['OutputLinks']['ArrayIndexAndLength'])
        
        self.Outputs=[]
        self.Variables=[]
        (index, length) = parse_arrayindexandlength(self.LinkedVariables)
        self.Variables=[cvld[i] for i in range(index, index+length)]


@dataclass
class BehaviorExtraData:
    """ TODO get these extra fields - copy from bpd_dot """
@dataclass
class BehaviorData:
    def __init__(self, nodeData, cvld):
        self.NodeData = nodeData
        self.Behavior:str = nodeData['Behavior']
        self.BehaviorClass:str = 'None'
        self.BehaviorObject:str = 'None'
        if self.Behavior != 'None':     # GD_ConstructorRoland.Projectiles.Proj_Ep6_ReinforcementFlare:BehaviorProviderDefinition_0
            self.BehaviorClass:str = self.Behavior.split('\'')[0]
            self.BehaviorObject:str = self.Behavior.split('\'')[1]
        self.LinkedVariables:int = int(nodeData['LinkedVariables']['ArrayIndexAndLength'])
        self.OutputLinks:int = int(nodeData['OutputLinks']['ArrayIndexAndLength'])
        self.ExtraData:BehaviorExtraData = None
        
        self.Outputs=[]
        self.Variables=[]
        (index, length) = parse_arrayindexandlength(self.LinkedVariables)
        self.Variables=[cvld[i] for i in range(index, index+length)]


@dataclass
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
        self.NodeData = seq
        self.Name:str = seq['BehaviorSequenceName'].strip('"')
        
        # Parse variables first so we have objects to link
        self.VariableData = [VariableData(i) for i in seq['VariableData']]
        self.ConsolidatedLinkedVariables = []
        if seq['ConsolidatedLinkedVariables'] != '':
            self.ConsolidatedLinkedVariables = [int(i) for i in seq['ConsolidatedLinkedVariables'].split(',')]
        self.ConsolidatedVariableLinkData = [VariableLinkData(i, self.ConsolidatedLinkedVariables, self.VariableData) for i in seq['ConsolidatedVariableLinkData']]
        
        self.EventData2 = [EventData(i, self.ConsolidatedVariableLinkData) for i in seq['EventData2']]
        self.BehaviorData2 = [BehaviorData(i, self.ConsolidatedVariableLinkData) for i in seq['BehaviorData2']]
        self.ConsolidatedOutputLinkData = [OutputLinkData(i, self.BehaviorData2) for i in seq['ConsolidatedOutputLinkData']]

        # Now store all the output links in the objects
        if len(self.ConsolidatedOutputLinkData)>0:   # Dark_Forest_Combat.TheWorld:PersistentLevel.Main_Sequence.InterpData_0.InterpGroup_0.InterpTrackBehaviors_0.BehaviorProviderDefinition_0
            for i in self.EventData2 + self.BehaviorData2:
                (index, length) = parse_arrayindexandlength(i.OutputLinks)       
                for j in range(index, index+length):
                    linkData = self.ConsolidatedOutputLinkData[j]
                    i.Outputs.append(linkData)
                
