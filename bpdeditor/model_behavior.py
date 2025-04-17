from __future__ import annotations
from typing import List
from bpdeditor.bpd_classes import *
from PyQt5.QtCore import Qt, QModelIndex, QPersistentModelIndex
from bpdeditor.model_sequenceItem import *

class BehaviorItem(SequenceItem):
    def __init__(self, sequence: BehaviorSequence, data):
        super().__init__(sequence, data, 'LinkedVariables')
        self.Behavior: str = data['Behavior']
        self._BehaviorClass: str = 'None'
        self._BehaviorObject: str = 'None'
        if self.Behavior != 'None':     # GD_ConstructorRoland.Projectiles.Proj_Ep6_ReinforcementFlare:BehaviorProviderDefinition_0
            self._BehaviorClass: str = self.Behavior.split('\'')[0]
            self._BehaviorObject: str = self.Behavior.split('\'')[1]
        
    @property
    def BehaviorClass(self) -> str:
        return self._BehaviorClass
    @BehaviorClass.setter
    def BehaviorClass(self, new_value):
        if self._BehaviorClass != new_value:
            self._BehaviorClass = new_value
            self.Behavior = f"{self._BehaviorClass}\'{self._BehaviorObject}\'"
            self.emitDataChanged()
    
    @property
    def BehaviorObject(self) -> str:
        return self._BehaviorObject
    @BehaviorObject.setter
    def BehaviorObject(self, new_value):
        if self._BehaviorObject != new_value:
            self._BehaviorObject = new_value
            self.Behavior = f"{self._BehaviorClass}\'{self._BehaviorObject}\'"
            self.emitDataChanged()

    def __str__(self) -> str:
        stringy: str = f'Behavior={self.BehaviorClass}\'{self.BehaviorObject}\','
        stringy += f'LinkedVariables=(ArrayIndexAndLength={self.LinkedVariables}),OutputLinks=(ArrayIndexAndLength={self.OutputLinks})'
        return stringy


class BehaviorItemModel(SequenceItemModel):
    def __init__(self, data: List[BehaviorItem], sequence, parent=None):
        super().__init__(sequence, parent)
        self.setColumnCount(2)
        for i, item in enumerate(data):
            self.setItem(i, item)
    
    
    def newItem(self) -> BehaviorItem:
        sequence = self.sequence
        item = BehaviorItem(sequence, {
            'Behavior':'Behavior_NewClass\'NewBehaviorObject\'',
            'LinkedVariables':{'ArrayIndexAndLength':'0'},
            'OutputLinks':{'ArrayIndexAndLength':'0'}
            })
        self.appendRow(item)
        return item
    
    def data(self, index, role):
        (row, col) = (index.row(), index.column())
        item: BehaviorItem = self.item(row)
        if role == Qt.DisplayRole:
            return f"{str(row)} - {str(item.BehaviorObject.split('.')[-1])}"
        if role == Qt.EditRole:
            if col == 0:
                return item.BehaviorClass
            elif col == 1:
                return item.BehaviorObject
    
    def setData(self, index, value, role) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False
        
        (row, col) = (index.row(), index.column())
        item: BehaviorItem = self.item(row)
        if col == 0:
            item.BehaviorClass = value
        elif col == 1:
            item.BehaviorObject = value
        
        #self.dataChanged.emit(index, index)
        return True
