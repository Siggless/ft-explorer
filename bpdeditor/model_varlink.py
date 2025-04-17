from __future__ import annotations
from typing import List
from bpdeditor.bpd_classes import *
from PyQt5.QtCore import Qt, QModelIndex, QPersistentModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem


class VarLinkItem(QStandardItem):
    def __init__(self, sequence: BehaviorSequence, data):
        super().__init__()
        self.sequence = sequence
        self._PropertyName: str = data['PropertyName'].strip('"')
        self._VariableLinkType: VariableLinkTypes = VariableLinkTypes[data['VariableLinkType']]
        self._ConnectionIndex = int(data['ConnectionIndex'])
        self._LinkedVariables: int = int(data['LinkedVariables']['ArrayIndexAndLength'])
        '''ArrayIndexAndLength pointing to ConsolidatedLinkedVariables'''
        self._CachedProperty = str(data['CachedProperty'])

        # We use the unpacked indexes in the editor, then repack during reconsolidation
        # Since they need to be consecutive indexes to pack to ArrayIndexAndLength
        (index, length) = parse_arrayindexandlength(self._LinkedVariables)
        linkedVariableIndexes: List[int] = [self.sequence.ConsolidatedLinkedVariables[i] for i in range(index, index+length)]
        self._VariableIndexes: List[QPersistentModelIndex] = []
        """The model indexes of the linked VarItems (we bypass the CLV list here)"""
        varModel: QStandardItemModel = self.sequence.varModel
        self._VariableIndexes = [QPersistentModelIndex(varModel.index(row, 0)) for row in linkedVariableIndexes]
        
    @property
    def PropertyName(self) -> str:
        return self._PropertyName
    @PropertyName.setter
    def PropertyName(self, new_value):
        if self._PropertyName != new_value:
            self._PropertyName = new_value
            self.emitDataChanged()
            
    @property
    def VariableLinkType(self) -> VariableLinkTypes:
        return self._VariableLinkType
    @VariableLinkType.setter
    def VariableLinkType(self, new_value):
        if self._VariableLinkType != new_value:
            self._VariableLinkType = new_value
            self.emitDataChanged()
        
    @property
    def ConnectionIndex(self) -> int:
        return self._ConnectionIndex
    @ConnectionIndex.setter
    def ConnectionIndex(self, new_value):
        if self._ConnectionIndex != new_value:
            self._ConnectionIndex = new_value
            self.emitDataChanged()

    def GetAllVariableIndexes(self) -> List[int]:
        return [x.row() for x in self._VariableIndexes]
    def GetVariableIndex(self, i) -> int:
        return self._VariableIndexes[i].row()
    def SetVariableIndex(self, i, new_value):
        if self._VariableIndexes[i].row() != new_value:
            varModel: QStandardItemModel = self.sequence.varModel
            self._VariableIndexes[i] = QPersistentModelIndex(varModel.index(new_value, 0))
            self.emitDataChanged()
            
    def __str__(self) -> str:
        stringy:str = f'(PropertyName=\"{self._PropertyName}\",'
        stringy += f'VariableLinkType={self._VariableLinkType._name_},'
        stringy += f'ConnectionIndex={str(self._ConnectionIndex)},'
        stringy += f'LinkedVariables=(ArrayIndexAndLength={self._LinkedVariables}),'
        stringy += f'CachedProperty={str(self._CachedProperty)})'
        return stringy


class VarLinkItemModel(QStandardItemModel):
    def __init__(self, data: List[VarLinkItem], sequence, parent=None):
        super().__init__(parent)
        self.sequence = sequence
        self.setColumnCount(10) #2 + max arrayLength - bodge until we use children items
        for i, item in enumerate(data):
            self.setItem(i, item)

    def newItem(self, cId=0, linkType=VariableLinkTypes.BVARLINK_Unknown.name) -> VarLinkItem:
        sequence = self.sequence
        item = VarLinkItem(sequence, {'PropertyName':'NewVarLink','VariableLinkType':linkType,'ConnectionIndex':str(cId),'LinkedVariables':{'ArrayIndexAndLength':'1'},'CachedProperty':'None'})
        self.appendRow(item)
        return item
    
    def data(self, index, role):
        if not index.isValid():
            raise IndexError("Make sure columnCount is set correctly you numpty!")
        
        (row, col) = (index.row(), index.column())
        item: VarLinkItem = self.item(row)
        if role == Qt.DisplayRole:
            return f"{str(row)} - {str(item.ConnectionIndex)} - {item.PropertyName} - {str(item.VariableLinkType.name)}"
        
        if role == Qt.EditRole:
            if col == 0:
                return item.PropertyName
            elif col == 1:
                return item.VariableLinkType.name
            elif col == 2:
                return item.ConnectionIndex
            elif col >= 3:
                # The actual link index for this LinkedVariables item
                listIndex = col - 3
                if len(item.GetAllVariableIndexes()) > listIndex:
                    return item.GetVariableIndex(col - 3)
                else:
                    raise IndexError(f"VarLinkItemModel - tried to get index {col - 3} from list len {len(item.VariableIndexes)}")
    
    def setData(self, index, value, role) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False
        
        (row, col) = (index.row(), index.column())
        item: VarLinkItem = self.item(row)
        if col == 0:
            item.PropertyName = value
        elif col == 1:
            item.VariableLinkType = VariableLinkTypes[value]
        elif col == 2:
            try:
                item.ConnectionIndex = int(value)
            except: # Not an integer
                item.ConnectionIndex = item.ConnectionIndex
        elif col >= 3:
            # One of the linked references has changed - update the model index
            item.SetVariableIndex(col - 3,  value)
        
        #self.dataChanged.emit(index, index)
        return True
    
    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled