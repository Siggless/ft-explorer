from __future__ import annotations
from typing import List
from bpdeditor.bpd_classes import *
from PyQt5.QtCore import Qt, QModelIndex, QPersistentModelIndex
from bpdeditor.model_sequenceItem import *

class EventItem(SequenceItem):
    def __init__(self, sequence: BehaviorSequence, data):
        super().__init__(sequence, data, 'OutputVariables')
        self.UserData: dict = data['UserData']

    def __str__(self) -> str:
        stringy:str = f'UserData=('
        for key, value in self.UserData.items():
            stringy += f'{str(key)}={str(value)},'

        stringy = stringy.removesuffix(',')
        stringy += f'),OutputVariables=(ArrayIndexAndLength={self.LinkedVariables}),OutputLinks=(ArrayIndexAndLength={self.OutputLinks})'
        return stringy


class EventItemModel(SequenceItemModel):
    def __init__(self, data: List[EventItem], sequence, parent=None):
        super().__init__(sequence, parent)
        for i, item in enumerate(data):
            self.setItem(i, item)
        self.stringTypes = []
        if len(data) > 0:
            self.stringTypes = [i.startswith('"') for i in data[0].UserData.values()]
        self.setColumnCount(len(self.stringTypes))

    def newItem(self) -> EventItem:
        sequence = self.sequence
        item = EventItem(sequence, {
            'UserData':{
                'EventName':'\"NewEvent\"',
                'bEnabled':'True',
                'bReplicate':'False',
                'bReplicateReliable':'True',
                'bServerOnly':'False',
                'MaxTriggerCount':'0',
                'ReTriggerDelay':'0.000000',
                'FilterObject':'None'
            },
            'OutputVariables':{'ArrayIndexAndLength':'0'},
            'OutputLinks':{'ArrayIndexAndLength':'0'}
            })
        self.appendRow(item)
        return item

    def data(self, index, role):
        (row, col) = (index.row(), index.column())
        event: EventItem = self.item(row)
        userData = event.UserData
        key = list(userData.keys())[col]
        value = list(userData.values())[col]
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if self.stringTypes[col]:
                return value.strip('"')
            else:
                if value == 'True' or value == 'False':
                    value = True if value == 'True' else False
                return value
        elif role == Qt.UserRole:   # UserRole is KeyValue pairs for widget setup
            if self.stringTypes[col]:
                return (key, value.strip('"'))
            else:
                if value == 'True' or value == 'False':
                    value = True if value == 'True' else False
                return (key, value)
    
    def setData(self, index, value, role) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False
        
        (row, col) = (index.row(), index.column())
        event: EventItem = self.item(row)
        userData = event.UserData
        key = list(userData.keys())[col]
        
        # We need to add correct quotes for how the various types are stored
        if self.stringTypes[col]:
            value = f'\"{value}\"'
        elif type(value) is not str:
            value = str(value)
        
        userData[key] = value
        
        self.dataChanged.emit(index, index)
        return True
