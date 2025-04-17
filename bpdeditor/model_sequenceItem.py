from __future__ import annotations
from typing import List
from bpdeditor.bpd_classes import *
from PyQt5.QtCore import Qt, QModelIndex, QPersistentModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem

from .model_outlink import OutLinkItem
from .model_varlink import VarLinkItem


class SequenceItem(QStandardItem):
    """
    A SequenceItem is the base class for both Events and Behaviors,
    handling the output links and variable links
    """
    def __init__(self, sequence: BehaviorSequence, data, variablesKey:str):
        super().__init__()
        self.sequence = sequence
        self.LinkedVariables: int = int(data[variablesKey]['ArrayIndexAndLength'])
        self.OutputLinks: int = int(data['OutputLinks']['ArrayIndexAndLength'])
        
        # We use the unpacked indexes in the editor, then repack during reconsolidation
        # Since they need to be consecutive indexes to pack to ArrayIndexAndLength
        self._OutLinkIndexes: List[QPersistentModelIndex] = []
        """ Model indexes of the OutLinkItems """
        self._VarLinkIndexes: List[QPersistentModelIndex] = []
        """ Model indexes of the VarLinkItems """
        
    def GetAllOutLinkItems(self) -> List[OutLinkItem]:
        return [x.model().item(x.row()) for x in self._OutLinkIndexes]
    def GetAllOutLinkIndexes(self) -> List[int]:
        return [x.row() for x in self._OutLinkIndexes]
    def GetOutLinkIndex(self, i) -> int:
        return self._OutLinkIndexes[i].row()
    def SetOutLinkIndex(self, i, new_value):
        if self._OutLinkIndexes[i].row() != new_value:
            linkModel: QStandardItemModel = self.model().outLinkModel
            self._OutLinkIndexes[i] = QPersistentModelIndex(linkModel.index(new_value, 0))
            self.emitDataChanged()
    def AddOutLink(self, linkModelIndex: int):
        linkModel: QStandardItemModel = self.model().outLinkModel
        linkModelIndex = QPersistentModelIndex(linkModel.index(linkModelIndex, 0))
        self._OutLinkIndexes.append(linkModelIndex)
        self.emitDataChanged()
    def RemoveOutLink(self, linkModelIndex: int):
        for idx, linkIndex in enumerate(self.GetAllOutLinkIndexes()):
            if linkIndex == linkModelIndex:
                self._OutLinkIndexes.pop(idx)
        self.emitDataChanged()
    
    def GetAllVarLinkItems(self) -> List[VarLinkItem]:
        return [x.model().item(x.row()) for x in self._VarLinkIndexes]
    def GetAllVarLinkIndexes(self) -> List[int]:
        return [x.row() for x in self._VarLinkIndexes]
    def GetVarLinkIndex(self, i) -> int:
        return self._VarLinkIndexes[i].row()
    def SetVarLinkIndex(self, i, new_value):
        if self._VarLinkIndexes[i].row() != new_value:
            linkModel: QStandardItemModel = self.model().varLinkModel
            self._VarLinkIndexes[i] = QPersistentModelIndex(linkModel.index(new_value, 0))
            self.emitDataChanged()
    def AddVarLink(self, linkModelIndex: int):
        linkModel: QStandardItemModel = self.model().varLinkModel
        newIndex = QPersistentModelIndex(linkModel.index(linkModelIndex, 3))
        self._VarLinkIndexes.append(newIndex)
        self.emitDataChanged()
    def RemoveVarLink(self, linkModelIndex: int):
        for idx, linkIndex in enumerate(self.GetAllVarLinkIndexes()):
            if linkIndex == linkModelIndex:
                self._VarLinkIndexes.pop(idx)
        self.emitDataChanged()


class SequenceItemModel(QStandardItemModel):
    def __init__(self, sequence, parent=None):
        super().__init__(parent)
        self.sequence = sequence
    
    def createLinks(self, outLinkModel, varLinkModel):
        self.outLinkModel: QStandardItemModel = outLinkModel
        self.varLinkModel: QStandardItemModel = varLinkModel
        for row in range(self.rowCount()):
            item: SequenceItem = self.item(row)
            (index, length) = parse_arrayindexandlength(item.OutputLinks)
            for j in range(index, index+length):
                modelIndex = QPersistentModelIndex(self.outLinkModel.index(j, 0))
                item._OutLinkIndexes.append(modelIndex)
            (index, length) = parse_arrayindexandlength(item.LinkedVariables)
            for j in range(index, index+length):
                modelIndex = QPersistentModelIndex(self.varLinkModel.index(j, 0))
                item._VarLinkIndexes.append(modelIndex)


    def addVariableLink(self, index: int, linkModelIndex: int):
        if not index.isValid():
            return False

        item: SequenceItem = self.item(index.row())
        item.AddVarLink(linkModelIndex)

    def removeVariableLink(self, index: int, linkModelIndex: int):
        if not index.isValid():
            return False

        item: SequenceItem = self.item(index.row())
        item.RemoveVarLink(linkModelIndex)


    def addOutputLink(self, index: int, outModelIndex: int):
        if not index.isValid():
            return False

        item: SequenceItem = self.item(index.row())
        item.AddOutLink(outModelIndex)
    
    def removeOutputLink(self, index: int, linkModelIndex: int):
        if not index.isValid():
            return False

        item: SequenceItem = self.item(index.row())
        item.RemoveOutLink(linkModelIndex)

    
    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled
