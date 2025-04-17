from __future__ import annotations
from typing import List
from bpdeditor.bpd_classes import *
from PyQt5.QtCore import Qt, QModelIndex, QPersistentModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem


class VariableItem(QStandardItem):
    def __init__(self, sequence: BehaviorSequence, data):
        super().__init__()
        self.sequence = sequence
        self._name: str = data['Name'].strip('"')
        self._type: VariableTypes = VariableTypes[data['Type']]
        
    @property
    def Name(self) -> str:
        return self._name
    @Name.setter
    def Name(self, new_value):
        if self._name != new_value:
            self._name = new_value
            self.emitDataChanged()
            
    @property
    def Type(self) -> VariableTypes:
        return self._type
    @Type.setter
    def Type(self, new_value):
        if self._type != new_value:
            self._type = new_value
            self.emitDataChanged()
    
    def __str__(self) -> str:
        return f'Name={f'\"{self.Name}\"' if len(self.Name) > 0 else ''},Type={self.Type.name}'


class VariableItemModel(QStandardItemModel):
    def __init__(self, data: List[VariableItem], sequence, parent=None):
        super().__init__(parent)
        self.sequence = sequence
        self.setColumnCount(2)
        for i, item in enumerate(data):
            self.setItem(i, item)
    
    def newItem(self) -> VariableItem:
        sequence = self.sequence
        item = VariableItem(sequence, {'Name':'NewVariable','Type':'BVAR_None'})
        self.appendRow(item)
        return item

    def data(self, index, role):
        (row, col) = (index.row(), index.column())
        var: VariableItem = self.item(row)
        if role == Qt.DisplayRole:
            return f"{str(row)} - {var.Name} - {str(var.Type.name)}"
        
        if role == Qt.EditRole:
            if col == 0:
                return var.Name
            elif col == 1:
                return var.Type.value
    
    def setData(self, index, value, role) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False
        
        (row, col) = (index.row(), index.column())
        var: VariableItem = self.item(row)
        if col == 0:
            var.Name = value
        elif col == 1:
            var.Type = VariableTypes(value)
        
        # Not needed since all edits fire this from the Item
        #self.dataChanged.emit(index, index)
        return True
    
    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled
