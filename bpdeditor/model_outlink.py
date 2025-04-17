from __future__ import annotations
from typing import List
from bpdeditor.bpd_classes import *
from PyQt5.QtCore import Qt, QModelIndex, QPersistentModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem

# NOTE I would like to have a custom linkChanged signal emitted from the OutLinkItem
# But for some reason if I inherit both QObject and QStandardItem it causes a crash
# on emit(), so just using the model's dataChanged signal.


class OutLinkItem(QStandardItem):
    def __init__(self, sequence: BehaviorSequence, data):
        super().__init__()
        self.sequence = sequence
        self.LinkIdAndLinkedBehavior = int(data['LinkIdAndLinkedBehavior'])
        self._ActiveDelay: float = float(data['ActivateDelay'])

        # We use the unpacked indexes in the editor, and repack every change here
        (linkID, behaviorIndex) = parse_linkidandlinkedbehavior(self.LinkIdAndLinkedBehavior)
        self._LinkId: int = linkID
        behModel: QStandardItemModel = self.sequence.behaviorModel
        self._LinkIndex: QPersistentModelIndex = QPersistentModelIndex(behModel.index(behaviorIndex, 0))

    @property
    def ActiveDelay(self) -> float:
        return self._ActiveDelay
    @ActiveDelay.setter
    def ActiveDelay(self, new_value):
        if self._ActiveDelay != new_value:
            self._ActiveDelay = new_value
            self.emitDataChanged()
        
    @property
    def LinkId(self) -> int:
        return self._LinkId
    @LinkId.setter
    def LinkId(self, new_value):
        if self._LinkId != new_value:
            self._LinkId = new_value
            self.LinkIdAndLinkedBehavior = pack_linkidandlinkedbehavior(self._LinkId, self._LinkIndex)
            self.emitDataChanged()

    @property
    def LinkIndex(self) -> int:
        return self._LinkIndex.row()
    @LinkIndex.setter
    def LinkIndex(self, new_value: int):
        if self._LinkIndex.row() != new_value:
            self._LinkIndex = QPersistentModelIndex(self.model().behaviorModel.index(new_value, 0))
            self.LinkIdAndLinkedBehavior = pack_linkidandlinkedbehavior(self._LinkId, self._LinkIndex.row())
            self.emitDataChanged()

    def __str__(self) -> str:
        return f'LinkIdAndLinkedBehavior={self.LinkIdAndLinkedBehavior},ActivateDelay={self.ActiveDelay}'


class OutLinkItemModel(QStandardItemModel):
    def __init__(self, data: List[OutLinkItem], sequence, parent):
        super().__init__(parent)
        self.sequence = sequence
        self.behaviorModel: QStandardItemModel = parent
        self.setColumnCount(3)
        for i, item in enumerate(data):
            self.setItem(i, item)

    def newItem(self) -> OutLinkItem:
        sequence = self.sequence
        item = OutLinkItem(sequence, {'LinkIdAndLinkedBehavior':'0','ActivateDelay':'0.0'})
        self.appendRow(item)
        return item
    
    def data(self, index, role):
        (row, col) = (index.row(), index.column())
        item: OutLinkItem = self.item(row)
        if not item:
            return
        if role == Qt.DisplayRole:
            linkedBehaviorName = self.behaviorModel.item(item.LinkId, 0).BehaviorObject
            return f"{str(row)} - {str(item.LinkId)} - {linkedBehaviorName} - {item.ActiveDelay}"
        elif role == Qt.EditRole:
            if col == 0:
                return item.LinkId
            elif col == 1:
                return item.ActiveDelay
            elif col == 2:
                return item.LinkIndex
    
    def setData(self, index, value, role) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False
        
        (row, col) = (index.row(), index.column())
        item: OutLinkItem = self.item(row)
        if col == 0:
            try:
                item.LinkId = int(value)
            except: # Not an integer
                return False
        elif col == 1:
            if value.isnumeric():
                item.ActiveDelay = float(value)
            else:
                return False
        elif col == 2:
            item.LinkIndex = value
        
        #self.dataChanged.emit(index, index)
        return True
    
    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled
